#!/usr/bin/env python3
"""
Add weather_avg_monthly property to GeoJSON fields.

Computes monthly averages across all years from weather_monthly data.
"""

import json
from pathlib import Path


def compute_weather_averages(weather_monthly):
    """Compute monthly averages from weather_monthly array."""
    if not weather_monthly:
        return None

    month_data = {m: [] for m in range(1, 13)}

    for record in weather_monthly:
        month = record.get('month')
        if month and 1 <= month <= 12:
            month_data[month].append(record)

    avg_high_c = []
    avg_low_c = []
    avg_rain_in = []

    for m in range(1, 13):
        records = month_data[m]
        if records:
            avg_high = sum(r.get('avg_high_c', 0) for r in records) / len(records)
            avg_low = sum(r.get('avg_low_c', 0) for r in records) / len(records)
            avg_rain = sum(r.get('total_rain_in', 0) for r in records) / len(records)
            avg_high_c.append(round(avg_high, 2))
            avg_low_c.append(round(avg_low, 2))
            avg_rain_in.append(round(avg_rain, 2))
        else:
            avg_high_c.append(0)
            avg_low_c.append(0)
            avg_rain_in.append(0)

    return {
        'avg_high_c': avg_high_c,
        'avg_low_c': avg_low_c,
        'avg_rain_in': avg_rain_in
    }


def main():
    input_path = Path('docs/assignment-03/fields_complete_wgs84.geojson')
    output_path = Path('docs/assignment-03/fields_complete_wgs84.geojson')

    print(f"Loading {input_path}...")
    with open(input_path, 'r') as f:
        geojson = json.load(f)

    print(f"Processing {len(geojson['features'])} fields...")

    for feature in geojson['features']:
        weather_monthly = feature['properties'].get('weather_monthly')
        if weather_monthly:
            weather_avg = compute_weather_averages(weather_monthly)
            feature['properties']['weather_avg_monthly'] = weather_avg

    print(f"Writing {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(geojson, f)

    print("Done!")


if __name__ == '__main__':
    main()
