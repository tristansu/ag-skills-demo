#!/usr/bin/env python3
"""
Download SSURGO soil polygons for each field from NRCS Soil Data Access API.

Output:
- docs/assignment-03b/soil_data/ssurgo_polygons.geojson - Spatial soil boundaries
- docs/assignment-03b/soil_data/ssurgo_properties.csv - Soil property data
"""

import json
from pathlib import Path
from collections import defaultdict

import geopandas as gpd
import pandas as pd
import requests
from shapely import wkt

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

INPUT_GEOJSON = Path("docs/assignment-03b/fields_complete_wgs84.geojson")
OUTPUT_POLYGONS = Path("docs/assignment-03b/soil_data/ssurgo_polygons.geojson")
OUTPUT_PROPERTIES = Path("docs/assignment-03b/soil_data/ssurgo_properties.csv")

OUTPUT_POLYGONS.parent.mkdir(exist_ok=True, parents=True)


def query_sda(sql):
    """Execute SQL query against NRCS Soil Data Access API."""
    try:
        resp = requests.post(SDA_URL, data={"query": sql, "format": "JSON"}, timeout=120)
        resp.raise_for_status()
        return resp.json().get("Table", [])
    except Exception as e:
        print(f"  SDA query error: {e}")
        return []


def get_mukeys_for_field(wkt_geom):
    """Get list of mukeys that intersect with the field geometry."""
    sql = f"""
    SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt_geom}')
    """
    rows = query_sda(sql)
    return [str(row[0]) for row in rows if row[0]]


def get_soil_properties(mukeys):
    """Get soil properties for a list of mukeys."""
    if not mukeys:
        return []
    
    mukey_list = ", ".join(f"'{m}'" for m in mukeys)
    sql = f"""
    SELECT 
        mu.mukey,
        mu.muname,
        c.comppct_r,
        c.compname,
        c.drainagecl,
        ch.hzdept_r,
        ch.hzdepb_r,
        ch.om_r,
        ch.ph1to1h2o_r,
        ch.claytotal_r,
        ch.sandtotal_r,
        ch.silttotal_r,
        ch.cec7_r,
        ch.awc_r
    FROM mapunit mu
    INNER JOIN component c ON mu.mukey = c.mukey
    LEFT JOIN chorizon ch ON c.cokey = ch.cokey
    WHERE mu.mukey IN ({mukey_list})
    AND ch.hzdept_r IS NOT NULL
    ORDER BY mu.mukey, c.comppct_r DESC, ch.hzdept_r
    """
    rows = query_sda(sql)
    
    properties = []
    for row in rows:
        properties.append({
            "mukey": str(row[0]) if row[0] else None,
            "muname": row[1],
            "comppct_r": row[2],
            "compname": row[3],
            "drainagecl": row[4],
            "hzdept_r": row[5],
            "hzdepb_r": row[6],
            "om_r": row[7],
            "ph1to1h2o_r": row[8],
            "claytotal_r": row[9],
            "sandtotal_r": row[10],
            "silttotal_r": row[11],
            "cec7_r": row[12],
            "awc_r": row[13],
        })
    return properties


def get_mupolygon_geometry(mukey, field_wkt):
    """Get the polygon geometry for a specific mukey that intersects with field."""
    sql = f"""
    SELECT m.mupolygonkey, m.mupolygongeo.STAsText() AS wkt
    FROM mupolygon m
    WHERE m.mukey = '{mukey}'
    AND m.mupolygonkey IN (
        SELECT * FROM SDA_Get_Mupolygonkey_from_intersection_with_WktWgs84('{field_wkt}')
    )
    """
    rows = query_sda(sql)
    if rows and rows[0][1]:
        try:
            return wkt.loads(rows[0][1])
        except Exception:
            pass
    return None


def process_field(field_id, field_geom):
    """Process a single field to get soil polygons and properties."""
    wkt_geom = field_geom.wkt
    
    print(f"  Getting mukeys for {field_id}...")
    mukeys = get_mukeys_for_field(wkt_geom)
    
    if not mukeys:
        print(f"  No soil data found for {field_id}")
        return None, []
    
    print(f"  Found {len(mukeys)} mukeys, getting properties...")
    properties = get_soil_properties(mukeys)
    
    print(f"  Getting polygon geometries...")
    polygons = []
    for mukey in mukeys:
        geom = get_mupolygon_geometry(mukey, wkt_geom)
        if geom:
            polygons.append({
                "mukey": mukey,
                "geometry": geom,
            })
    
    return polygons, properties


def main():
    print(f"Loading {INPUT_GEOJSON}...")
    gdf = gpd.read_file(INPUT_GEOJSON)
    gdf_wgs84 = gdf.to_crs("EPSG:4326")
    
    print(f"Processing {len(gdf_wgs84)} fields...")
    
    all_polygons = []
    all_properties = []
    
    for idx, (_, field) in enumerate(gdf_wgs84.iterrows()):
        field_id = field["field_id"]
        print(f"\n[{idx + 1}/{len(gdf_wgs84)}] {field_id}")
        
        polygons, properties = process_field(field_id, field.geometry)
        
        if polygons:
            for poly in polygons:
                poly["field_id"] = field_id
                all_polygons.append(poly)
        
        if properties:
            for prop in properties:
                prop["field_id"] = field_id
                all_properties.append(prop)
    
    if all_polygons:
        print(f"\nSaving {len(all_polygons)} polygons to {OUTPUT_POLYGONS}...")
        gdf_polys = gpd.GeoDataFrame(all_polygons, crs="EPSG:4326")
        gdf_polys.to_file(OUTPUT_POLYGONS, driver="GeoJSON")
    else:
        print("\nNo polygons found, skipping GeoJSON output")
    
    if all_properties:
        print(f"Saving {len(all_properties)} property records to {OUTPUT_PROPERTIES}...")
        df_props = pd.DataFrame(all_properties)
        df_props.to_csv(OUTPUT_PROPERTIES, index=False)
    else:
        print("No properties found, skipping CSV output")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
