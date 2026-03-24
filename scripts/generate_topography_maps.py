#!/usr/bin/env python3
"""
Generate topography maps (elevation, slope, aspect) from field boundary GeoJSON.

This script:
1. Takes GeoJSON with field boundaries (Polygon or MultiPolygon)
2. Fetches elevation from USGS 3DEP
3. Calculates slope and aspect from elevation
4. Generates float GeoTIFFs and JSON metadata

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
    # Process all fields in GeoJSON
    python scripts/generate_topography_maps.py --input data/fields.geojson --output-dir ./topography_output

    # Process single field by ID
    python scripts/generate_topography_maps.py --input data/fields.geojson --output-dir ./topography_output --field-id WV_AG_001

    # Custom padding and resolution
    python scripts/generate_topography_maps.py --input data/fields.geojson --output-dir ./topography_output --padding 0.15 --resolution 10

Full Options:
    --input        Path to GeoJSON file with field boundaries (required)
    --output-dir   Output directory (default: topography_maps)
    --padding      Padding around polygon as fraction (default: 0.10 = 10%%)
    --resolution   Target resolution in meters (default: 5)
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
    - properties: min/max values and units for each property
    - spatial: bounds, CRS, resolution, padding
    - data_source: USGS 3DEP

Example:
    python scripts/generate_topography_maps.py \\
        --input data/fields_oregon_willamette_ag_2025.geojson \\
        --output-dir ./topography_maps \\
        --field-id WV_AG_001 \\
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
    """Fetch elevation from USGS 3DEP with specific dimensions to preserve aspect ratio."""
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
        print(f"    Error fetching: {e}")
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
        print(f"    Error fetching: {e}")
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


def generate_topography_maps(
    input_geojson, output_dir, padding=0.10, resolution=5, single_field_id=None
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

        mid_lat = (miny + maxy) / 2
        deg_per_m_lat = 1.0 / 111_320.0
        deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(mid_lat))))

        res_deg = resolution * deg_per_m_lon
        lon_range = maxx - minx
        lat_range = maxy - miny

        target_width = max(64, int(math.ceil(lon_range / res_deg)))
        target_height = max(64, int(math.ceil(lat_range / res_deg)))

        print(f"  Fetching USGS 3DEP at {resolution}m (target: {target_width}x{target_height})...")
        tif_bytes = fetch_usgs_elevation_preserving_aspect(padded_bounds, target_width, target_height)

        resolutions = [resolution]
        if resolution == 5:
            resolutions.extend([10, 30])
        elif resolution == 10:
            resolutions.extend([30])

        res_idx = 0
        while tif_bytes is None and res_idx < len(resolutions) - 1:
            print(f"    {resolutions[res_idx]}m failed, trying {resolutions[res_idx + 1]}m...")
            tif_bytes = fetch_usgs_elevation(padded_bounds, resolutions[res_idx + 1])
            res_idx += 1

        if tif_bytes is None:
            print(f"  WARNING: Failed to fetch DEM for {field_id}")
            continue

        print(f"  Successfully fetched DEM")

        with MemoryFile(tif_bytes) as memfile:
            with memfile.open() as src:
                elevation = src.read(1)
                bounds = src.bounds
                transform = src.transform

                nodata = -9999
                valid = elevation[elevation != nodata]
                if len(valid) == 0:
                    print(f"  WARNING: No valid elevation data for {field_id}")
                    continue

                elev_min, elev_max = float(np.min(valid)), float(np.max(valid))
                print(f"  Elevation: {elev_min:.1f}m to {elev_max:.1f}m")
                print(f"  Dimensions: {elevation.shape[1]}x{elevation.shape[0]}")

                print(f"  Calculating slope and aspect...")
                slope_deg, aspect_deg = calculate_slope_aspect(elevation, transform, bounds)

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
                save_float_geotiff(elev_path, elevation.astype(np.float32), transform)

                slope_path = field_output_dir / f"{field_id}_slope.tif"
                save_float_geotiff(slope_path, slope_deg, transform)

                aspect_path = field_output_dir / f"{field_id}_aspect.tif"
                save_float_geotiff(aspect_path, aspect_deg, transform)

                actual_resolution = resolutions[res_idx] if res_idx > 0 else resolution

                metadata = {
                    "field_id": field_id,
                    "properties": {
                        "elevation": {
                            "min": elev_min,
                            "max": elev_max,
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
                    "data_source": "USGS 3DEP"
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
                })

    print(f"\n=== Summary ===")
    print(f"Total fields: {len(gdf)}")
    print(f"Processed: {len(results)}")
    print(f"Output: {output_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate topography maps (elevation, slope, aspect) from field boundary GeoJSON"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to GeoJSON file with field boundaries",
    )
    parser.add_argument(
        "--output-dir",
        default="topography_maps",
        help="Output directory (default: topography_maps)",
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
        "--field-id",
        default=None,
        help="Process single field by ID (default: all fields)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Topography Map Generation")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m")
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
