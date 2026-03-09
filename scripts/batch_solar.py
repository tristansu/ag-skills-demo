#!/usr/bin/env python3
"""Batch process solar radiation for all fields."""

import json
import tempfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import mapping
import subprocess

SOLAR_SCRIPT = Path("scripts/lat_lon_polygon_to_solar_radiation_daily.py")
TERRAIN_DIR = Path("data/terrain")
OUTPUT_DIR = Path("data/solar")
INPUT_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    gdf = gpd.read_file(INPUT_GEOJSON)
    gdf_wgs84 = gdf.to_crs("EPSG:4326")
    
    print(f"Processing {len(gdf_wgs84)} fields...")
    
    success = 0
    skipped = 0
    errors = 0
    
    for idx, (_, row) in enumerate(gdf_wgs84.iterrows()):
        field_id = row["field_id"]
        
        existing = list(OUTPUT_DIR.glob(f"{field_id}_solar_yearly.tif"))
        if existing:
            print(f"[{idx + 1}/{len(gdf_wgs84)}] {field_id} - already exists, skipping")
            skipped += 1
            continue
        
        print(f"[{idx + 1}/{len(gdf_wgs84)}] {field_id}...")
        
        # Create temp geojson file
        geom_dict = mapping(row.geometry)
        feature = {"type": "Feature", "geometry": geom_dict, "properties": {}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(feature, f)
            temp_file = f.name
        
        # Check if we have slope/aspect
        slope_tif = TERRAIN_DIR / f"{field_id}_slope.tif"
        aspect_tif = TERRAIN_DIR / f"{field_id}_aspect.tif"
        
        try:
            if slope_tif.exists() and aspect_tif.exists():
                result = subprocess.run(
                    ["python", str(SOLAR_SCRIPT),
                     "--input", temp_file,
                     "--output-dir", str(OUTPUT_DIR),
                     "--slope-tif", str(slope_tif),
                     "--aspect-tif", str(aspect_tif),
                     "--field-id", field_id,
                     "--resolution", "5",
                     "--padding", "0.15"],
                    capture_output=True,
                    text=True,
                    timeout=180
                )
            else:
                # Let script fetch its own slope/aspect
                result = subprocess.run(
                    ["python", str(SOLAR_SCRIPT),
                     "--input", temp_file,
                     "--output-dir", str(OUTPUT_DIR),
                     "--field-id", field_id,
                     "--resolution", "5",
                     "--padding", "0.15"],
                    capture_output=True,
                    text=True,
                    timeout=180
                )
            
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr[:200]}")
                errors += 1
            else:
                print(f"  Done")
                success += 1
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT")
            errors += 1
        finally:
            Path(temp_file).unlink()
    
    print(f"\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
