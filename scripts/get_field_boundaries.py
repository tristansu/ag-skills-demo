#!/usr/bin/env python3
"""
Get Oregon Willamette Valley Field Boundaries from USDA NASS Crop Sequence Boundaries.

This script:
1. Downloads the national CSB dataset (if not present)
2. Extracts Oregon Willamette Valley fields
3. Filters to fields >= 10 acres
4. Samples 50 random fields
5. Saves to GeoJSON

Usage:
    python scripts/get_field_boundaries.py

Output:
    data/assignment-02/fields_oregon_willamette_2025.geojson
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
OUTPUT_PATH = "data/assignment-02/fields_oregon_willamette_2025.geojson"
N_FIELDS = 50
MIN_ACRES = 10

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

    # Download with curl for reliability
    result = subprocess.run(
        ["curl", "-L", "-o", CSB_ZIP, CSB_URL, "--max-time", "3600"], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Download failed: {result.stderr}")
        sys.exit(1)

    print(f"Downloaded to {CSB_ZIP}")

    # Extract
    print("Extracting...")
    os.makedirs(CSB_DIR, exist_ok=True)
    with zipfile.ZipFile(CSB_ZIP, "r") as z:
        z.extractall(CSB_DIR)

    print(f"Extracted to {CSB_DIR}")


def get_field_boundaries():
    """Extract Willamette Valley field boundaries."""
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

    # Filter >= 10 acres
    wv = wv[wv["CSBACRES"] >= MIN_ACRES]
    print(f"After {MIN_ACRES}+ acres filter: {len(wv)} fields")

    # Sample N fields
    if len(wv) >= N_FIELDS:
        wv = wv.sample(n=N_FIELDS, random_state=42)
    else:
        print(f"Warning: Only {len(wv)} fields available, using all")

    print(f"Sampled: {len(wv)} fields")

    # Convert to lat/lon
    wv_4326 = wv.to_crs("EPSG:4326")
    wv["lat"] = wv_4326.geometry.centroid.y
    wv["lon"] = wv_4326.geometry.centroid.x

    # Rename columns
    wv["field_id"] = [f"WV_{i + 1:03d}" for i in range(len(wv))]
    wv["area_acres"] = wv["CSBACRES"]

    # Select output columns
    out = wv[["field_id", "lat", "lon", "area_acres", "geometry"]].copy()

    # Ensure output directory exists
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Save
    out.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"\nSaved {len(out)} fields to {OUTPUT_PATH}")

    return out


def main():
    """Main entry point."""
    print("=" * 60)
    print("Oregon Willamette Valley Field Boundaries")
    print("=" * 60)

    # Check if CSB exists
    if not Path(CSB_DIR).exists():
        download_csb()

    # Get field boundaries
    fields = get_field_boundaries()

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
    print(f"Output: {OUTPUT_PATH}")
    print(f"Fields: {len(fields)}")
    print(f"Area range: {fields['area_acres'].min():.1f} - {fields['area_acres'].max():.1f} acres")


if __name__ == "__main__":
    main()
