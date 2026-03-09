#!/usr/bin/env python3
"""Batch process soil for all fields in a GeoJSON."""

import json
import tempfile
from pathlib import Path
import geopandas as gpd
import subprocess

SOIL_SCRIPT = Path(__file__).parent / "lat_lon_polygon_to_ssurgo_soil.py"
INPUT_GEOJSON = Path("data/fields_oregon_willamette_ag_2025.geojson")
OUTPUT_DIR = Path("data/soil")

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    gdf = gpd.read_file(INPUT_GEOJSON)
    gdf_wgs84 = gdf.to_crs("EPSG:4326")
    
    print(f"Processing {len(gdf_wgs84)} fields...")
    
    for idx, (_, field) in enumerate(gdf_wgs84.iterrows()):
        field_id = field["field_id"]
        
        existing = list(OUTPUT_DIR.glob(f"{field_id}_soil.tif"))
        if existing:
            print(f"[{idx + 1}/{len(gdf_wgs84)}] {field_id} - already exists, skipping")
            continue
        
        print(f"[{idx + 1}/{len(gdf_wgs84)}] {field_id}...")
        
        geom = field.geometry
        
        if geom.geom_type == "Polygon":
            coords = [[list(c) for c in geom.exterior.coords]]
        elif geom.geom_type == "MultiPolygon":
            coords = [[[list(c) for c in p.exterior.coords] for p in geom.geoms]]
        else:
            print(f"  SKIP: Unsupported geometry type: {geom.geom_type}")
            continue
        
        geom_dict = {
            "type": geom.geom_type,
            "coordinates": coords
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(geom_dict, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", str(SOIL_SCRIPT),
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
                print(f"  ERROR: {result.stderr[:300]}")
            else:
                print(f"  Done")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT")
        finally:
            Path(temp_file).unlink()

if __name__ == "__main__":
    main()
