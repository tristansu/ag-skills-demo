#!/usr/bin/env python3
"""Generate PNG versions of satellite TIFFs with colormaps for web display.

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
PNG_DIR = Path("data/satellite_pngs")
FIELD_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")
STATS_JSON = Path("data/satellite_pngs/satellite_statistics.json")

COLORMAPS = {
    "ndvi": ("viridis", -0.2, 1.0),
    "msavi": ("plasma", -0.2, 1.0),
    "evi": ("magma", -0.2, 1.0),
    "ndmi": ("Blues_r", -0.5, 0.6),
}


def apply_colormap(data, cmap_name, vmin, vmax):
    """Apply colormap to normalized data."""
    data_normalized = np.clip((data - vmin) / (vmax - vmin), 0, 1)
    cmap = cm.get_cmap(cmap_name)
    colored = cmap(data_normalized)
    rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    return rgb


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
    TIFF_DIR = Path("data/satellite")
    PNG_DIR = Path("data/satellite_pngs")
    FIELD_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")
    STATS_JSON = Path("data/satellite_pngs/satellite_statistics.json")

    PNG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading field boundaries from {FIELD_GEOJSON}...")
    gdf = gpd.read_file(FIELD_GEOJSON)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    field_ids = sorted(gdf["field_id"].unique())
    print(f"  Found {len(field_ids)} fields")

    all_stats = {}

    tiff_files = list(TIFF_DIR.glob("*.tif"))
    print(f"Processing {len(tiff_files)} TIFF files...")

    metrics = list(COLORMAPS.keys())

    for field_id in field_ids:
        all_stats[field_id] = {}
        field_geom = get_field_geometry(field_id, gdf)

        for metric in metrics:
            tiff_path = TIFF_DIR / f"{field_id}_{metric}.tif"

            if not tiff_path.exists():
                continue

            cmap_name, vmin, vmax = COLORMAPS[metric]

            with rasterio.open(tiff_path) as src:
                data = src.read(1)
                height, width = data.shape

                rgb = apply_colormap(data, cmap_name, vmin, vmax)

                alpha = ~np.isnan(data)
                rgba = np.zeros((height, width, 4), dtype=np.uint8)
                rgba[:, :, :3] = rgb
                rgba[:, :, 3] = (alpha * 255).astype(np.uint8)

                output_path = PNG_DIR / f"{field_id}_{metric}.png"
                img = Image.fromarray(rgba, mode="RGBA")
                img.save(output_path)

            stats = calculate_field_statistics(tiff_path, field_geom)
            if stats:
                all_stats[field_id][metric] = stats

            valid = data[~np.isnan(data)]
            print(f"  {output_path.name}: {width}x{height}, range {valid.min():.3f} to {valid.max():.3f}")

    with open(STATS_JSON, "w") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\nStatistics saved to {STATS_JSON}")

    print("Done!")


if __name__ == "__main__":
    main()
