#!/usr/bin/env python3
"""
Generate spatially varying soil property rasters from soil label TIFs.

This script:
1. Reads existing soil label TIFs (integer mukey labels) and their JSON definitions
2. Converts them to float32 TIFs with actual property values (pH, OM%, clay%, sand%, CEC)
3. Saves to docs/assignment-03/soil_properties/

Input:
    data/assignment-04/soil/{field_id}_soil.tif (integer labels)
    data/assignment-04/soil/{field_id}_soil_labels.json (property definitions)

Output:
    docs/assignment-03/soil_properties/{field_id}_soil_{property}.tif (float32)
"""

import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

SOIL_INPUT_DIR = Path("data/soil")
OUTPUT_DIR = Path("data/soil_properties")
FIELD_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")

PROPERTIES = {
    "ph": "ph",
    "om_pct": "om_pct",
    "clay_pct": "clay_pct",
    "sand_pct": "sand_pct",
    "silt_pct": "silt_pct",
    "cec": "cec",
    "awc": "awc",
}


def generate_property_raster(field_id, property_key, property_column):
    """Generate a single property raster for one field."""
    soil_tiff_path = SOIL_INPUT_DIR / f"{field_id}_soil.tif"
    labels_json_path = SOIL_INPUT_DIR / f"{field_id}_soil_labels.json"
    output_path = OUTPUT_DIR / f"{field_id}_soil_{property_key}.tif"

    if not soil_tiff_path.exists():
        print(f"  SKIP: Soil TIF not found: {soil_tiff_path}")
        return False

    if not labels_json_path.exists():
        print(f"  SKIP: Labels JSON not found: {labels_json_path}")
        return False

    with open(labels_json_path) as f:
        labels = json.load(f)

    label_to_mukey = labels.get("label_to_mukey", {})
    soil_defs = labels.get("soil_definitions", {})

    label_to_value = {}
    for label_id, mukey_str in label_to_mukey.items():
        soil_def = soil_defs.get(label_id, {})
        value = soil_def.get(property_column)
        if value is not None:
            try:
                label_to_value[int(label_id)] = float(value)
            except (ValueError, TypeError):
                pass

    if not label_to_value:
        print(f"  SKIP: No property values found for {property_key}")
        return False

    with rasterio.open(soil_tiff_path) as src:
        data = src.read(1)
        profile = src.profile.copy()

    output = np.full_like(data, np.nan, dtype=np.float64)
    for label_id, value in label_to_value.items():
        output[data == label_id] = value

    output_clean = np.where(np.isnan(output), np.nan, output).astype(np.float32)

    profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=np.nan,
        compress="lzw",
    )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(output_clean, 1)

    return True


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading fields from {FIELD_GEOJSON}...")
    gdf = gpd.read_file(FIELD_GEOJSON)
    field_ids = sorted(gdf["field_id"].unique())
    print(f"  Found {len(field_ids)} fields")

    total = len(field_ids) * len(PROPERTIES)
    current = 0
    success = 0
    errors = 0

    print(f"\nGenerating {len(PROPERTIES)} property rasters for {len(field_ids)} fields...")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    for field_id in field_ids:
        for property_key, property_column in PROPERTIES.items():
            current += 1
            print(f"[{current}/{total}] {field_id} - {property_key}...", end=" ")

            try:
                result = generate_property_raster(field_id, property_key, property_column)
                if result:
                    print("OK")
                    success += 1
                else:
                    errors += 1
            except Exception as e:
                print(f"ERROR: {e}")
                errors += 1

    print("-" * 60)
    print(f"\n=== Summary ===")
    print(f"Total: {total}")
    print(f"Success: {success}")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()
