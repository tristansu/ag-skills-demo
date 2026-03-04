#!/usr/bin/env python3
"""
Get Soil Data for Oregon Willamette Valley Fields from NRCS SSURGO.

This script:
1. Loads field boundaries
2. Queries NRCS Soil Data Access API for each field centroid
3. Extracts soil properties (OM, pH, texture, drainage, etc.)
4. Saves to CSV

Usage:
    python scripts/get_soil.py

Output:
    data/assignment-02/soil_oregon_willamette_2025.csv

Requirements:
    geopandas, pandas, requests

API:
    NRCS Soil Data Access: https://sdmdataaccess.sc.egov.usda.gov/
"""

import subprocess
import sys
import time
from pathlib import Path

# Configuration
FIELDS_PATH = "data/assignment-02/fields_oregon_willamette_2025.geojson"
OUTPUT_PATH = "data/assignment-02/soil_oregon_willamette_2025.csv"
SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
MAX_DEPTH_CM = 60


def install_deps():
    """Install required packages."""
    packages = ["geopandas", "pandas", "requests"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def query_sda(sql: str) -> list:
    """Query the NRCS Soil Data Access API."""
    import requests

    for timeout_seconds in (60, 120):
        try:
            response = requests.post(
                SDA_URL,
                data={"query": sql, "format": "JSON"},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            result = response.json()

            if "Table" in result:
                return result["Table"]
            return []
        except Exception:
            continue
    return []


def get_soil_query(wkt: str, max_depth_cm: int = 30) -> str:
    """Build SQL query for soil properties."""
    return f"""
    SELECT DISTINCT
        mu.mukey,
        mu.muname,
        c.compname,
        c.comppct_r,
        c.drainagecl,
        ch.hzdept_r,
        ch.hzdepb_r,
        ch.om_r,
        ch.ph1to1h2o_r,
        ch.awc_r,
        ch.claytotal_r,
        ch.sandtotal_r,
        ch.silttotal_r,
        ch.dbthirdbar_r,
        ch.cec7_r
    FROM mapunit mu
    INNER JOIN component c ON mu.mukey = c.mukey
    LEFT JOIN chorizon ch ON c.cokey = ch.cokey
    WHERE mu.mukey IN (
        SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84(
            '{wkt}'
        )
    )
    AND (ch.hzdept_r < {max_depth_cm} OR ch.hzdept_r IS NULL)
    ORDER BY c.comppct_r DESC, ch.hzdept_r ASC
    """


SDA_COLUMNS = [
    "mukey",
    "muname",
    "compname",
    "comppct_r",
    "drainagecl",
    "hzdept_r",
    "hzdepb_r",
    "om_r",
    "ph1to1h2o_r",
    "awc_r",
    "claytotal_r",
    "sandtotal_r",
    "silttotal_r",
    "dbthirdbar_r",
    "cec7_r",
]

NUMERIC_COLUMNS = [
    "comppct_r",
    "hzdept_r",
    "hzdepb_r",
    "om_r",
    "ph1to1h2o_r",
    "awc_r",
    "claytotal_r",
    "sandtotal_r",
    "silttotal_r",
    "dbthirdbar_r",
    "cec7_r",
]


def get_soil_for_point(lon: float, lat: float, max_depth_cm: int = 30) -> list:
    """Get soil data for a point."""
    wkt = f"POINT({lon} {lat})"
    sql = get_soil_query(wkt, max_depth_cm)
    rows = query_sda(sql)

    return [dict(zip(SDA_COLUMNS, row)) for row in rows]


def get_soil_data():
    """Extract soil data for all fields."""
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

    # Query soil for each field
    print("Querying NRCS Soil Data Access API...")

    import pandas as pd

    all_results = []
    for idx, row in fields_4326.iterrows():
        print(f"  {row['field_id']} ({idx + 1}/{len(fields)})...", end=" ")

        try:
            soil = get_soil_for_point(row["lon"], row["lat"], MAX_DEPTH_CM)

            if soil:
                for s in soil:
                    s["field_id"] = row["field_id"]
                all_results.extend(soil)
                print(f"Got {len(soil)} records")
            else:
                print("No data")
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(0.3)  # Rate limiting

    if not all_results:
        print("No soil data retrieved")
        return

    # Create DataFrame
    df = pd.DataFrame(all_results)

    # Convert numeric columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Reorder columns
    cols = ["field_id"] + [c for c in df.columns if c != "field_id"]
    df = df[cols]

    # Save
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved {len(df)} soil records to {OUTPUT_PATH}")
    return df


def main():
    """Main entry point."""
    print("=" * 60)
    print("NRCS SSURGO Soil Data Extraction")
    print("=" * 60)

    df = get_soil_data()

    if df is not None:
        print(f"\nFields with soil data: {df['field_id'].nunique()}")
        print(f"Total records: {len(df)}")

    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
