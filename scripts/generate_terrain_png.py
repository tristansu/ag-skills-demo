#!/usr/bin/env python3
"""
Generate PNG versions of terrain TIFFs (elevation, slope, aspect) with colormaps.

Also generates a JSON file with per-field polygon statistics for colorbar scaling.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from matplotlib import cm
from PIL import Image
from rasterio.mask import mask

COLORMAPS = {
    "elevation": ("inferno", None, None),
    "slope": ("YlOrRd", None, None),
    "aspect": ("hsv", 0, 360),
}


def apply_colormap(data, cmap_name, vmin=None, vmax=None):
    """Apply colormap to normalized data."""
    if vmin is None:
        valid = data[~np.isnan(data)]
        if len(valid) == 0:
            return None, None, None
        vmin, vmax = float(np.min(valid)), float(np.max(valid))

    data_normalized = np.clip((data - vmin) / (vmax - vmin + 0.001), 0, 1)
    cmap = cm.get_cmap(cmap_name, 256)
    colored = cmap(data_normalized)
    rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    return rgb, vmin, vmax


def get_field_geometry(field_id, gdf):
    """Get the geometry for a specific field."""
    field = gdf[gdf["field_id"] == field_id]
    if len(field) == 0:
        return None
    return field.iloc[0].geometry


def calculate_field_statistics(tiff_path, field_geometry):
    """Calculate statistics for pixels within the field polygon."""
    with rasterio.open(tiff_path) as src:
        try:
            nodata = src.nodata
            clipped, transform = mask(src, [field_geometry], crop=True, all_touched=True)
            data = clipped[0]
        except Exception as e:
            print(f"    Warning: Could not mask {tiff_path.name}: {e}")
            return None

        valid = data[~np.isnan(data)]
        if nodata is not None and not np.isnan(nodata):
            valid = valid[valid != nodata]
        if len(valid) == 0:
            return None

        return {
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "avg": float(np.mean(valid)),
            "std": float(np.std(valid)),
            "pixel_count": int(len(valid)),
        }


def main():
    TIFF_DIR = Path("data/terrain")
    PNG_DIR = Path("data/terrain_pngs")
    FIELD_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")
    STATS_JSON = Path("data/terrain_pngs/terrain_statistics.json")

    PNG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading field boundaries from {FIELD_GEOJSON}...")
    gdf = gpd.read_file(FIELD_GEOJSON)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    field_ids = sorted(gdf["field_id"].unique())
    print(f"  Found {len(field_ids)} fields")

    all_stats = {}

    tif_files = list(TIFF_DIR.glob("*_elevation.tif")) + list(TIFF_DIR.glob("*_slope.tif")) + list(TIFF_DIR.glob("*_aspect.tif"))
    print(f"Processing {len(tif_files)} terrain TIFF files...")

    metrics = ["elevation", "slope", "aspect"]

    for field_id in field_ids:
        all_stats[field_id] = {}
        field_geom = get_field_geometry(field_id, gdf)

        for metric in metrics:
            tiff_path = TIFF_DIR / f"{field_id}_{metric}.tif"

            if not tiff_path.exists():
                continue

            cmap_name, vmin_default, vmax_default = COLORMAPS[metric]

            with rasterio.open(tiff_path) as src:
                data = src.read(1)
                height, width = data.shape

                rgb, vmin, vmax = apply_colormap(data, cmap_name, vmin_default, vmax_default)

                if rgb is None:
                    print(f"  Skipping {tiff_path.name}: no valid data")
                    continue

                output_png = PNG_DIR / f"{field_id}_{metric}.png"
                img = Image.fromarray(rgb, mode="RGB")
                img.save(output_png)

            stats = calculate_field_statistics(tiff_path, field_geom)
            if stats:
                all_stats[field_id][metric] = stats

            valid = data[~np.isnan(data)]
            valid_count = len(valid)
            print(f"  {output_png.name}: {width}x{height}, range {vmin:.1f} to {vmax:.1f} ({valid_count} pixels)")

    with open(STATS_JSON, "w") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\nStatistics saved to {STATS_JSON}")

    print("Done!")


if __name__ == "__main__":
    main()
