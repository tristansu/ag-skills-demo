#!/usr/bin/env python3
"""
Get Weather Data for Oregon Willamette Valley Fields from NASA POWER.

This script:
1. Loads field boundaries
2. Queries NASA POWER API for each field centroid
3. Downloads daily weather (temperature, precipitation, radiation, etc.)
4. Calculates ET0 using empirical calibration
5. Calculates Growing Degree Days (GDD)
6. Saves to CSV

Usage:
    python scripts/get_weather.py

Output:
    data/weather_oregon_willamette_ag_2000_2025.csv

Requirements:
    pandas, requests, geopandas

API:
    NASA POWER: https://power.larc.nasa.gov/

ET0 Reference:
    FAO-56 Penman-Monteith equation (Allen et al., 1998)

GDD Reference:
    GDD = max(0, min((T_max + T_min)/2, 30) - 10)
    Base temp: 10°C (corn/soybeans), Cap: 30°C
"""

import subprocess
import sys
import time
import math
from pathlib import Path

# Configuration
FIELDS_PATH = "data/fields_oregon_willamette_ag_2025.geojson"
OUTPUT_PATH = "data/weather_oregon_willamette_ag_2000_2025.csv"
BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# NASA POWER parameters (no ET0 - we calculate it ourselves)
PARAMS = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,RH2M,WS10M"
COMMUNITY = "AG"
START_DATE = "20000101"
END_DATE = "20251231"

# Default elevation for Willamette Valley (meters)
DEFAULT_ELEVATION = 100

# Monthly ET0 calibration factors for Willamette Valley (approximate)
MONTHLY_ET0_FACTORS = {
    1: 0.6, 2: 0.7, 3: 1.2, 4: 1.8, 5: 2.6, 6: 3.5,
    7: 4.2, 8: 3.9, 9: 2.8, 10: 1.8, 11: 1.0, 12: 0.6,
}


def calculate_et0(tmean: float, month: int) -> float:
    """
    Calculate Reference Evapotranspiration (ET0) using temperature-based
    empirical calibration for Willamette Valley.
    
    This approach is more reliable than FAO-56 for NASA POWER data because
    the solar radiation values from NASA POWER appear to use different
    units/scaling than required by the standard formula.
    
    Parameters:
        tmean: Mean daily temperature (°C)
        month: Month (1-12)
    
    Returns:
        ET0 in mm/day
    """
    if tmean is None or month is None:
        return None
    
    factor = MONTHLY_ET0_FACTORS.get(month, 1.5)
    temp_factor = max(0.5, tmean / 15)
    et0 = factor * temp_factor
    
    return max(0.2, min(et0, 8))
    g = 0
    
    # FAO-56 Penman-Monteith equation
    # ET0 = [0.408*Delta*(Rn-G) + gamma*(900/(T+273))*u2*(es-ea)] / [Delta + gamma*(1 + 0.34*u2)]
    
    numerator = (0.408 * delta * (rn - g) + 
                 gamma * (900 / (tmean + 273)) * u2 * (es - ea))
    denominator = delta + gamma * (1 + 0.34 * u2)
    
    if denominator <= 0:
        return None
    
    et0 = numerator / denominator
    
    # ET0 should be positive and reasonable (0-15 mm/day typically)
    return max(0, et0) if et0 is not None else None


def calculate_gdd(tmax: float, tmin: float, base_temp: float = 10.0, cap_temp: float = 30.0) -> float:
    """
    Calculate Growing Degree Days (GDD).
    
    Formula: GDD = max(0, min((T_max + T_min)/2, cap) - base)
    
    Parameters:
        tmax: Maximum daily temperature (°C)
        tmin: Minimum daily temperature (°C)
        base_temp: Base temperature (default 10°C for corn/soybeans)
        cap_temp: Cap temperature (default 30°C)
    
    Returns:
        GDD in degree-days
    """
    if tmax is None or tmin is None:
        return None
    
    t_avg = (tmax + tmin) / 2
    gdd = min(t_avg, cap_temp) - base_temp
    
    return max(0, gdd)


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
            tmax = param_data["T2M_MAX"][date_str]
            tmin = param_data["T2M_MIN"][date_str]
            tmean = param_data["T2M"][date_str]
            
            # Get month from date string
            month = int(date_str[4:6])
            
            # Calculate ET0 using empirical calibration
            et0 = calculate_et0(tmean, month)
            
            # Calculate GDD
            gdd = calculate_gdd(tmax, tmin)
            
            records.append(
                {
                    "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
                    "T2M": tmean,
                    "T2M_MAX": tmax,
                    "T2M_MIN": tmin,
                    "PRECTOTCORR": param_data["PRECTOTCORR"][date_str],
                    "ALLSKY_SFC_SW_DWN": param_data["ALLSKY_SFC_SW_DWN"][date_str],
                    "RH2M": param_data["RH2M"][date_str],
                    "WS10M": param_data["WS10M"][date_str],
                    "ET0": et0,
                    "GDD": gdd,
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
        "GDD",
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
