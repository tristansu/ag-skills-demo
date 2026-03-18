#!/usr/bin/env python3
"""
Process daily weather data to extract heat wave and extreme temperature metrics.

Input:  data/weather_oregon_willamette_ag_2000_2025.csv
Output: data/heat_wave_summary.csv

This script identifies heat waves and extreme temperature events for each field
across the 26-year study period.

Usage:
    python scripts/process_heat_wave_metrics.py

Configurable thresholds:
    HEAT_WAVE_THRESHOLD: Temperature (°C) defining heat wave (default: 30°C)
    HEAT_WAVE_MIN_DAYS: Minimum consecutive days for heat wave (default: 3)
    EXTREME_HEAT_THRESHOLD: Temperature (°C) for extreme heat (default: 35°C)
    HOT_DAY_THRESHOLD: Temperature (°C) for hot days (default: 25°C)
"""

import pandas as pd
from pathlib import Path

INPUT_PATH = "data/weather_oregon_willamette_ag_2000_2025.csv"
OUTPUT_PATH = "data/heat_wave_summary.csv"

HEAT_WAVE_THRESHOLD = 30
HEAT_WAVE_MIN_DAYS = 3
EXTREME_HEAT_THRESHOLD = 35
HOT_DAY_THRESHOLD = 25


def identify_heat_waves(temp_series, threshold=HEAT_WAVE_THRESHOLD, min_days=HEAT_WAVE_MIN_DAYS):
    """
    Identify heat wave events (consecutive days above threshold).

    Returns: list of (start_idx, end_idx, length) tuples
    """
    above_threshold = temp_series >= threshold
    heat_waves = []
    current_start = None
    current_length = 0

    for i, is_hot in enumerate(above_threshold):
        if is_hot:
            if current_start is None:
                current_start = i
                current_length = 1
            else:
                current_length += 1
        else:
            if current_start is not None and current_length >= min_days:
                heat_waves.append((current_start, current_start + current_length - 1, current_length))
            current_start = None
            current_length = 0

    if current_start is not None and current_length >= min_days:
        heat_waves.append((current_start, current_start + current_length - 1, current_length))

    return heat_waves


def process_field_year(field_id, year, df_field):
    """Process all data for a single field in a single year."""
    df_year = df_field[df_field['year'] == year].copy()
    df_year = df_year.sort_values('date').reset_index(drop=True)

    if len(df_year) < 10:
        return None

    temps = df_year['T2M_MAX'].values

    heat_waves = identify_heat_waves(pd.Series(temps))

    heat_wave_count = len(heat_waves)
    heat_wave_avg_length = sum(hw[2] for hw in heat_waves) / heat_wave_count if heat_wave_count > 0 else 0
    heat_wave_total_days = sum(hw[2] for hw in heat_waves)

    hot_days_25 = (temps > HOT_DAY_THRESHOLD).sum()
    hot_days_30 = (temps > HEAT_WAVE_THRESHOLD).sum()
    extreme_heat_days = (temps > EXTREME_HEAT_THRESHOLD).sum()

    max_temp = temps.max()
    max_temp_idx = temps.argmax()
    max_temp_date = df_year.iloc[max_temp_idx]['date'] if max_temp_idx < len(df_year) else None

    return {
        'field_id': field_id,
        'year': year,
        'heat_wave_count': heat_wave_count,
        'heat_wave_avg_length': heat_wave_avg_length,
        'heat_wave_total_days': heat_wave_total_days,
        'hot_days_25': hot_days_25,
        'hot_days_30': hot_days_30,
        'extreme_heat_days': extreme_heat_days,
        'max_temp': max_temp,
        'max_temp_date': max_temp_date
    }


def process_heat_wave_metrics():
    """Process all fields and years to generate heat wave summary."""
    print(f"Loading daily weather data from {INPUT_PATH}...")
    df = pd.read_csv(INPUT_PATH)
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year

    print(f"Loaded {len(df):,} daily records")
    print(f"Fields: {df['field_id'].nunique()}")
    print(f"Years: {df['year'].min()} - {df['year'].max()}")

    fields = df['field_id'].unique()
    years = sorted(df['year'].unique())

    results = []
    total = len(fields) * len(years)
    processed = 0

    print(f"\nProcessing {len(fields)} fields × {len(years)} years = {total} field-years...")

    for field_id in fields:
        df_field = df[df['field_id'] == field_id]

        for year in years:
            result = process_field_year(field_id, year, df_field)
            if result:
                results.append(result)

            processed += 1
            if processed % 500 == 0:
                print(f"  Processed {processed}/{total} ({100*processed/total:.1f}%)")

    results_df = pd.DataFrame(results)

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved {len(results_df)} records to {OUTPUT_PATH}")
    print(f"\nSummary:")
    print(f"  Fields: {results_df['field_id'].nunique()}")
    print(f"  Years: {results_df['year'].min()} - {results_df['year'].max()}")
    print(f"  Total heat wave events: {results_df['heat_wave_count'].sum()}")
    print(f"  Total extreme heat days: {results_df['extreme_heat_days'].sum()}")

    print(f"\nSample output:")
    print(results_df.head(10).to_string())

    return results_df


if __name__ == "__main__":
    process_heat_wave_metrics()
