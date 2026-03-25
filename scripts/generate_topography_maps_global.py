#!/usr/bin/env python3
"""
Generate topography maps (elevation, slope, aspect) from field boundary GeoJSON.

This script:
1. Takes GeoJSON with field boundaries (Polygon or MultiPolygon)
2. Fetches elevation from Copernicus GLO-30 DEM (global coverage)
3. Calculates slope and aspect from elevation
4. Generates float GeoTIFFs and JSON metadata

================================================================================
GLOBAL VERSION - Non-US Coverage
================================================================================

This is the global version of generate_topography_maps.py using Copernicus DEM
instead of USGS 3DEP. Use this version for locations outside the United States.

Key Differences from US Version:
- Data Source: Copernicus GLO-30 (global) vs USGS 3DEP (US only)
- Resolution: 30m (vs 5m target in US)
- Coverage: Worldwide (some countries have restricted tiles - see below)

Resolution Notes:
- Copernicus GLO-30: 30m resolution globally
- Fallback: GLO-90 (90m) if GLO-30 tiles unavailable
- Some regions (e.g., Armenia, Azerbaijan) have restricted GLO-30 coverage

DSM vs DTM Note:
- Copernicus DEM is a Digital Surface Model (DSM) - includes buildings,
  infrastructure, and vegetation. This is consistent with USGS 3DEP which
  is also a DSM, not a Digital Terrain Model (DTM).

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
    # Process all fields in GeoJSON
    python scripts/generate_topography_maps_global.py --input data/fields_germany.geojson --output-dir ./topography_maps_global

    # Process single field by ID
    python scripts/generate_topography_maps_global.py --input data/fields_germany.geojson --output-dir ./topography_maps_global --field-id DE_FIELD_001

Full Options:
    --input        Path to GeoJSON file with field boundaries (required)
    --output-dir   Output directory (default: topography_maps_global)
    --padding      Padding around polygon as fraction (default: 0.10 = 10%%)
    --resolution   Target resolution in meters (default: 30, ignored - uses native 30m)
    --field-id     Process single field by ID (default: all fields)

Output Structure:
    {output-dir}/
    └── {field_id}/
        ├── {field_id}_elevation.tif    # Elevation (meters)
        ├── {field_id}_slope.tif       # Slope (degrees, 0-90)
        ├── {field_id}_aspect.tif      # Aspect (degrees, 0-360)
        └── {field_id}_topography_metadata.json

    Aspect reference:
        0° = North
        90° = East
        180° = South
        270° = West

Metadata JSON includes:
    - field_id
    - properties: min/max/average values and units for each property
    - spatial: bounds, CRS, resolution, padding
    - data_source: Copernicus GLO-30 (with fallback note)
    - resolution_note: 30m native, GLO-90 fallback used if applicable

Example:
    python scripts/generate_topography_maps_global.py \\
        --input data/fields_germany.geojson \\
        --output-dir ./topography_maps_global \\
        --field-id DE_FIELD_001 \\
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
from rasterio.io import MemoryFile
from shapely.geometry import box

from dem_stitcher import stitch_dem
from dem_stitcher.datasets import DATASETS


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


def fetch_copernicus_elevation(bounds, resolution=30):
    """Fetch elevation from Copernicus GLO-30 DEM with GLO-90 fallback.
    
    Args:
        bounds: (minx, miny, maxx, maxy) in EPSG:4326
        resolution: Target resolution in meters (default: 30m native)
    
    Returns:
        tuple: (elevation_array, rasterio_profile, resolution_note)
    
    Raises:
        RuntimeError: If both GLO-30 and GLO-90 fail
    """
    print(f"    Fetching Copernicus DEM...")
    
    # Convert resolution from meters to degrees based on latitude
    minx, miny, maxx, maxy = bounds
    mid_lat = (miny + maxy) / 2
    resolution_deg = meters_to_degrees(resolution, mid_lat)
    print(f"    Resolution: {resolution}m -> {resolution_deg[0]:.6f}° x {resolution_deg[1]:.6f}°")
    
    # Try GLO-30 first with fallback to GLO-90
    dem_source = None
    try:
        print(f"    Attempting GLO-30 (30m resolution)...")
        elevation, profile = stitch_dem(
            list(bounds),
            dem_name='glo_30',
            dst_resolution=resolution_deg,
            fill_in_glo_30=True,  # Auto-fallback to GLO-90 for missing tiles
            dst_ellipsoidal_height=False,
            dst_area_or_point='Point'
        )
        dem_source = 'Copernicus GLO-30'
        print(f"    Successfully fetched GLO-30")
    except Exception as e:
        print(f"    GLO-30 failed: {e}")
        dem_source = None
    
    # Fallback to GLO-90 if GLO-30 failed
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
    """Calculate slope and aspect from elevation array.
    
    Args:
        elevation: 2D numpy array of elevation values
        transform: rasterio transform (Affine or tuple)
    
    Returns:
        tuple: (slope_deg, aspect_deg) arrays
    """
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


def save_float_geotiff(output_path, data, profile, nodata=-9999):
    """Save Float32 GeoTIFF."""
    data_clean = np.where(np.isnan(data), nodata, data).astype(np.float32)
    
    height, width = data_clean.shape
    
    out_profile = profile.copy()
    out_profile.update({
        'driver': 'GTiff',
        'height': height,
        'width': width,
        'count': 1,
        'dtype': 'float32',
        'nodata': nodata,
    })
    
    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(data_clean, 1)


def generate_topography_maps(
    input_geojson, output_dir, padding=0.10, resolution=30, single_field_id=None
):
    """Generate topography maps for all fields in GeoJSON."""
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
        minx, miny, maxx, maxy = padded_bounds
        print(f"  Bounds: {geometry.bounds}")
        print(f"  Padded: {padded_bounds}")

        try:
            elevation, profile, dem_source = fetch_copernicus_elevation(padded_bounds, resolution)
        except Exception as e:
            print(f"  ERROR: Failed to fetch DEM for {field_id}: {e}")
            continue

        print(f"  Successfully fetched DEM")
        
        # Calculate actual resolution from profile
        if 'transform' in profile:
            actual_res = abs(profile['transform'][0])
            # Convert to approximate meters
            mid_lat = (miny + maxy) / 2
            meters_per_deg = 111320 * max(0.01, math.cos(math.radians(mid_lat)))
            actual_resolution = actual_res * meters_per_deg
        else:
            actual_resolution = resolution

        valid = elevation[~np.isnan(elevation)]
        if len(valid) == 0:
            print(f"  WARNING: No valid elevation data for {field_id}")
            continue

        elev_min, elev_max = float(np.min(valid)), float(np.max(valid))
        elev_avg = float(np.mean(valid))
        print(f"  Elevation: {elev_min:.1f}m to {elev_max:.1f}m (avg: {elev_avg:.1f}m)")
        print(f"  Dimensions: {elevation.shape[1]}x{elevation.shape[0]}")
        print(f"  DEM Source: {dem_source}")

        print(f"  Calculating slope and aspect...")
        slope_deg, aspect_deg = calculate_slope_aspect(elevation, profile['transform'])

        slope_clean = slope_deg[~np.isnan(slope_deg)]
        aspect_clean = aspect_deg[~np.isnan(aspect_deg)]

        slope_min = float(np.min(slope_clean)) if len(slope_clean) > 0 else 0.0
        slope_max = float(np.max(slope_clean)) if len(slope_clean) > 0 else 0.0
        print(f"  Slope: {slope_min:.1f}° to {slope_max:.1f}°")

        aspect_min = float(np.min(aspect_clean)) if len(aspect_clean) > 0 else 0.0
        aspect_max = float(np.max(aspect_clean)) if len(aspect_clean) > 0 else 360.0
        if len(aspect_clean) > 0:
            print(f"  Aspect: {aspect_min:.1f}° to {aspect_max:.1f}°")

        print(f"  Saving GeoTIFFs...")

        elev_path = field_output_dir / f"{field_id}_elevation.tif"
        save_float_geotiff(elev_path, elevation, profile)

        slope_path = field_output_dir / f"{field_id}_slope.tif"
        save_float_geotiff(slope_path, slope_deg, profile)

        aspect_path = field_output_dir / f"{field_id}_aspect.tif"
        save_float_geotiff(aspect_path, aspect_deg, profile)

        metadata = {
            "field_id": field_id,
            "properties": {
                "elevation": {
                    "min": elev_min,
                    "max": elev_max,
                    "average": elev_avg,
                    "unit": "meters"
                },
                "slope": {
                    "min": slope_min,
                    "max": slope_max,
                    "unit": "degrees"
                },
                "aspect": {
                    "min": aspect_min,
                    "max": aspect_max,
                    "unit": "degrees (0=N, 90=E, 180=S, 270=W)"
                }
            },
            "spatial": {
                "bounds": list(padded_bounds),
                "crs": "EPSG:4326",
                "resolution_m": actual_resolution,
                "padding_pct": int(padding * 100),
            },
            "data_source": dem_source,
            "resolution_note": "Copernicus GLO-30 at 30m native resolution. GLO-90 (90m) fallback used if GLO-30 tiles unavailable."
        }

        metadata_path = field_output_dir / f"{field_id}_topography_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"  Generated 3 TIFs + metadata")

        results.append({
            "field_id": field_id,
            "output_dir": str(field_output_dir),
            "elevation_range": [elev_min, elev_max],
            "slope_range": [slope_min, slope_max],
            "aspect_range": [aspect_min, aspect_max],
            "dem_source": dem_source,
        })

    print(f"\n=== Summary ===")
    print(f"Total fields: {len(gdf)}")
    print(f"Processed: {len(results)}")
    print(f"Output: {output_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate topography maps (elevation, slope, aspect) from field boundary GeoJSON - GLOBAL VERSION"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to GeoJSON file with field boundaries",
    )
    parser.add_argument(
        "--output-dir",
        default="topography_maps_global",
        help="Output directory (default: topography_maps_global)",
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
        "--field-id",
        default=None,
        help="Process single field by ID (default: all fields)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Topography Map Generation (Global - Copernicus DEM)")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m (native Copernicus)")
    if args.field_id:
        print(f"Field ID: {args.field_id}")
    print("-" * 60)

    try:
        results = generate_topography_maps(
            args.input,
            args.output_dir,
            padding=args.padding,
            resolution=args.resolution,
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
