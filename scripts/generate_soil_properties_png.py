#!/usr/bin/env python3
"""
Generate PNG versions of soil property TIFFs with colormaps for web display.

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
    "cec": ("plasma", None, None),
    "awc": ("Blues", None, None),
    "ph": ("RdYlBu_r", None, None),
    "sand_pct": ("viridis", None, None),
    "silt_pct": ("viridis", None, None),
    "clay_pct": ("YlOrBr", None, None),
    "om_pct": ("YlOrBr", None, None),
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
            clipped, transform = mask(src, [field_geometry], crop=True, all_touched=True)
            data = clipped[0]
        except Exception as e:
            print(f"    Warning: Could not mask {tiff_path.name}: {e}")
            return None

        valid = data[~np.isnan(data)]
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
    TIFF_DIR = Path("data/soil_properties")
    PNG_DIR = Path("data/soil_properties_pngs")
    FIELD_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")
    STATS_JSON = Path("data/soil_properties_pngs/soil_properties_statistics.json")

    PNG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading field boundaries from {FIELD_GEOJSON}...")
    gdf = gpd.read_file(FIELD_GEOJSON)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    field_ids = sorted(gdf["field_id"].unique())
    print(f"  Found {len(field_ids)} fields")

    all_stats = {}

    properties = list(COLORMAPS.keys())

    for field_id in field_ids:
        all_stats[field_id] = {}
        field_geom = get_field_geometry(field_id, gdf)

        for prop in properties:
            tiff_path = TIFF_DIR / f"{field_id}_soil_{prop}.tif"

            if not tiff_path.exists():
                continue

            cmap_name, vmin_default, vmax_default = COLORMAPS[prop]

            with rasterio.open(tiff_path) as src:
                data = src.read(1)
                height, width = data.shape

                rgb, vmin, vmax = apply_colormap(data, cmap_name, vmin_default, vmax_default)

                if rgb is None:
                    print(f"  Skipping {tiff_path.name}: no valid data")
                    continue

                output_png = PNG_DIR / f"{field_id}_{prop}.png"
                img = Image.fromarray(rgb, mode="RGB")
                img.save(output_png)

            stats = calculate_field_statistics(tiff_path, field_geom)
            if stats:
                all_stats[field_id][prop] = stats

            valid = data[~np.isnan(data)]
            valid_count = len(valid)
            print(f"  {output_png.name}: {width}x{height}, range {vmin:.4f} to {vmax:.4f} ({valid_count} pixels)")

    with open(STATS_JSON, "w") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\nStatistics saved to {STATS_JSON}")

    print("Done!")


if __name__ == "__main__":
    main()
