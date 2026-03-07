#!/usr/bin/env python3
"""
Get Weather Data for Oregon Willamette Valley Fields from NASA POWER.

This script:
1. Loads field boundaries
2. Queries NASA POWER API for each field centroid
3. Downloads daily weather (temperature, precipitation, radiation, etc.)
4. Saves to CSV

Usage:
    python scripts/get_weather.py

Output:
    data/assignment-02/weather_oregon_willamette_2020_2025.csv

Requirements:
    pandas, requests

API:
    NASA POWER: https://power.larc.nasa.gov/
"""

import subprocess
import sys
import time
from pathlib import Path

# Configuration
FIELDS_PATH = "data/assignment-02/fields_oregon_willamette_ag_2025.geojson"
OUTPUT_PATH = "data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv"
BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# NASA POWER parameters
PARAMS = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,RH2M,WS10M,ET0"  # ET0 = Reference Evapotranspiration
COMMUNITY = "AG"
START_DATE = "20200101"
END_DATE = "20251231"


def install_deps():
    """Install required packages."""
    packages = ["pandas", "requests"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def get_weather_for_point(lat: float, lon: float) -> list:
    """Get weather data for a point."""
    import requests

    params = {
        "parameters": PARAMS,
        "community": COMMUNITY,
        "longitude": lon,
        "latitude": lat,
        "start": START_DATE,
        "end": END_DATE,
        "format": "JSON",
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        param_data = data["properties"]["parameter"]
        dates = list(param_data["T2M"].keys())

        records = []
        for date_str in dates:
            records.append(
                {
                    "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
                    "T2M": param_data["T2M"][date_str],
                    "T2M_MAX": param_data["T2M_MAX"][date_str],
                    "T2M_MIN": param_data["T2M_MIN"][date_str],
                    "PRECTOTCORR": param_data["PRECTOTCORR"][date_str],
                    "ALLSKY_SFC_SW_DWN": param_data["ALLSKY_SFC_SW_DWN"][date_str],
                    "RH2M": param_data["RH2M"][date_str],
                    "WS10M": param_data["WS10M"][date_str],
                    "ET0": param_data.get("ET0", {}).get(date_str, None),
                }
            )

        return records
    except Exception as e:
        print(f"Error: {e}")
        return []


def get_weather_data():
    """Extract weather data for all fields."""
    try:
        import geopandas as gpd
    except ImportError:
        install_deps()
        import geopandas as gpd

    # Load fields
    if not Path(FIELDS_PATH).exists():
        print(f"Fields not found at {FIELDS_PATH}")
        print("Run scripts/get_field_boundaries.py first")
        sys.exit(1)

    fields = gpd.read_file(FIELDS_PATH)
    print(f"Loaded {len(fields)} fields")

    # Convert to lat/lon
    fields_4326 = fields.to_crs("EPSG:4326")
    fields_4326["lat"] = fields_4326.geometry.centroid.y
    fields_4326["lon"] = fields_4326.geometry.centroid.x

    # Query weather for each field
    print(f"Querying NASA POWER API ({START_DATE} to {END_DATE})...")

    import pandas as pd

    all_records = []
    for idx, row in fields_4326.iterrows():
        print(f"  {row['field_id']} ({idx + 1}/{len(fields)})...", end=" ")

        records = get_weather_for_point(row["lat"], row["lon"])

        if records:
            for r in records:
                r["field_id"] = row["field_id"]
                r["lat"] = row["lat"]
                r["lon"] = row["lon"]
            all_records.extend(records)
            print(f"Got {len(records)} days")
        else:
            print("No data")

        time.sleep(0.5)  # Rate limiting

    if not all_records:
        print("No weather data retrieved")
        return

    # Create DataFrame
    df = pd.DataFrame(all_records)

    # Reorder columns
    cols = [
        "field_id",
        "lat",
        "lon",
        "date",
        "T2M",
        "T2M_MAX",
        "T2M_MIN",
        "PRECTOTCORR",
        "ALLSKY_SFC_SW_DWN",
        "RH2M",
                "WS10M",
        "ET0",
    ]
    df = df[cols]

    # Save
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved {len(df)} records to {OUTPUT_PATH}")
    return df


def main():
    """Main entry point."""
    print("=" * 60)
    print("NASA POWER Weather Data Extraction")
    print("=" * 60)
    print(f"Date range: {START_DATE} to {END_DATE}")

    df = get_weather_data()

    if df is not None:
        print(f"\nFields with weather data: {df['field_id'].nunique()}")
        print(f"Total records: {len(df)}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
