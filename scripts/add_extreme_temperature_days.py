#!/usr/bin/env python3
"""
Calculate Extreme Temperature Days from Weather Data.

This script:
1. Loads weather data
2. Counts days below freezing thresholds (frost, killing frost)
3. Counts days above heat thresholds
4. Calculates Growing Degree Days (GDD)
5. Aggregates to field-level averages
6. Saves to CSV

Usage:
    python scripts/add_extreme_temperature_days.py

Output:
    data/assignment-03/field_extreme_temperature.csv

Requirements:
    pandas, numpy

Configurable thresholds (edit at top of file):
    FROST_THRESHOLD_C = 0        # Days below this = frost days
    KILLING_FROST_THRESHOLD_C = -2  # Days below this = killing frost
    HEAT_THRESHOLD_C = 30       # Days above this = heat days
    GDD_BASE_TEMP_C = 10        # Base temp for Growing Degree Days
"""

import subprocess
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Configuration - Adjust these thresholds as needed
FROST_THRESHOLD_C = 0        # Days below this = frost days
KILLING_FROST_THRESHOLD_C = -2  # Days below this = killing frost days
HEAT_THRESHOLD_C = 30       # Days above this = heat days
GDD_BASE_TEMP_C = 10        # Base temp for Growing Degree Days

WEATHER_PATH = Path("data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv")
OUTPUT_PATH = Path("data/assignment-03/field_extreme_temperature.csv")


def install_deps():
    """Install required packages."""
    packages = ["pandas", "numpy"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def get_season(month):
    """Return season for a given month."""
    if month in [3, 4, 5]:
        return 'spring'
    elif month in [6, 7, 8]:
        return 'summer'
    elif month in [9, 10, 11]:
        return 'fall'
    else:
        return 'winter'


def calculate_extreme_days(weather_df):
    """Calculate extreme temperature days for each field."""
    weather_df = weather_df.copy()
    weather_df['date'] = pd.to_datetime(weather_df['date'])
    weather_df['year'] = weather_df['date'].dt.year
    weather_df['month'] = weather_df['date'].dt.month
    
    results = []
    
    for field_id in weather_df['field_id'].unique():
        field_data = weather_df[weather_df['field_id'] == field_id]
        
        yearly_stats = []
        
        for year in field_data['year'].unique():
            year_data = field_data[field_data['year'] == year]
            
            # Frost days (below FROST_THRESHOLD_C)
            frost_days = (year_data['T2M_MIN'] < FROST_THRESHOLD_C).sum()
            
            # Killing frost days (below KILLING_FROST_THRESHOLD_C)
            killing_frost_days = (year_data['T2M_MIN'] < KILLING_FROST_THRESHOLD_C).sum()
            
            # Heat days (above HEAT_THRESHOLD_C)
            heat_days = (year_data['T2M_MAX'] > HEAT_THRESHOLD_C).sum()
            
            # Growing Degree Days (using simple method: (T_max + T_min)/2 - base)
            # Only count positive GDD days
            avg_temp = (year_data['T2M_MAX'] + year_data['T2M_MIN']) / 2
            gdd = (avg_temp - GDD_BASE_TEMP_C).clip(lower=0).sum()
            
            yearly_stats.append({
                'year': year,
                'frost_days': frost_days,
                'killing_frost_days': killing_frost_days,
                'heat_days': heat_days,
                'gdd': gdd
            })
        
        yearly_df = pd.DataFrame(yearly_stats)
        
        results.append({
            'field_id': field_id,
            'frost_days': yearly_df['frost_days'].mean(),
            'killing_frost_days': yearly_df['killing_frost_days'].mean(),
            'heat_days': yearly_df['heat_days'].mean(),
            'growing_degree_days': yearly_df['gdd'].mean()
        })
    
    return pd.DataFrame(results)


def main():
    """Main function."""
    print("=" * 60)
    print("Extreme Temperature Days Analysis")
    print("=" * 60)
    print(f"\nThresholds:")
    print(f"  Frost threshold: {FROST_THRESHOLD_C}°C")
    print(f"  Killing frost threshold: {KILLING_FROST_THRESHOLD_C}°C")
    print(f"  Heat threshold: {HEAT_THRESHOLD_C}°C")
    print(f"  GDD base temperature: {GDD_BASE_TEMP_C}°C")
    
    if not WEATHER_PATH.exists():
        print(f"\n❌ Weather file not found: {WEATHER_PATH}")
        print("Run scripts/get_weather.py first")
        return
    
    print(f"\nLoading weather data from {WEATHER_PATH}...")
    weather = pd.read_csv(WEATHER_PATH)
    print(f"  Loaded {len(weather)} records for {weather['field_id'].nunique()} fields")
    
    print("\nCalculating extreme temperature days...")
    df = calculate_extreme_days(weather)
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    
    print(f"\n✅ Saved {len(df)} records to {OUTPUT_PATH}")
    print(f"\nSummary Statistics:")
    print(df.describe())
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
