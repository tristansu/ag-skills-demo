#!/usr/bin/env python3
"""
Generate DEM PNGs for each field with correct bounds matching the web map display.

Uses USGS 3DEP to fetch elevation and saves as PNG with inferno colormap.
Output matches the 20% padding used in field_map_7.html getFieldBoundsWithPadding().
"""

import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from matplotlib import cm
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

INPUT_GEOJSON = Path("docs/assignment-03/fields_complete_wgs84.geojson")
OUTPUT_DIR = Path("docs/assignment-03/dem")
OUTPUT_DIR.mkdir(exist_ok=True)
BOUNDS_FILE = OUTPUT_DIR / "dem_bounds.json"

USGS_3DEP_EXPORT = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
)

TARGET_RES_M = 10


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
    """Fetch elevation from USGS 3DEP."""
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


def apply_inferno_colormap(dem_array, vmin, vmax):
    """Apply inferno colormap to elevation array."""
    valid_mask = ~np.isnan(dem_array) & (dem_array != -9999)
    if not np.any(valid_mask):
        return None

    normalized = dem_array.copy()
    normalized[valid_mask] = (normalized[valid_mask] - vmin) / (vmax - vmin + 0.001)
    normalized[valid_mask] = np.clip(normalized[valid_mask], 0, 1)

    inferno = cm.get_cmap("inferno", 256)
    colored = inferno(normalized)

    rgb = np.zeros((colored.shape[0], colored.shape[1], 3), dtype=np.uint8)
    rgb[:, :, 0] = (colored[:, :, 0] * 255).astype(np.uint8)
    rgb[:, :, 1] = (colored[:, :, 1] * 255).astype(np.uint8)
    rgb[:, :, 2] = (colored[:, :, 2] * 255).astype(np.uint8)

    rgb[~valid_mask] = [0, 0, 0]

    return rgb


def process_field(field_id, field_bounds_wgs84, target_res_m=TARGET_RES_M):
    """Process a single field: fetch, colorize, save as PNG."""

    dx = (field_bounds_wgs84[2] - field_bounds_wgs84[0]) * 0.2
    dy = (field_bounds_wgs84[3] - field_bounds_wgs84[1]) * 0.2
    padded_bbox = (
        field_bounds_wgs84[0] - dx,
        field_bounds_wgs84[1] - dy,
        field_bounds_wgs84[2] + dx,
        field_bounds_wgs84[3] + dy,
    )

    minx, miny, maxx, maxy = padded_bbox
    mid_lat = (miny + maxy) / 2

    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(mid_lat))))

    res_deg = target_res_m * deg_per_m_lon
    lon_range = maxx - minx
    lat_range = maxy - miny

    width = max(64, int(math.ceil(lon_range / res_deg)))
    height = max(64, int(math.ceil(lat_range / res_deg)))

    print(f"    Fetching USGS 3DEP at {target_res_m}m (target: {width}x{height})...")
    tif_bytes = fetch_usgs_elevation_preserving_aspect(padded_bbox, width, height)

    if tif_bytes is None and target_res_m == 5:
        print(f"    5m failed, trying 10m...")
        tif_bytes = fetch_usgs_elevation(padded_bbox, 10)

    if tif_bytes is None:
        print(f"    Failed to fetch elevation")
        return None

    try:
        with MemoryFile(tif_bytes) as memfile:
            with memfile.open() as src:
                dem = src.read(1)
                bounds = src.bounds

                valid = dem[dem != -9999]
                if len(valid) == 0:
                    print(f"    No valid elevation data")
                    return None

                vmin, vmax = float(np.min(valid)), float(np.max(valid))
                print(f"    Elevation: {vmin:.1f}m to {vmax:.1f}m")
                print(f"    DEM dimensions: {dem.shape[1]}x{dem.shape[0]}")

                colored = apply_inferno_colormap(dem, vmin, vmax)
                if colored is None:
                    return None

                output_path = OUTPUT_DIR / f"dem_{field_id}.png"

                from PIL import Image
                img = Image.fromarray(colored, mode="RGB")
                img.save(output_path)

                print(f"    Saved: {output_path}")
                return {
                    "vmin": vmin,
                    "vmax": vmax,
                    "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top]
                }

    except Exception as e:
        print(f"    Error processing: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print(f"Loading {INPUT_GEOJSON}...")
    gdf = gpd.read_file(INPUT_GEOJSON)

    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf_wgs84 = gdf.to_crs("EPSG:4326")
    else:
        gdf_wgs84 = gdf

    print(f"Processing {len(gdf_wgs84)} fields...")

    success = 0
    errors = 0
    skipped = 0
    dem_bounds = {}

    for idx, (_, field) in enumerate(gdf_wgs84.iterrows()):
        field_id = field["field_id"]

        existing_png = OUTPUT_DIR / f"dem_{field_id}.png"
        if existing_png.exists():
            print(f"  [{idx + 1}/{len(gdf_wgs84)}] {field_id} - already exists, skipping")
            skipped += 1
            continue

        bounds = gdf_wgs84.geometry.iloc[idx].bounds
        print(f"  [{idx + 1}/{len(gdf_wgs84)}] {field_id}...")

        result = process_field(field_id, bounds, target_res_m=TARGET_RES_M)

        if result:
            success += 1
            if 'bounds' in result:
                dem_bounds[field_id] = result['bounds']
        else:
            errors += 1

    with open(BOUNDS_FILE, 'w') as f:
        json.dump(dem_bounds, f, indent=2)

    print("\n=== Summary ===")
    print(f"Success: {success}, Errors: {errors}, Skipped: {skipped}")
    print(f"PNGs saved to: {OUTPUT_DIR}")
    print(f"Bounds saved to: {BOUNDS_FILE}")
    print("Done!")


if __name__ == "__main__":
    main()
