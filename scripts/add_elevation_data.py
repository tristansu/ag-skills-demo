#!/usr/bin/env python3
"""
Add elevation data to fields_complete.geojson

Uses AWS Terrain Tiles to get elevation for each field.

Output:
- fields_complete_elevation.geojson (with elevation stats)
- data/assignment-02/elevation/*_stats.json (statistics)
"""

import json
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import mercantile
import numpy as np
import requests
from PIL import Image

INPUT_GEOJSON = Path("data/assignment-02/fields_complete.geojson")
OUTPUT_GEOJSON = Path("data/assignment-02/fields_complete_elevation.geojson")
ELEVATION_DIR = Path("data/assignment-02/elevation")
ZOOM = 14  # ~10m resolution


def get_field_elevation(bounds, zoom=14):
    """Get elevation data for a field's bounding box."""

    # Get tile for field center
    cx = (bounds[0] + bounds[2]) / 2
    cy = (bounds[1] + bounds[3]) / 2

    tile = mercantile.tile(cx, cy, zoom)

    # Get tile bounds
    tile_bounds = mercantile.bounds(tile)

    # Fetch tile
    url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{zoom}/{tile.x}/{tile.y}.png"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        return None

    img = Image.open(BytesIO(resp.content))
    arr = np.array(img, dtype=np.float32)
    elevation = (arr[:, :, 0] * 256 + arr[:, :, 1] + arr[:, :, 2] / 256.0) - 32768

    # Convert field bounds to pixel coordinates
    px_min = max(
        0, int((bounds[0] - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * 256)
    )
    px_max = min(
        256, int((bounds[2] - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * 256)
    )
    py_min = max(
        0, int((tile_bounds.north - bounds[3]) / (tile_bounds.north - tile_bounds.south) * 256)
    )
    py_max = min(
        256, int((tile_bounds.north - bounds[1]) / (tile_bounds.north - tile_bounds.south) * 256)
    )

    if px_max > px_min and py_max > py_min:
        return elevation[py_min:py_max, px_min:px_max]
    return None


def process_fields():
    ELEVATION_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {INPUT_GEOJSON}...")
    gdf = gpd.read_file(INPUT_GEOJSON)
    gdf_wgs84 = gdf.to_crs("EPSG:4326")

    # Add elevation columns
    for col in [
        "elevation_min_m",
        "elevation_max_m",
        "elevation_mean_m",
        "elevation_std_m",
        "elevation_range_m",
        "elevation_raster",
    ]:
        gdf[col] = None

    success = 0
    errors = 0

    for idx, (orig_idx, field) in enumerate(gdf.iterrows()):
        field_id = field["field_id"]
        field_wgs = gdf_wgs84.loc[orig_idx]
        bounds = field_wgs.geometry.bounds

        print(f"  [{idx + 1}/{len(gdf)}] {field_id}...")

        try:
            # Get elevation grid for the field area
            clipped = get_field_elevation(bounds, ZOOM)
            if clipped is None:
                print("    Could not fetch tiles")
                errors += 1
                continue

            valid = clipped[~np.isnan(clipped)]

            if len(valid) == 0:
                print("    No valid elevation data")
                errors += 1
                continue

            # Calculate stats
            stats = {
                "elevation_min_m": float(np.min(valid)),
                "elevation_max_m": float(np.max(valid)),
                "elevation_mean_m": float(np.mean(valid)),
                "elevation_std_m": float(np.std(valid)),
                "elevation_range_m": float(np.max(valid) - np.min(valid)),
            }

            print(f"    Stats: {stats['elevation_min_m']:.1f}m - {stats['elevation_max_m']:.1f}m")

            # Save stats
            stats_path = ELEVATION_DIR / f"{field_id}_stats.json"
            with open(stats_path, "w") as f:
                json.dump(stats, f, indent=2)

            # Update GeoDataFrame
            for key, value in stats.items():
                gdf.at[orig_idx, key] = value

            # For now, store stats reference instead of raster path
            gdf.at[orig_idx, "elevation_raster"] = f"elevation/{field_id}_stats.json"

            success += 1

        except Exception as e:
            print(f"    Error: {e}")
            errors += 1
            continue

    print(f"\nSaving {OUTPUT_GEOJSON}...")
    gdf.to_file(OUTPUT_GEOJSON, driver="GeoJSON")

    print("\n=== Summary ===")
    print(f"Success: {success}, Errors: {errors}")
    print("Done!")


if __name__ == "__main__":
    process_fields()
