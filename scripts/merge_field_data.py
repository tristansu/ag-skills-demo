#!/usr/bin/env python3
"""
Merge field data from assignment-02 into a single GeoJSON file.

Combines:
- Field boundaries (GeoJSON)
- CDL crop data (CSV)
- SSURGO soil data (CSV) - aggregated to dominant soil per field
- NASA POWER weather data (CSV) - aggregated to monthly averages per field

Output: data/assignment-02/fields_complete.geojson

Usage: python scripts/merge_field_data.py
"""

import csv
import json
from collections import defaultdict
from pathlib import Path


def load_geojson(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_csv(path: str) -> list[dict]:
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_dominant_soil(soil_rows: list[dict]) -> dict | None:
    """Select dominant soil component based on comppct_r."""
    valid_rows = [r for r in soil_rows if r.get("comppct_r") and r["comppct_r"].strip()]
    if not valid_rows:
        return None

    dominant = max(valid_rows, key=lambda r: float(r["comppct_r"]))

    return {
        "muname": dominant.get("muname", "").strip('"'),
        "drainagecl": dominant.get("drainagecl", ""),
        "clay_pct": _safe_float(dominant.get("claytotal_r")),
        "sand_pct": _safe_float(dominant.get("sandtotal_r")),
        "silt_pct": _safe_float(dominant.get("silttotal_r")),
        "om_pct": _safe_float(dominant.get("om_r")),
        "ph": _safe_float(dominant.get("ph1to1h2o_r")),
        "cec": _safe_float(dominant.get("cec7_r")),
        "depth_cm": _safe_float(dominant.get("hzdept_r")),
    }


def _safe_float(val: str) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def aggregate_weather_monthly(weather_rows: list[dict]) -> list[dict]:
    """Aggregate daily weather to monthly averages per field."""
    monthly_data = defaultdict(lambda: {"temps_max": [], "temps_min": [], "rainfall": []})

    for row in weather_rows:
        date = row.get("date", "")
        if not date:
            continue

        try:
            year, month = date.split("-")[:2]
        except ValueError:
            continue

        key = (year, month)
        monthly_data[key]["temps_max"].append(_safe_float(row.get("T2M_MAX")) or 0)
        monthly_data[key]["temps_min"].append(_safe_float(row.get("T2M_MIN")) or 0)
        monthly_data[key]["rainfall"].append(_safe_float(row.get("PRECTOTCORR")) or 0)

    result = []
    for (year, month), data in sorted(monthly_data.items()):
        if data["temps_max"]:
            result.append(
                {
                    "year": int(year),
                    "month": int(month),
                    "avg_high_c": round(sum(data["temps_max"]) / len(data["temps_max"]), 2),
                    "avg_low_c": round(sum(data["temps_min"]) / len(data["temps_min"]), 2),
                    "total_rain_mm": round(sum(data["rainfall"]), 2),
                    "total_rain_in": round(sum(data["rainfall"]) * 0.0393701, 2),
                }
            )

    return result


def main():
    base_dir = Path("data/assignment-02")

    print("Loading data files...")
    fields_geojson = load_geojson(base_dir / "fields_oregon_willamette_ag_2025.geojson")
    cdl_data = load_csv(base_dir / "cdl_oregon_willamette_ag_2025.csv")
    soil_data = load_csv(base_dir / "soil_oregon_willamette_ag_2025.csv")
    weather_data = load_csv(base_dir / "weather_oregon_willamette_ag_2020_2025.csv")

    print(f"  Fields: {len(fields_geojson['features'])}")
    print(f"  CDL records: {len(cdl_data)}")
    print(f"  Soil records: {len(soil_data)}")
    print(f"  Weather records: {len(weather_data)}")

    print("\nIndexing CDL data by field_id...")
    cdl_by_field = {row["field_id"]: row for row in cdl_data}

    print("Indexing soil data by field_id...")
    soil_by_field = defaultdict(list)
    for row in soil_data:
        soil_by_field[row["field_id"]].append(row)

    print("Indexing weather data by field_id...")
    weather_by_field = defaultdict(list)
    for row in weather_data:
        weather_by_field[row["field_id"]].append(row)

    print("\nMerging data into GeoJSON...")
    merged_features = []

    for feature in fields_geojson["features"]:
        field_id = feature["properties"]["field_id"]
        props = feature["properties"]

        if field_id in cdl_by_field:
            cdl = cdl_by_field[field_id]
            props["crop_code"] = int(cdl["crop_code"])
            props["cdl_crop"] = cdl["cdl_crop"]
            props["crop_dominant_pct"] = float(cdl["dominant_pct"])

        if field_id in soil_by_field:
            soil = get_dominant_soil(soil_by_field[field_id])
            if soil:
                props["soil_muname"] = soil["muname"]
                props["soil_drainage"] = soil["drainagecl"]
                props["soil_clay_pct"] = soil["clay_pct"]
                props["soil_sand_pct"] = soil["sand_pct"]
                props["soil_silt_pct"] = soil["silt_pct"]
                props["soil_om_pct"] = soil["om_pct"]
                props["soil_ph"] = soil["ph"]
                props["soil_cec"] = soil["cec"]
                props["soil_depth_cm"] = soil["depth_cm"]

        if field_id in weather_by_field:
            monthly = aggregate_weather_monthly(weather_by_field[field_id])
            props["weather_monthly"] = monthly

        merged_features.append(feature)

    output_geojson = {
        "type": "FeatureCollection",
        "name": "fields_complete",
        "crs": fields_geojson.get("crs"),
        "features": merged_features,
    }

    output_path = base_dir / "fields_complete.geojson"
    print(f"\nWriting output to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(output_geojson, f, indent=2)

    print(f"Done! Created {output_path}")
    print(f"  Total features: {len(merged_features)}")

    sample = merged_features[0]["properties"]
    print("\nSample field properties:")
    print(f"  field_id: {sample.get('field_id')}")
    print(f"  cdl_crop: {sample.get('cdl_crop')}")
    print(f"  soil_muname: {sample.get('soil_muname')}")
    print(f"  soil_drainage: {sample.get('soil_drainage')}")
    weather = sample.get("weather_monthly", [])
    if weather:
        print(f"  weather_monthly: {len(weather)} months (first: {weather[0]})")


if __name__ == "__main__":
    main()
