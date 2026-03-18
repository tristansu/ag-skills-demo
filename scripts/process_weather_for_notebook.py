#!/usr/bin/env python3
"""
Process weather data into monthly summaries for trend analysis.

Input:  data/weather_oregon_willamette_ag_2000_2025.csv
Output: data/weather_monthly_summary.csv

This script converts the large daily weather CSV (~475K rows) into 
monthly aggregated summaries (~15.6K rows) for efficient notebook analysis.

Usage:
    python scripts/process_weather_for_notebook.py
"""

import pandas as pd
from pathlib import Path

INPUT_PATH = "data/weather_oregon_willamette_ag_2000_2025.csv"
OUTPUT_PATH = "data/weather_monthly_summary.csv"


def get_season(month: int) -> str:
    """Return season name for given month."""
    if month in [12, 1, 2]:
        return 'winter'
    elif month in [3, 4, 5]:
        return 'spring'
    elif month in [6, 7, 8]:
        return 'summer'
    else:
        return 'fall'


def process_weather():
    """Process daily weather into monthly summaries."""
    
    print(f"Loading weather data from {INPUT_PATH}...")
    df = pd.read_csv(INPUT_PATH)
    df['date'] = pd.to_datetime(df['date'])
    
    print(f"Loaded {len(df):,} daily records")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Add date components
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['season'] = df['month'].apply(get_season)
    
    print(f"Processing {len(df):,} daily records...")
    
    # Aggregate to monthly summaries per field
    monthly = df.groupby(['field_id', 'year', 'month']).agg({
        'T2M': 'mean',
        'T2M_MAX': 'mean',
        'T2M_MIN': 'mean',
        'PRECTOTCORR': 'sum',
        'ALLSKY_SFC_SW_DWN': 'mean',
        'RH2M': 'mean',
        'WS10M': 'mean',
        'ET0': 'sum',
        'GDD': 'sum',
    }).reset_index()
    
    # Add season column
    monthly['season'] = monthly['month'].apply(get_season)
    
    # Rename columns for clarity
    monthly = monthly.rename(columns={
        'T2M': 'temp_mean_c',
        'T2M_MAX': 'temp_max_mean_c',
        'T2M_MIN': 'temp_min_mean_c',
        'PRECTOTCORR': 'precip_total_mm',
        'ALLSKY_SFC_SW_DWN': 'solar_rad_mean_mj',
        'RH2M': 'humidity_mean_pct',
        'WS10M': 'wind_speed_mean_ms',
        'ET0': 'et0_total_mm',
        'GDD': 'gdd_total',
    })
    
    # Save output
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(OUTPUT_PATH, index=False)
    
    print(f"Saved {len(monthly):,} monthly records to {OUTPUT_PATH}")
    
    # Print summary
    print(f"\nSummary:")
    print(f"  Fields: {monthly['field_id'].nunique()}")
    print(f"  Years: {monthly['year'].min()} - {monthly['year'].max()}")
    print(f"  Records: {len(monthly):,}")
    print(f"  Data reduction: {len(df):,} → {len(monthly):,} ({100*(1-len(monthly)/len(df)):.1f}% reduction)")
    
    # Show sample
    print(f"\nSample output:")
    print(monthly.head(10).to_string())
    
    return monthly


if __name__ == "__main__":
    process_weather()
