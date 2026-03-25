#!/usr/bin/env python3
"""
Generate solar radiation maps from field boundary GeoJSON.

This script:
1. Takes GeoJSON with field boundaries (Polygon or MultiPolygon)
2. Fetches slope and aspect from Copernicus GLO-30 DEM (global coverage)
3. Calculates solar radiation (MJ/m²/day) based on slope, aspect, and latitude
4. Generates float GeoTIFFs for the specified time resolution
5. Creates JSON metadata with bounds, min/max, source, and resolution

================================================================================
GLOBAL VERSION - Non-US Coverage
================================================================================

This is the global version of generate_solar_maps.py using Copernicus DEM
instead of USGS 3DEP. Use this version for locations outside the United States.

Key Differences from US Version:
- Topography Source: Copernicus GLO-30 (global) vs USGS 3DEP (US only)
- Resolution: 30m (vs 5m target in US)

Resolution Notes:
- Copernicus GLO-30: 30m resolution globally
- Fallback: GLO-90 (90m) if GLO-30 tiles unavailable
- Some regions have restricted GLO-30 coverage

The solar radiation calculation itself is location-agnostic and works globally
based on latitude, day of year, slope, and aspect.

================================================================================
DETAILED USAGE
================================================================================

Prerequisites:
    - Python 3.9+
    - Dependencies: geopandas, rasterio, numpy, dem-stitcher, shapely
    - Internet access to AWS (for Copernicus DEM)

Input Format:
    GeoJSON file with:
    - A "field_id" property for each feature (or auto-generated if missing)
    - Polygon or MultiPolygon geometries in WGS84 (EPSG:4326)

    Example GeoJSON:
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "properties": {"field_id": "DE_FIELD_001"},
          "geometry": {
            "type": "Polygon",
            "coordinates": [[[10.0, 50.0], [10.5, 50.0], ...]]
          }
        }
      ]
    }

Basic Usage:
    # Process all fields in GeoJSON (monthly default)
    python scripts/generate_solar_maps_global.py --input data/fields_germany.geojson --output-dir ./solar_maps_global

    # Process single field by ID
    python scripts/generate_solar_maps_global.py --input data/fields_germany.geojson --output-dir ./solar_maps_global --field-id DE_FIELD_001

    # Daily resolution
    python scripts/generate_solar_maps_global.py --input data/fields_germany.geojson --output-dir ./solar_maps_global --time-resolution daily

    # Weekly resolution
    python scripts/generate_solar_maps_global.py --input data/fields_germany.geojson --output-dir ./solar_maps_global --time-resolution weekly

    # Yearly (single average)
    python scripts/generate_solar_maps_global.py --input data/fields_germany.geojson --output-dir ./solar_maps_global --time-resolution yearly

Full Options:
    --input           Path to GeoJSON file with field boundaries (required)
    --output-dir      Output directory (default: solar_maps_global)
    --padding         Padding around polygon as fraction (default: 0.10 = 10%%)
    --resolution      Target resolution in meters (default: 30, uses native 30m)
    --time-resolution monthly|weekly|daily|yearly (default: monthly)
    --field-id        Process single field by ID (default: all fields)

Output Structure:
    {output-dir}/
    └── {field_id}/
        ├── {field_id}_solar_jan.tif    # Monthly: jan, feb, ..., dec
        ├── {field_id}_solar_W01.tif   # Weekly: W01, W02, ..., W52
        ├── {field_id}_solar_001.tif    # Daily: 001, 002, ..., 365
        ├── {field_id}_solar_yearly.tif # Yearly: single average
        └── {field_id}_solar_metadata.json

    Units: MJ/m²/day (Megajoules per square meter per day)

Metadata JSON includes:
    - field_id
    - time_resolution
    - properties: min/max values and units for each period
    - spatial: bounds, CRS, resolution, padding
    - data_source: Calculated from Copernicus GLO-30 slope/aspect
    - latitude: centroid latitude used for calculations

Example:
    python scripts/generate_solar_maps_global.py \\
        --input data/fields_germany.geojson \\
        --output-dir ./solar_maps_global \\
        --field-id DE_FIELD_001 \\
        --time-resolution monthly \\
        --padding 0.10
"""

import argparse
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

from dem_stitcher import stitch_dem
from shapely.geometry import box


GSC = 0.0820

MONTHS = [
    ('jan', 31, 1),
    ('feb', 28, 32),
    ('mar', 31, 60),
    ('apr', 30, 91),
    ('may', 31, 121),
    ('jun', 30, 152),
    ('jul', 31, 182),
    ('aug', 31, 213),
    ('sep', 30, 244),
    ('oct', 31, 274),
    ('nov', 30, 305),
    ('dec', 31, 335),
]

WEEKS = [(f'W{i:02d}', (i - 1) * 7 + 1, i * 7) for i in range(1, 53)]


def parse_geojson(input_path):
    """Parse GeoJSON file and return GeoDataFrame in WGS84."""
    gdf = gpd.read_file(input_path)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def calculate_padded_bounds(bounds, padding):
    """Apply padding to bounds."""
    minx, miny, maxx, maxy = bounds
    dx = (maxx - minx) * padding
    dy = (maxy - miny) * padding
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def meters_to_degrees(meters, latitude):
    """Convert meters to degrees at a given latitude.
    
    Args:
        meters: Resolution in meters
        latitude: Latitude in degrees
    
    Returns:
        tuple: (x_resolution, y_resolution) in degrees
    """
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lon = meters_per_degree_lat * max(0.01, abs(math.cos(math.radians(latitude))))
    x_res = meters / meters_per_degree_lon
    y_res = meters / meters_per_degree_lat
    return (x_res, y_res)


def fetch_copernicus_dem(bounds, resolution=30):
    """Fetch elevation from Copernicus GLO-30 DEM with GLO-90 fallback.
    
    Args:
        bounds: (minx, miny, maxx, maxy) in EPSG:4326
        resolution: Target resolution in meters (default: 30m native)
    
    Returns:
        tuple: (elevation_array, rasterio_profile, dem_source)
    
    Raises:
        RuntimeError: If both GLO-30 and GLO-90 fail
    """
    print(f"    Fetching Copernicus DEM...")
    
    # Convert resolution from meters to degrees based on latitude
    minx, miny, maxx, maxy = bounds
    mid_lat = (miny + maxy) / 2
    resolution_deg = meters_to_degrees(resolution, mid_lat)
    print(f"    Resolution: {resolution}m -> {resolution_deg[0]:.6f}° x {resolution_deg[1]:.6f}°")
    
    dem_source = None
    
    try:
        print(f"    Attempting GLO-30 (30m resolution)...")
        elevation, profile = stitch_dem(
            list(bounds),
            dem_name='glo_30',
            dst_resolution=resolution_deg,
            fill_in_glo_30=True,
            dst_ellipsoidal_height=False,
            dst_area_or_point='Point'
        )
        dem_source = 'Copernicus GLO-30'
        print(f"    Successfully fetched GLO-30")
    except Exception as e:
        print(f"    GLO-30 failed: {e}")
        dem_source = None
    
    if dem_source is None:
        try:
            print(f"    Attempting GLO-90 fallback (90m resolution)...")
            resolution_90_deg = meters_to_degrees(90, mid_lat)
            elevation, profile = stitch_dem(
                list(bounds),
                dem_name='glo_90',
                dst_resolution=resolution_90_deg,
                dst_ellipsoidal_height=False,
                dst_area_or_point='Point'
            )
            dem_source = 'Copernicus GLO-90 (fallback)'
            print(f"    Successfully fetched GLO-90 fallback")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch DEM from both GLO-30 and GLO-90: {e}")
    
    # Handle nodata values
    nodata = -9999
    elevation = np.where(elevation == nodata, np.nan, elevation)
    
    return elevation, profile, dem_source


def calculate_slope_aspect(elevation, transform):
    """Calculate slope and aspect from elevation array."""
    nodata = -9999
    elevation_clean = np.where(elevation == nodata, np.nan, elevation)
    
    # Handle both Affine objects and tuples
    if hasattr(transform, 'a'):
        pixel_width_deg = abs(transform.a)
        pixel_height_deg = abs(transform.e)
    else:
        # Tuple format: (a, b, c, d, e, f) where a=width_res, e=height_res
        pixel_width_deg = abs(transform[0])
        pixel_height_deg = abs(transform[4])
    
    # Get bounds from transform
    height, width = elevation_clean.shape
    bounds = rasterio.transform.array_bounds(height, width, transform)
    lat = (bounds[1] + bounds[3]) / 2
    meters_per_deg_lon = 111320 * max(0.01, math.cos(math.radians(lat)))
    
    pixel_width = pixel_width_deg * meters_per_deg_lon
    pixel_height = pixel_height_deg * 111320
    
    dy, dx = np.gradient(elevation_clean, pixel_height, pixel_width)
    
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    
    aspect_rad = np.arctan2(dx, -dy)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)
    aspect_deg = np.where(slope_deg < 0.1, np.nan, aspect_deg)
    
    return slope_deg, aspect_deg


def calculate_day_angle(day_of_year):
    """Calculate day angle in radians."""
    return 2 * math.pi * (day_of_year - 1) / 365


def calculate_eccentricity(day_angle):
    """Calculate eccentricity correction factor."""
    return 1 + 0.033 * math.cos(day_angle)


def calculate_declination(day_of_year):
    """Calculate solar declination in degrees."""
    return 23.45 * math.radians(360 / 365 * (day_of_year - 81))


def calculate_sunset_hour_angle(latitude_rad, declination_rad):
    """Calculate sunset hour angle in radians."""
    tan_product = -math.tan(latitude_rad) * math.tan(declination_rad)
    tan_product = max(-1, min(1, tan_product))
    return math.acos(tan_product)


def calculate_extraterrestrial_radiation(latitude_rad, declination_rad, sunset_angle, eccentricity):
    """Calculate extraterrestrial radiation on horizontal surface (Ra in MJ/m^2/day)."""
    term1 = sunset_angle * math.sin(latitude_rad) * math.sin(declination_rad)
    term2 = math.cos(latitude_rad) * math.cos(declination_rad) * math.sin(sunset_angle)
    Ra = (24 * 60 / math.pi) * GSC * eccentricity * (term1 + term2)
    return max(0, Ra)


def calculate_slope_radiation_vectorized(Ra, slope_array, aspect_array, declination_rad, sunset_angle):
    """Calculate radiation on sloped surface for each pixel."""
    aspect_solar = 180 - aspect_array
    
    slope_rad = np.radians(slope_array)
    aspect_solar_rad = np.radians(aspect_solar)
    decl = declination_rad
    omega = sunset_angle
    
    term1 = np.cos(slope_rad) * np.cos(decl) * np.sin(omega)
    term2 = (math.pi / 180) * omega * np.sin(slope_rad) * np.sin(aspect_solar_rad) * np.sin(decl)
    
    Rs = Ra * (term1 + term2)
    
    flat_mask = (slope_array < 0.1) | np.isnan(slope_array)
    Rs[flat_mask] = Ra
    
    Rs = np.maximum(0, Rs)
    Rs = np.where(np.isnan(Ra), np.nan, Rs)
    
    return Rs


def calculate_daily_solar(latitude_deg, slope_array, aspect_array, day_of_year):
    """Calculate daily solar radiation for a specific day."""
    day_angle = calculate_day_angle(day_of_year)
    eccentricity = calculate_eccentricity(day_angle)
    declination = calculate_declination(day_of_year)
    declination_rad = declination
    
    latitude_rad = math.radians(latitude_deg)
    sunset_angle = calculate_sunset_hour_angle(latitude_rad, declination_rad)
    
    Ra = calculate_extraterrestrial_radiation(latitude_rad, declination_rad, sunset_angle, eccentricity)
    
    Rs = calculate_slope_radiation_vectorized(Ra, slope_array, aspect_array, declination_rad, sunset_angle)
    
    return Rs


def calculate_period_solar(latitude_deg, slope_array, aspect_array, start_day, end_day):
    """Calculate average solar radiation over a period (start_day to end_day inclusive)."""
    total = np.zeros_like(slope_array, dtype=np.float64)
    count = 0
    
    for day in range(start_day, min(end_day + 1, 366)):
        daily = calculate_daily_solar(latitude_deg, slope_array, aspect_array, day)
        total = np.nansum([total, daily], axis=0)
        count += 1
    
    return total / count if count > 0 else total


def save_float_geotiff(output_path, data, transform, crs="EPSG:4326", nodata=-9999):
    """Save Float32 GeoTIFF."""
    data_clean = np.where(np.isnan(data), nodata, data).astype(np.float32)
    height, width = data_clean.shape
    
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "crs": crs,
        "nodata": nodata,
    }
    
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data_clean, 1)


def generate_solar_maps(
    input_geojson, output_dir, padding=0.10, resolution=30, 
    time_resolution="monthly", single_field_id=None
):
    """Generate solar maps for all fields in GeoJSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading fields from {input_geojson}...")
    gdf = parse_geojson(input_geojson)

    if "field_id" not in gdf.columns:
        gdf["field_id"] = [f"field_{i}" for i in range(len(gdf))]

    if single_field_id:
        gdf = gdf[gdf["field_id"] == single_field_id]
        if len(gdf) == 0:
            raise ValueError(f"Field ID '{single_field_id}' not found in GeoJSON")

    print(f"Processing {len(gdf)} field(s)...")

    results = []
    for idx, (_, row) in enumerate(gdf.iterrows()):
        field_id = row["field_id"]
        geometry = row.geometry

        field_output_dir = output_dir / field_id
        field_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{idx + 1}/{len(gdf)}] Processing {field_id}...")

        padded_bounds = calculate_padded_bounds(geometry.bounds, padding)
        centroid_lat = geometry.centroid.y
        centroid_lon = geometry.centroid.x

        print(f"  Bounds: {geometry.bounds}")
        print(f"  Padded: {padded_bounds}")
        print(f"  Centroid: {centroid_lon:.4f}, {centroid_lat:.4f}")

        # Fetch DEM from Copernicus
        try:
            elevation, dem_profile, dem_source = fetch_copernicus_dem(padded_bounds, resolution)
        except Exception as e:
            print(f"  ERROR: Failed to fetch DEM for {field_id}: {e}")
            continue
        
        # Calculate slope and aspect
        print(f"  Calculating slope and aspect...")
        slope_array, aspect_array = calculate_slope_aspect(elevation, dem_profile['transform'])
        
        # Get transform for output
        transform = dem_profile['transform']

        print(f"  Array shape: {slope_array.shape}")
        print(f"  Calculating solar radiation ({time_resolution})...")

        property_stats = {}

        if time_resolution == "monthly":
            for month_name, days, start_day in MONTHS:
                radiation = calculate_period_solar(
                    centroid_lat, slope_array, aspect_array, start_day, start_day + days - 1
                )
                output_path = field_output_dir / f"{field_id}_solar_{month_name}.tif"
                save_float_geotiff(output_path, radiation, transform)

                valid = radiation[~np.isnan(radiation)]
                if len(valid) > 0:
                    property_stats[month_name] = {
                        "min": float(np.min(valid)),
                        "max": float(np.max(valid)),
                        "unit": "MJ/m²/day"
                    }
                print(f"    {month_name}: {property_stats.get(month_name, {}).get('min', 'N/A'):.2f} - {property_stats.get(month_name, {}).get('max', 'N/A'):.2f}")

        elif time_resolution == "weekly":
            for week_name, start_day, end_day in WEEKS:
                radiation = calculate_period_solar(
                    centroid_lat, slope_array, aspect_array, start_day, end_day
                )
                output_path = field_output_dir / f"{field_id}_solar_{week_name}.tif"
                save_float_geotiff(output_path, radiation, transform)

                valid = radiation[~np.isnan(radiation)]
                if len(valid) > 0:
                    property_stats[week_name] = {
                        "min": float(np.min(valid)),
                        "max": float(np.max(valid)),
                        "unit": "MJ/m²/day"
                    }
            print(f"    Generated 52 weekly TIFs")

        elif time_resolution == "daily":
            for day in range(1, 366):
                radiation = calculate_daily_solar(centroid_lat, slope_array, aspect_array, day)
                day_name = f"{day:03d}"
                output_path = field_output_dir / f"{field_id}_solar_{day_name}.tif"
                save_float_geotiff(output_path, radiation, transform)

                valid = radiation[~np.isnan(radiation)]
                if len(valid) > 0:
                    property_stats[day_name] = {
                        "min": float(np.min(valid)),
                        "max": float(np.max(valid)),
                        "unit": "MJ/m²/day"
                    }
            print(f"    Generated 365 daily TIFs")

        elif time_resolution == "yearly":
            radiation = calculate_period_solar(centroid_lat, slope_array, aspect_array, 1, 365)
            output_path = field_output_dir / f"{field_id}_solar_yearly.tif"
            save_float_geotiff(output_path, radiation, transform)

            valid = radiation[~np.isnan(radiation)]
            if len(valid) > 0:
                property_stats["yearly"] = {
                    "min": float(np.min(valid)),
                    "max": float(np.max(valid)),
                    "unit": "MJ/m²/day"
                }
            print(f"    yearly: {property_stats['yearly']['min']:.2f} - {property_stats['yearly']['max']:.2f}")

        metadata = {
            "field_id": field_id,
            "time_resolution": time_resolution,
            "properties": property_stats,
            "spatial": {
                "bounds": list(padded_bounds),
                "crs": "EPSG:4326",
                "resolution_m": resolution,
                "padding_pct": int(padding * 100),
            },
            "data_source": f"Calculated from {dem_source} slope/aspect",
            "dem_source": dem_source,
            "latitude": centroid_lat,
            "resolution_note": "Copernicus GLO-30 at 30m native resolution. GLO-90 (90m) fallback used if GLO-30 tiles unavailable."
        }

        metadata_path = field_output_dir / f"{field_id}_solar_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"  Generated metadata JSON")

        results.append({
            "field_id": field_id,
            "output_dir": str(field_output_dir),
            "time_resolution": time_resolution,
        })

    print(f"\n=== Summary ===")
    print(f"Total fields: {len(gdf)}")
    print(f"Processed: {len(results)}")
    print(f"Output: {output_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate solar radiation maps from field boundary GeoJSON - GLOBAL VERSION"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to GeoJSON file with field boundaries",
    )
    parser.add_argument(
        "--output-dir",
        default="solar_maps_global",
        help="Output directory (default: solar_maps_global)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.10,
        help="Padding around polygon bounds as fraction (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=30,
        help="Target resolution in meters (default: 30, uses native Copernicus resolution)",
    )
    parser.add_argument(
        "--time-resolution",
        default="monthly",
        choices=["monthly", "weekly", "daily", "yearly"],
        help="Time resolution: monthly, weekly, daily, yearly (default: monthly)",
    )
    parser.add_argument(
        "--field-id",
        default=None,
        help="Process single field by ID (default: all fields)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Solar Radiation Map Generation (Global - Copernicus DEM)")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m (native Copernicus)")
    print(f"Time resolution: {args.time_resolution}")
    if args.field_id:
        print(f"Field ID: {args.field_id}")
    print("-" * 60)

    try:
        results = generate_solar_maps(
            args.input,
            args.output_dir,
            padding=args.padding,
            resolution=args.resolution,
            time_resolution=args.time_resolution,
            single_field_id=args.field_id,
        )
        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
