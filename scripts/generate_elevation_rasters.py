#!/usr/bin/env python3
"""
Generate per-field elevation rasters with inferno colormap.

Uses USGS 3DEP to fetch elevation for each field at 5m/10m,
and saves as GeoTIFF with inferno colormap.
"""

import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from matplotlib import cm
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

INPUT_GEOJSON = Path("data/assignment-02/fields_complete_elevation.geojson")
OUTPUT_DIR = Path("data/assignment-02/elevation")
OUTPUT_DIR.mkdir(exist_ok=True)

USGS_3DEP_EXPORT = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
)


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
    except Exception:
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


def process_field(field_id, field_bounds_wgs84, target_res_m=5):
    """Process a single field: fetch, get stats, colorize, save."""

    # Add 20% padding
    dx = (field_bounds_wgs84[2] - field_bounds_wgs84[0]) * 0.2
    dy = (field_bounds_wgs84[3] - field_bounds_wgs84[1]) * 0.2
    padded_bbox = (
        field_bounds_wgs84[0] - dx,
        field_bounds_wgs84[1] - dy,
        field_bounds_wgs84[2] + dx,
        field_bounds_wgs84[3] + dy,
    )

    print(f"    Fetching USGS 3DEP at {target_res_m}m...")
    tif_bytes = fetch_usgs_elevation(padded_bbox, target_res_m)

    if tif_bytes is None and target_res_m == 5:
        print("    5m failed, trying 10m...")
        tif_bytes = fetch_usgs_elevation(padded_bbox, 10)

    if tif_bytes is None:
        print("    Failed to fetch elevation")
        return None

    try:
        with MemoryFile(tif_bytes) as memfile:
            with memfile.open() as src:
                dem = src.read(1)
                bounds = src.bounds  # left, bottom, right, top

                # Get elevation statistics from the entire DEM
                valid = dem[dem != -9999]
                if len(valid) == 0:
                    print("    No valid elevation data")
                    return None

                vmin, vmax = float(np.min(valid)), float(np.max(valid))
                print(f"    Elevation: {vmin:.1f}m to {vmax:.1f}m")

                # Apply inferno colormap
                colored = apply_inferno_colormap(dem, vmin, vmax)

                if colored is None:
                    return None

                # Create transform for the DEM
                out_transform = from_bounds(
                    bounds[0], bounds[1], bounds[2], bounds[3], colored.shape[1], colored.shape[0]
                )

                # Save RGB GeoTIFF in EPSG:4326
                output_path = OUTPUT_DIR / f"{field_id}_inferno.tif"

                profile = {
                    "driver": "GTiff",
                    "height": colored.shape[0],
                    "width": colored.shape[1],
                    "count": 3,
                    "dtype": "uint8",
                    "transform": out_transform,
                    "crs": "EPSG:4326",
                }

                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(colored[:, :, 0], 1)
                    dst.write(colored[:, :, 1], 2)
                    dst.write(colored[:, :, 2], 3)

                print(f"    Saved: {output_path}")
                return {"vmin": vmin, "vmax": vmax}

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

    print(f"Processing {len(gdf)} fields...")

    success = 0
    errors = 0

    for idx, (_, field) in enumerate(gdf.iterrows()):
        field_id = field["field_id"]
        bounds = gdf_wgs84.geometry.iloc[idx].bounds

        print(f"  [{idx + 1}/{len(gdf)}] {field_id}...")

        result = process_field(field_id, bounds, target_res_m=5)

        if result:
            success += 1
        else:
            errors += 1

    print("\n=== Summary ===")
    print(f"Success: {success}, Errors: {errors}")
    print(f"Rasters saved to: {OUTPUT_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()
