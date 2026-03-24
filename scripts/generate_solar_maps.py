#!/usr/bin/env python3
"""
Generate solar radiation maps from field boundary GeoJSON.

This script:
1. Takes GeoJSON with field boundaries (Polygon or MultiPolygon)
2. Fetches slope and aspect from USGS 3DEP
3. Calculates solar radiation (MJ/m²/day) based on slope, aspect, and latitude
4. Generates float GeoTIFFs for the specified time resolution
5. Creates JSON metadata with bounds, min/max, source, and resolution

=============================================================================
DETAILED USAGE
=============================================================================

Prerequisites:
    - Python 3.9+
    - Dependencies: geopandas, rasterio, numpy, requests, shapely
    - Internet access to USGS 3DEP API

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
          "properties": {"field_id": "WV_AG_001"},
          "geometry": {
            "type": "Polygon",
            "coordinates": [[[-122.9, 44.9], [-122.8, 44.9], ...]]
          }
        }
      ]
    }

Basic Usage:
    # Process all fields in GeoJSON (monthly default)
    python scripts/generate_solar_maps.py --input data/fields.geojson --output-dir ./solar_output

    # Process single field by ID
    python scripts/generate_solar_maps.py --input data/fields.geojson --output-dir ./solar_output --field-id WV_AG_001

    # Daily resolution
    python scripts/generate_solar_maps.py --input data/fields.geojson --output-dir ./solar_output --time-resolution daily

    # Weekly resolution
    python scripts/generate_solar_maps.py --input data/fields.geojson --output-dir ./solar_output --time-resolution weekly

    # Yearly (single average)
    python scripts/generate_solar_maps.py --input data/fields.geojson --output-dir ./solar_output --time-resolution yearly

Full Options:
    --input           Path to GeoJSON file with field boundaries (required)
    --output-dir      Output directory (default: solar_maps)
    --padding         Padding around polygon as fraction (default: 0.10 = 10%%)
    --resolution      Target resolution in meters (default: 5)
    --time-resolution monthly|weekly|daily|yearly (default: monthly)
    --field-id        Process single field by ID (default: all fields)

Output Structure:
    {output-dir}/
    └── {field_id}/
        ├── {field_id}_solar_jan.tif    # Monthly: jan, feb, ..., dec
        ├── {field_id}_solar_W01.tif    # Weekly: W01, W02, ..., W52
        ├── {field_id}_solar_001.tif    # Daily: 001, 002, ..., 365
        ├── {field_id}_solar_yearly.tif # Yearly: single average
        └── {field_id}_solar_metadata.json

    Units: MJ/m²/day (Megajoules per square meter per day)

Metadata JSON includes:
    - field_id
    - time_resolution
    - properties: min/max values and units for each period
    - spatial: bounds, CRS, resolution, padding
    - data_source: Calculated from USGS 3DEP slope/aspect
    - latitude: centroid latitude used for calculations

Example:
    python scripts/generate_solar_maps.py \\
        --input data/fields_oregon_willamette_ag_2025.geojson \\
        --output-dir ./solar_maps \\
        --field-id WV_AG_001 \\
        --time-resolution monthly \\
        --padding 0.10 \\
        --resolution 5
"""

import argparse
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
import rasterio
from rasterio.io import MemoryFile
from shapely.geometry import box


USGS_3DEP_EXPORT = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
)

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


def fetch_usgs_elevation_preserving_aspect(bbox, target_width, target_height):
    """Fetch elevation from USGS 3DEP with specific dimensions."""
    minx, miny, maxx, maxy = bbox

    params = {
        "f": "image",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{target_width},{target_height}",
        "format": "tiff",
        "pixelType": "F32",
        "noData": "-9999",
        "interpolation": "RSP_BilinearInterpolation",
    }

    try:
        r = requests.get(USGS_3DEP_EXPORT, params=params, timeout=120)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if ctype.startswith("image/") or "tiff" in ctype:
            return r.content
        return None
    except Exception as e:
        print(f"    Error fetching DEM: {e}")
        return None


def fetch_usgs_elevation(bbox, target_res_m):
    """Fetch elevation from USGS 3DEP at specified resolution."""
    minx, miny, maxx, maxy = bbox
    mid_lat = (miny + maxy) / 2

    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(mid_lat))))

    res_deg_x = target_res_m * deg_per_m_lon
    res_deg_y = target_res_m * deg_per_m_lat

    width = max(64, int(math.ceil((maxx - minx) / res_deg_x)))
    height = max(64, int(math.ceil((maxy - miny) / res_deg_y)))

    params = {
        "f": "image",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "noData": "-9999",
        "interpolation": "RSP_BilinearInterpolation",
    }

    try:
        r = requests.get(USGS_3DEP_EXPORT, params=params, timeout=120)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if ctype.startswith("image/") or "tiff" in ctype:
            return r.content
        return None
    except Exception as e:
        print(f"    Error fetching DEM: {e}")
        return None


def calculate_slope_aspect(elevation, transform, bounds):
    """Calculate slope and aspect from elevation array."""
    nodata = -9999
    elevation_clean = np.where(elevation == nodata, np.nan, elevation)

    pixel_width_deg = abs(transform.a)
    pixel_height_deg = abs(transform.e)
    lat = (bounds.bottom + bounds.top) / 2
    meters_per_deg_lon = 111320 * math.cos(math.radians(lat))

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


def fetch_slope_aspect(padded_bounds, resolution):
    """Fetch slope and aspect from USGS 3DEP."""
    minx, miny, maxx, maxy = padded_bounds
    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(mid_lat))))

    res_deg = resolution * deg_per_m_lon
    width = max(64, int(math.ceil((maxx - minx) / res_deg)))
    height = max(64, int(math.ceil((maxy - miny) / res_deg)))

    print(f"  Fetching USGS 3DEP at {resolution}m ({width}x{height})...")
    tif_bytes = fetch_usgs_elevation_preserving_aspect(padded_bounds, width, height)

    if tif_bytes is None and resolution == 5:
        print(f"    5m failed, trying 10m...")
        tif_bytes = fetch_usgs_elevation(padded_bounds, 10)

    if tif_bytes is None:
        raise RuntimeError("Failed to fetch DEM from USGS 3DEP")

    with MemoryFile(tif_bytes) as memfile:
        with memfile.open() as src:
            elevation = src.read(1)
            bounds = src.bounds
            transform = src.transform

            print(f"  Calculating slope and aspect...")
            slope_deg, aspect_deg = calculate_slope_aspect(elevation, transform, bounds)

    return slope_deg, aspect_deg, transform, bounds


def calculate_day_angle(day_of_year):
    """Calculate day angle in radians."""
    return 2 * math.pi * (day_of_year - 1) / 365


def calculate_eccentricity(day_angle):
    """Calculate eccentricity correction factor."""
    return 1 + 0.033 * math.cos(day_angle)


def calculate_declination(day_of_year):
    """Calculate solar declination in degrees."""
    return 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))


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
    declination_rad = math.radians(declination)

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
    input_geojson, output_dir, padding=0.10, resolution=5, 
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

        slope_array, aspect_array, transform, bounds = fetch_slope_aspect(padded_bounds, resolution)

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
            "data_source": "Calculated from USGS 3DEP slope/aspect",
            "latitude": centroid_lat
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
        description="Generate solar radiation maps from field boundary GeoJSON"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to GeoJSON file with field boundaries",
    )
    parser.add_argument(
        "--output-dir",
        default="solar_maps",
        help="Output directory (default: solar_maps)",
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
        default=5,
        help="Target resolution in meters (default: 5)",
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
    print("Solar Radiation Map Generation")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m")
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
