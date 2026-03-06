#!/usr/bin/env python3
"""
Get CDL Crop Data for Oregon Willamette Valley Fields.

This script:
1. Downloads CDL 2024 raster for Oregon (if not present)
2. Extracts crop data for each field polygon
3. Maps CDL codes to crop names
4. Saves to CSV

Usage:
    python scripts/get_cdl_crops.py

Output:
    data/assignment-02/cdl_oregon_willamette_2025.csv

Requirements:
    geopandas, rasterio, pandas
"""

import subprocess
import sys
from pathlib import Path

# Configuration
CDL_URL = "https://nassgeodata.gmu.edu/nass_data_cache/byfips/CDL_2024_41.tif"
CDL_PATH = "/tmp/CDL_2024_41.tif"
FIELDS_PATH = "data/assignment-02/fields_oregon_willamette_ag_2025.geojson"
OUTPUT_PATH = "data/assignment-02/cdl_oregon_willamette_ag_2025.csv"

# CDL code mapping
CDL_CODES = {
    0: "No Data",
    1: "Corn",
    5: "Soybeans",
    24: "Winter Wheat",
    27: "Spring Wheat",
    28: "Grass",
    36: "Alfalfa",
    37: "Other Hay",
    38: "Small Grains",
    42: "Forest",
    43: "Fallow/Idle",
    59: "Grass/Pasture",
    61: "Fallow/Idle",
    74: "Horticulture",
    75: "Berries",
    121: "Developed/Open Space",
    122: "Developed/Low Intensity",
    141: "Deciduous Forest",
    142: "Evergreen Forest",
    143: "Mixed Forest",
    152: "Shrubland",
    176: "Grassland/Herbaceous",
    190: "Woody Wetlands",
    195: "Herbaceous Wetlands",
    204: "Christmas Trees",
    205: "Other",
    206: "Other",
    207: "Forest",
    208: "Forest",
    209: "Mixed Forest",
    210: "Developed",
    211: "Open Water",
    212: "No Data",
    213: "Developed",
    214: "Wetlands",
    215: "Nonag",
    216: "Shrubland",
    222: "Clouds",
}


def install_deps():
    """Install required packages."""
    packages = ["geopandas", "rasterio", "pandas", "shapely"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def download_cdl():
    """Download CDL 2024 raster for Oregon."""
    if Path(CDL_PATH).exists():
        print(f"CDL already exists at {CDL_PATH}")
        return

    print(f"Downloading CDL from {CDL_URL}...")
    result = subprocess.run(
        ["curl", "-L", "-o", CDL_PATH, CDL_URL, "--max-time", "600"], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Download failed: {result.stderr}")
        sys.exit(1)

    print(f"Downloaded to {CDL_PATH}")


def get_cdl_crops():
    """Extract CDL crop data for each field."""
    try:
        from collections import Counter

        import geopandas as gpd
        import rasterio
        from rasterio.mask import mask
    except ImportError:
        install_deps()
        from collections import Counter

        import geopandas as gpd
        import rasterio
        from rasterio.mask import mask

    # Load fields
    if not Path(FIELDS_PATH).exists():
        print(f"Fields not found at {FIELDS_PATH}")
        print("Run scripts/get_field_boundaries.py first")
        sys.exit(1)

    fields = gpd.read_file(FIELDS_PATH)
    print(f"Loaded {len(fields)} fields")

    # Download CDL if needed
    if not Path(CDL_PATH).exists():
        download_cdl()

    # Extract CDL data for each field
    print("Extracting CDL crop data...")

    results = []
    with rasterio.open(CDL_PATH) as src:
        for idx, field in fields.iterrows():
            try:
                out_image, _ = mask(src, [field.geometry], crop=True)
                pixels = out_image[0]
                valid = pixels[pixels > 0]

                if len(valid) > 0:
                    counts = Counter(valid.flat)
                    dominant_code = counts.most_common(1)[0][0]
                    dominant_pct = counts[dominant_code] / len(valid) * 100
                else:
                    dominant_code = 0
                    dominant_pct = 0.0

                results.append(
                    {
                        "field_id": field["field_id"],
                        "crop_code": int(dominant_code),
                        "dominant_pct": round(dominant_pct, 1),
                    }
                )
            except Exception:
                results.append(
                    {
                        "field_id": field["field_id"],
                        "crop_code": 0,
                        "dominant_pct": 0.0,
                    }
                )

    # Create DataFrame
    import pandas as pd

    df = pd.DataFrame(results)

    # Map crop codes to names
    df["cdl_crop"] = df["crop_code"].map(CDL_CODES).fillna(f"Code_{df['crop_code']}")

    # Save
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(df)} records to {OUTPUT_PATH}")
    return df


def main():
    """Main entry point."""
    print("=" * 60)
    print("CDL Crop Data Extraction")
    print("=" * 60)

    df = get_cdl_crops()

    print("\nCrop distribution:")
    print(df["cdl_crop"].value_counts())

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
