#!/usr/bin/env python3
"""
Generate DEM, Slope, and Aspect rasters from lat/lon polygon coordinates.

This script:
1. Takes polygon coordinates (GeoJSON or simple [lon,lat] list)
2. Fetches elevation from USGS 3DEP
3. Calculates slope and aspect from elevation
4. Saves three Float32 GeoTIFFs

Usage:
    # GeoJSON polygon format:
    python scripts/lat_lon_polygon_to_dem_slope_aspect.py \
        --input '{"type":"Polygon","coordinates":[[[-122.9,44.8],[-122.8,44.8],...]]}' \
        --output-dir ./terrain_output

    # Simple list format:
    python scripts/lat_lon_polygon_to_dem_slope_aspect.py \
        --input "[[-122.9,44.8],[-122.8,44.8],[-122.85,44.7]]" \
        --output-dir ./terrain_output

    # From file:
    python scripts/lat_lon_polygon_to_dem_slope_aspect.py \
        --input path/to/polygon.geojson \
        --output-dir ./terrain_output \
        --resolution 5 \
        --padding 0.15 \
        --field-id my_field

Output:
    {field_id}_elevation.tif - Float32 elevation in meters
    {field_id}_slope.tif    - Float32 slope in degrees (0-90)
    {field_id}_aspect.tif   - Float32 aspect in degrees (0-360)

Requirements:
    numpy, rasterio, requests, geopandas
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import requests
from rasterio.io import MemoryFile


USGS_3DEP_EXPORT = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
)


def parse_polygon_input(input_str):
    """
    Parse polygon input from various formats.

    Args:
        input_str: JSON string (GeoJSON or simple list) OR path to .geojson/.json file

    Returns:
        dict with 'type' (str), 'coordinates' (list), and 'bounds' (tuple)
    """
    input_str = input_str.strip()

    # Check if it's a file path
    input_path = Path(input_str)
    if input_path.exists():
        with open(input_path, 'r') as f:
            data = json.load(f)
    else:
        # Try to parse as JSON
        try:
            data = json.loads(input_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}")

    # Handle GeoJSON format
    if isinstance(data, dict):
        if data.get('type') == 'Polygon':
            coords = data['coordinates'][0]  # Exterior ring
        elif data.get('type') == 'Feature' and data.get('geometry', {}).get('type') == 'Polygon':
            coords = data['geometry']['coordinates'][0]
        elif 'coordinates' in data and isinstance(data['coordinates'], list):
            # Assume it's a Polygon without type field
            coords = data['coordinates'][0] if isinstance(data['coordinates'][0], list) else data['coordinates']
        else:
            raise ValueError("Unknown GeoJSON format. Expected Polygon or Feature with Polygon geometry.")
    elif isinstance(data, list) and len(data) > 0:
        # Simple list of [lon, lat] pairs
        if isinstance(data[0], list) and len(data[0]) == 2:
            coords = data
        else:
            raise ValueError("Expected list of [lon, lat] pairs")
    else:
        raise ValueError("Invalid input format")

    # Calculate bounds
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    bounds = (min(lons), min(lats), max(lons), max(lats))

    return {
        'type': 'Polygon',
        'coordinates': [coords],
        'bounds': bounds
    }


def calculate_padded_bounds(bounds, padding):
    """
    Apply padding to bounds.

    Args:
        bounds: (min_lon, min_lat, max_lon, max_lat)
        padding: float (e.g., 0.15 for 15%)

    Returns:
        Padded bounds (min_lon, min_lat, max_lon, max_lat)
    """
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
    import rasterio

    # Handle NaN values
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

    print(f"    Saved: {output_path}")


def generate_terrain_rasters(polygon_data, output_dir, target_res_m=5, padding=0.15, field_id=None):
    """
    Generate elevation, slope, and aspect rasters from polygon.

    Args:
        polygon_data: dict from parse_polygon_input()
        output_dir: Path to output directory
        target_res_m: Target resolution in meters
        padding: Padding fraction (e.g., 0.15 for 15%)
        field_id: Optional field ID for output filenames

    Returns:
        dict with paths to generated files
    """
    # Calculate bounds with padding
    padded_bounds = calculate_padded_bounds(polygon_data['bounds'], padding)
    minx, miny, maxx, maxy = padded_bounds

    # Generate field_id if not provided
    if field_id is None:
        field_id = f"polygon_{int(minx*1000)}_{int(miny*1000)}"

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Calculate target dimensions
    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(mid_lat))))

    res_deg = target_res_m * deg_per_m_lon
    lon_range = maxx - minx
    lat_range = maxy - miny

    target_width = max(64, int(math.ceil(lon_range / res_deg)))
    target_height = max(64, int(math.ceil(lat_range / res_deg)))

    # Try to fetch DEM at requested resolution
    print(f"  Fetching USGS 3DEP at {target_res_m}m (target: {target_width}x{target_height})...")
    tif_bytes = fetch_usgs_elevation_preserving_aspect(padded_bounds, target_width, target_height)

    # Fallback chain
    resolutions = [target_res_m]
    if target_res_m == 5:
        resolutions.extend([10, 30])
    elif target_res_m == 10:
        resolutions.extend([30])
    
    res_idx = 0
    while tif_bytes is None and res_idx < len(resolutions):
        print(f"    {resolutions[res_idx]}m failed, trying {resolutions[res_idx+1] if res_idx+1 < len(resolutions) else 'none'}...")
        tif_bytes = fetch_usgs_elevation(padded_bounds, resolutions[res_idx + 1]) if res_idx + 1 < len(resolutions) else None
        res_idx += 1

    if tif_bytes is None:
        raise RuntimeError(f"Failed to fetch DEM. Tried resolutions: {resolutions}")

    print(f"    Successfully fetched DEM")

    # Process DEM
    with MemoryFile(tif_bytes) as memfile:
        with memfile.open() as src:
            elevation = src.read(1)
            bounds = src.bounds
            transform = src.transform

            valid = elevation[elevation != -9999]
            if len(valid) == 0:
                raise RuntimeError("No valid elevation data in requested area")

            vmin, vmax = float(np.min(valid)), float(np.max(valid))
            print(f"    Elevation: {vmin:.1f}m to {vmax:.1f}m")
            print(f"    Dimensions: {elevation.shape[1]}x{elevation.shape[0]}")

            # Calculate slope and aspect
            print(f"    Calculating slope and aspect...")
            slope_deg, aspect_deg = calculate_slope_aspect(elevation, transform, bounds)

            slope_clean = slope_deg[~np.isnan(slope_deg)]
            aspect_clean = aspect_deg[~np.isnan(aspect_deg)]

            print(f"    Slope: {np.min(slope_clean):.1f}° to {np.max(slope_clean):.1f}° (mean: {np.mean(slope_clean):.1f}°)")
            if len(aspect_clean) > 0:
                print(f"    Aspect: {np.min(aspect_clean):.1f}° to {np.max(aspect_clean):.1f}° (mean: {np.mean(aspect_clean):.1f}°)")

            # Save GeoTIFFs
            print(f"    Saving GeoTIFFs...")

            # Elevation
            elev_path = output_dir / f"{field_id}_elevation.tif"
            save_float_geotiff(elev_path, elevation.astype(np.float32), transform)

            # Slope
            slope_path = output_dir / f"{field_id}_slope.tif"
            save_float_geotiff(slope_path, slope_deg, transform)

            # Aspect
            aspect_path = output_dir / f"{field_id}_aspect.tif"
            save_float_geotiff(aspect_path, aspect_deg, transform)

            return {
                'elevation': str(elev_path),
                'slope': str(slope_path),
                'aspect': str(aspect_path),
                'bounds': [bounds.left, bounds.bottom, bounds.right, bounds.top],
                'elevation_range': [vmin, vmax],
                'slope_range': [float(np.min(slope_clean)), float(np.max(slope_clean))],
                'aspect_range': [float(np.min(aspect_clean)), float(np.max(aspect_clean))] if len(aspect_clean) > 0 else [0, 360],
                'resolution': resolutions[res_idx - 1] if res_idx > 0 else target_res_m,
            }


def main():
    parser = argparse.ArgumentParser(
        description="Generate DEM, Slope, and Aspect rasters from lat/lon polygon coordinates"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Polygon as GeoJSON string, simple [lon,lat] list, or path to .geojson file",
    )
    parser.add_argument(
        "--output-dir",
        default="terrain_rasters",
        help="Output directory (default: terrain_rasters)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=5,
        help="Target resolution in meters (default: 5)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.15,
        help="Padding around polygon bounds as fraction (default: 0.15 = 15%%)",
    )
    parser.add_argument(
        "--field-id",
        default=None,
        help="Field ID for output filenames (default: auto-generated)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Terrain Raster Generation (DEM, Slope, Aspect)")
    print("=" * 60)
    print(f"Input: {args.input[:100]}{'...' if len(args.input) > 100 else ''}")
    print(f"Output: {args.output_dir}")
    print(f"Resolution: {args.resolution}m")
    print(f"Padding: {args.padding * 100:.0f}%")
    print("-" * 60)

    try:
        # Parse input
        print("Parsing input polygon...")
        polygon_data = parse_polygon_input(args.input)
        bounds = polygon_data['bounds']
        print(f"  Bounds: {bounds[0]:.6f}, {bounds[1]:.6f} to {bounds[2]:.6f}, {bounds[3]:.6f}")

        # Generate rasters
        result = generate_terrain_rasters(
            polygon_data,
            args.output_dir,
            target_res_m=args.resolution,
            padding=args.padding,
            field_id=args.field_id,
        )

        print("-" * 60)
        print("Generated files:")
        print(f"  Elevation: {result['elevation']}")
        print(f"  Slope: {result['slope']}")
        print(f"  Aspect: {result['aspect']}")
        print(f"\nActual resolution used: {result['resolution']}m")
        print("=" * 60)
        print("Done!")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
