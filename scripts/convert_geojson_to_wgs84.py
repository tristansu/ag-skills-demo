#!/usr/bin/env python3
"""Convert fields_complete.geojson from EPSG:5070 to EPSG:4326 (WGS84)."""

import json
import geopandas as gpd
from shapely.geometry import shape, mapping

def convert_geojson_to_wgs84(input_path, output_path):
    print(f"Loading GeoJSON from {input_path}...")
    
    # Load the GeoJSON file
    gdf = gpd.read_file(input_path)
    print(f"Loaded {len(gdf)} features")
    print(f"Original CRS: {gdf.crs}")
    
    # Check current CRS and transform to WGS84 if needed
    if gdf.crs and str(gdf.crs) != "EPSG:4326":
        print("Transforming to EPSG:4326 (WGS84)...")
        gdf_wgs84 = gdf.to_crs("EPSG:4326")
    else:
        print("Already in EPSG:4326, no transformation needed")
        gdf_wgs84 = gdf
    
    print(f"New CRS: {gdf_wgs84.crs}")
    
    # Save to new file
    print(f"Saving to {output_path}...")
    gdf_wgs84.to_file(output_path, driver="GeoJSON")
    
    # Verify first feature coordinates
    first_geom = gdf_wgs84.iloc[0].geometry
    if hasattr(first_geom, 'exterior'):
        coords = list(first_geom.exterior.coords)
    elif hasattr(first_geom, 'geoms'):
        coords = list(first_geom.geoms[0].exterior.coords)
    else:
        coords = list(first_geom.coords)
    
    print(f"First coordinate (should be lat/lon): {coords[0]}")
    print("Done!")

if __name__ == "__main__":
    input_file = "docs/assignment-03/fields_complete.geojson"
    output_file = "docs/assignment-03/fields_complete_wgs84.geojson"
    convert_geojson_to_wgs84(input_file, output_file)
