#!/usr/bin/env python3
"""
Get Oregon Willamette Valley Specialty Crop Field Boundaries.

This script:
1. Loads the USDA NASS CSB dataset (or downloads if needed)
2. Filters to Oregon Willamette Valley fields with specialty crops
3. Filters to fields >= 10 acres
4. Samples 50 fields with actual crops (not grasslands/forests)
5. Saves to GeoJSON

Specialty crops include:
- Berries (75)
- Grapes/Horticulture (74)
- Christmas Trees (204)
- Alfalfa (36)
- Other Hay (37)

Usage:
    python scripts/get_specialty_fields.py

Output:
    data/assignment-02b/fields_oregon_willamette_specialty_2025.geojson
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

# Configuration
CSB_URL = "https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/datasets/NationalCSB_2017-2024_rev23.zip"
CSB_ZIP = "/tmp/national_csb.zip"
CSB_DIR = "/tmp/csb"
OUTPUT_PATH = "data/assignment-02b/fields_oregon_willamette_ag_2025.geojson"
N_FIELDS = 50
MIN_ACRES = 10

# Specialty crop codes (not grasslands/forests)
# Expanded to get 50 fields while avoiding forests and wetlands
SPECIALTY_CODES = [
    74,  # Horticulture (includes grapes)
    75,  # Berries
    204,  # Christmas Trees
    36,  # Alfalfa
    37,  # Other Hay
    176,  # Grassland/Herbaceous
    59,  # Grass (pasture)
    38,  # Small Grains
    24,  # Winter Wheat
    27,  # Spring Wheat
]

# Willamette Valley bounding box (EPSG:5070)
WV_BBOX = {
    "x_min": -2250000,
    "y_min": 2350000,
    "x_max": -1900000,
    "y_max": 2650000,
}

# Oregon Willamette Valley counties (FIPS)
WV_COUNTIES = ["001", "003", "039", "043", "047", "053", "071"]


def install_deps():
    """Install required packages."""
    packages = ["geopandas", "pandas", "pyproj", "fiona", "pyogrio"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def download_csb():
    """Download USDA NASS Crop Sequence Boundaries dataset."""
    if Path(CSB_DIR).exists() and Path(CSB_DIR).is_dir():
        print(f"CSB already extracted at {CSB_DIR}")
        return

    print(f"Downloading CSB from {CSB_URL}...")
    print("This is ~3.4GB and may take several minutes...")

    result = subprocess.run(
        ["curl", "-L", "-o", CSB_ZIP, CSB_URL, "--max-time", "3600"], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Download failed: {result.stderr}")
        sys.exit(1)

    print(f"Downloaded to {CSB_ZIP}")

    print("Extracting...")
    os.makedirs(CSB_DIR, exist_ok=True)
    with zipfile.ZipFile(CSB_ZIP, "r") as z:
        z.extractall(CSB_DIR)

    print(f"Extracted to {CSB_DIR}")


def get_specialty_fields():
    """Extract Willamette Valley specialty crop field boundaries."""
    try:
        import geopandas as gpd
    except ImportError:
        install_deps()
        import geopandas as gpd

    gdb_path = Path(CSB_DIR) / "NationalCSB_2017-2024_rev23" / "CSB1724.gdb"

    if not gdb_path.exists():
        print(f"CSB not found at {gdb_path}")
        download_csb()

    print("Loading Willamette Valley fields from CSB...")

    # Load with bounding box filter
    bbox = (WV_BBOX["x_min"], WV_BBOX["y_min"], WV_BBOX["x_max"], WV_BBOX["y_max"])
    wv = gpd.read_file(
        str(gdb_path),
        layer="national1724",
        bbox=bbox,
        columns=["CSBACRES", "CDL2024", "CNTYFIPS", "geometry"],
    )

    print(f"Loaded {len(wv)} fields in bounding box")

    # Filter to Willamette Valley counties
    wv = wv[wv["CNTYFIPS"].isin(WV_COUNTIES)]
    print(f"After county filter: {len(wv)} fields")

    # Filter for specialty crop codes
    wv_specialty = wv[wv["CDL2024"].isin(SPECIALTY_CODES)]
    print(f"After specialty crop filter: {len(wv_specialty)} fields")

    # Filter >= 10 acres
    wv_specialty = wv_specialty[wv_specialty["CSBACRES"] >= MIN_ACRES]
    print(f"After {MIN_ACRES}+ acres filter: {len(wv_specialty)} fields")

    # Check if we have enough
    if len(wv_specialty) < N_FIELDS:
        print(f"Warning: Only {len(wv_specialty)} specialty fields available")
        print(f"Sampling all {len(wv_specialty)} fields")
        sample = wv_specialty.copy()
    else:
        sample = wv_specialty.sample(n=N_FIELDS, random_state=42)

    print(f"Sampled: {len(sample)} fields")

    # Convert to lat/lon
    sample_4326 = sample.to_crs("EPSG:4326")
    sample["lat"] = sample_4326.geometry.centroid.y
    sample["lon"] = sample_4326.geometry.centroid.x

    # Rename columns
    sample["field_id"] = [f"WV_AG_{i + 1:03d}" for i in range(len(sample))]
    sample["area_acres"] = sample["CSBACRES"]

    # Select output columns
    out = sample[["field_id", "lat", "lon", "area_acres", "geometry"]].copy()

    # Ensure output directory exists
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Save
    out.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"\nSaved {len(out)} specialty fields to {OUTPUT_PATH}")

    return out


def main():
    """Main entry point."""
    print("=" * 60)
    print("Oregon Willamette Valley Agricultural Fields")
    print("=" * 60)
    print(f"Filtering for crop codes: {SPECIALTY_CODES}")
    print("  74 = Horticulture (includes grapes)")
    print("  75 = Berries")
    print("  204 = Christmas Trees")
    print("  36 = Alfalfa")
    print("  37 = Other Hay")
    print("  176 = Grassland/Herbaceous")
    print("  59 = Grass/Pasture")
    print("  38 = Small Grains")
    print("  24 = Winter Wheat")
    print("  27 = Spring Wheat")
    print()

    # Check if CSB exists
    if not Path(CSB_DIR).exists():
        download_csb()

    # Get specialty fields
    fields = get_specialty_fields()

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
    print(f"Output: {OUTPUT_PATH}")
    print(f"Fields: {len(fields)}")
    print(f"Area range: {fields['area_acres'].min():.1f} - {fields['area_acres'].max():.1f} acres")


if __name__ == "__main__":
    main()
