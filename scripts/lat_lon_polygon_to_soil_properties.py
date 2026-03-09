#!/usr/bin/env python3
"""
Generate continuous soil property rasters at satellite resolution (10m, 10% padding).

This script:
1. Reads field polygons from GeoJSON
2. Queries NRCS Soil Data Access API for SSURGO soil data
3. Rasterizes soil properties at 10m resolution with 10% padding
4. Outputs Float32 GeoTIFFs with actual property values (not labels)

Usage:
    python scripts/lat_lon_polygon_to_soil_properties.py \
        --input data/assignment-03/fields_complete.geojson \
        --output-dir data/assignment-03/soil_properties \
        --resolution 10 \
        --padding 0.10

Output per field (e.g., WV_AG_001):
    pH_WV_AG_001.tif
    OM_pct_WV_AG_001.tif
    Clay_pct_WV_AG_001.tif
    Sand_pct_WV_AG_001.tif
    Silt_pct_WV_AG_001.tif
    CEC_WV_AG_001.tif

Requirements:
    geopandas, rasterio, numpy, requests, shapely
"""

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely import wkt
from shapely.geometry import shape


SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

PROPERTIES = {
    "pH": {"column": "ph1to1h2o_r", "name": "pH"},
    "OM_pct": {"column": "om_r", "name": "Organic Matter %"},
    "Clay_pct": {"column": "claytotal_r", "name": "Clay %"},
    "Sand_pct": {"column": "sandtotal_r", "name": "Sand %"},
    "Silt_pct": {"column": "silttotal_r", "name": "Silt %"},
    "CEC": {"column": "cec7_r", "name": "CEC"},
}


def parse_polygon_input(input_str):
    """Parse polygon input from file or GeoJSON string."""
    input_str = input_str.strip()

    input_path = Path(input_str)
    if input_path.exists():
        with open(input_path, 'r') as f:
            data = json.load(f)
    else:
        try:
            data = json.loads(input_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}")

    if isinstance(data, dict):
        if data.get('type') == 'FeatureCollection':
            features = data.get('features', [])
            if features:
                geom = shape(features[0]['geometry'])
                coords = None
                bounds = geom.bounds
        elif data.get('type') == 'Polygon':
            coords = data['coordinates'][0]
            geom = shape(data)
            bounds = geom.bounds
        elif data.get('type') == 'Feature' and data.get('geometry', {}).get('type') == 'Polygon':
            coords = data['geometry']['coordinates'][0]
            geom = shape(data['geometry'])
            bounds = geom.bounds
        else:
            raise ValueError("Unknown GeoJSON format")
    else:
        raise ValueError("Invalid input format")

    return {'geometry': geom, 'bounds': bounds}


def calculate_padded_bounds(bounds, padding):
    """Apply padding to bounds."""
    minx, miny, maxx, maxy = bounds
    dx = (maxx - minx) * padding
    dy = (maxy - miny) * padding
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def query_sda(sql):
    """Execute SQL query against NRCS Soil Data Access API."""
    try:
        resp = requests.post(SDA_URL, data={"query": sql, "format": "JSON"}, timeout=120)
        resp.raise_for_status()
        return resp.json().get("Table", [])
    except Exception as e:
        print(f"    SDA query error: {e}")
        return []


def get_mukeys_for_geometry(geometry):
    """Get list of mukeys that intersect with the geometry."""
    wkt_geom = geometry.wkt
    sql = f"SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt_geom}')"
    rows = query_sda(sql)
    return [str(row[0]) for row in rows if row[0]]


def get_soil_properties(mukeys):
    """Get soil properties for a list of mukeys."""
    if not mukeys:
        return {}

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
        ch.cec7_r
    FROM mapunit mu
    INNER JOIN component c ON mu.mukey = c.mukey
    LEFT JOIN chorizon ch ON c.cokey = ch.cokey
    WHERE mu.mukey IN ({mukey_list})
    AND ch.hzdept_r IS NOT NULL
    ORDER BY mu.mukey, c.comppct_r DESC, ch.hzdept_r
    """
    rows = query_sda(sql)

    properties = {}
    for row in rows:
        mukey = str(row[0]) if row[0] else None
        if mukey and mukey not in properties:
            properties[mukey] = {
                "mukey": mukey,
                "muname": row[1],
                "om_r": row[7],
                "ph1to1h2o_r": row[8],
                "claytotal_r": row[9],
                "sandtotal_r": row[10],
                "silttotal_r": row[11],
                "cec7_r": row[12],
            }
    return properties


def get_soil_polygons(geometry, mukeys):
    """Get polygon geometries for the mukeys."""
    wkt_geom = geometry.wkt

    polygons = []
    for mukey in mukeys:
        sql = f"""
        SELECT m.mupolygonkey, m.mupolygongeo.STAsText() AS wkt
        FROM mupolygon m
        WHERE m.mukey = '{mukey}'
        AND m.mupolygonkey IN (
            SELECT * FROM SDA_Get_Mupolygonkey_from_intersection_with_WktWgs84('{wkt_geom}')
        )
        """
        rows = query_sda(sql)
        if rows and rows[0][1]:
            try:
                geom = wkt.loads(rows[0][1])
                polygons.append({"mukey": mukey, "geometry": geom})
            except Exception:
                pass
    return polygons


def rasterize_properties(soil_gdf, padded_bounds, target_resolution, properties_dict):
    """Rasterize all soil properties to GeoTIFFs."""
    import rasterio

    minx, miny, maxx, maxy = padded_bounds

    # Calculate dimensions in meters, then divide by resolution (same as satellite script)
    mid_lat = (miny + maxy) / 2
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(0.01, abs(np.cos(np.radians(mid_lat))))
    
    width_m = (maxx - minx) * meters_per_deg_lon
    height_m = (maxy - miny) * meters_per_deg_lat
    
    width = max(5, round(width_m / target_resolution))
    height = max(5, round(height_m / target_resolution))

    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    output_files = {}

    for prop_name, prop_config in PROPERTIES.items():
        column = prop_config["column"]

        # Build mukey -> value mapping from properties_dict
        mukey_to_value = {}
        for mukey, props in properties_dict.items():
            val = props.get(column)
            if val is not None:
                try:
                    mukey_to_value[mukey] = float(val)
                except (ValueError, TypeError):
                    pass

        # Create shapes for rasterization
        shapes = []
        for _, row in soil_gdf.iterrows():
            mukey = row['mukey']
            if mukey in mukey_to_value:
                shapes.append((row['geometry'], mukey_to_value[mukey]))

        if shapes:
            raster = rasterize(
                shapes,
                out_shape=(height, width),
                transform=transform,
                fill=-9999.0,
                dtype=np.float32,
                all_touched=True
            )
        else:
            raster = np.full((height, width), np.nan, dtype=np.float32)

        output_files[prop_name] = raster

    return output_files, transform, (width, height)


def save_property_geotiff(output_path, data, transform, crs="EPSG:4326"):
    """Save property raster as Float32 GeoTIFF."""
    import rasterio

    height, width = data.shape

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "crs": crs,
        "nodata": np.nan,
        "compress": "lzw",
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data.astype(np.float32), 1)


import pandas as pd


def generate_field_properties(field_id, field_geom_wgs84, output_dir, target_resolution=10, padding=0.10):
    """Generate all property rasters for a single field."""
    # Use WGS84 geometry for API queries
    # Calculate padded bounds (same as satellite script)
    minx, miny, maxx, maxy = field_geom_wgs84.bounds
    
    dx = (maxx - minx) * padding
    dy = (maxy - miny) * padding
    padded_minx = minx - dx
    padded_miny = miny - dy
    padded_maxx = maxx + dx
    padded_maxy = maxy + dy
    
    padded_bounds = (padded_minx, padded_miny, padded_maxx, padded_maxy)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Querying NRCS Soil Data Access API...")

    mukeys = get_mukeys_for_geometry(field_geom_wgs84)
    if not mukeys:
        print(f"    No SSURGO soil data found for {field_id}")
        return []

    print(f"  Found {len(mukeys)} soil map units")

    properties = get_soil_properties(mukeys)
    print(f"  Retrieved properties for {len(properties)} map units")

    polygons = get_soil_polygons(field_geom_wgs84, mukeys)
    print(f"  Retrieved {len(polygons)} soil polygons")

    if not polygons:
        print(f"    Could not retrieve soil polygon geometries")
        return []

    soil_gdf = gpd.GeoDataFrame(polygons, crs="EPSG:4326")

    from shapely.geometry import box
    clip_geom = box(*padded_bounds)
    soil_gdf['geometry'] = soil_gdf['geometry'].intersection(clip_geom)
    soil_gdf = soil_gdf[~soil_gdf.is_empty]

    if len(soil_gdf) == 0:
        print(f"    No valid soil polygons after clipping")
        return []

    print(f"  Rasterizing {len(soil_gdf)} soil polygons at {target_resolution}m...")

    output_rasters, transform, dims = rasterize_properties(
        soil_gdf, padded_bounds, target_resolution, properties
    )

    print(f"  Raster dimensions: {dims[0]}x{dims[1]}")

    output_files = []
    for prop_name, raster in output_rasters.items():
        output_path = output_dir / f"{prop_name}_{field_id}.tif"
        print(f"    Saving {output_path.name}...")
        save_property_geotiff(output_path, raster, transform)
        output_files.append(str(output_path))

    return output_files


def main():
    parser = argparse.ArgumentParser(
        description="Generate continuous soil property rasters at satellite resolution"
    )
    parser.add_argument(
        "--input",
        default="data/assignment-03/fields_complete.geojson",
        help="Input GeoJSON file with field polygons",
    )
    parser.add_argument(
        "--output-dir",
        default="data/assignment-03/soil_properties",
        help="Output directory for soil property TIFs",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=10,
        help="Target resolution in meters (default: 10)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.10,
        help="Padding around polygon bounds as fraction (default: 0.10)",
    )
    parser.add_argument(
        "--start-field",
        type=int,
        default=1,
        help="Starting field number (default: 1)",
    )
    parser.add_argument(
        "--end-field",
        type=int,
        default=50,
        help="Ending field number (default: 50)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Soil Property Raster Generation")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Resolution: {args.resolution}m")
    print(f"Padding: {args.padding * 100:.0f}%")
    print("-" * 60)

    gdf = gpd.read_file(args.input)
    
    # Convert to WGS84 for API queries
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    field_ids = sorted(gdf["field_id"].unique())

    total = args.end_field - args.start_field + 1
    current = 0
    success = 0
    errors = 0

    for field_id in field_ids:
        field_num = int(field_id.split('_')[-1])
        if field_num < args.start_field or field_num > args.end_field:
            continue

        current += 1
        print(f"\n[{current}/{total}] {field_id}...")

        field_row = gdf[gdf["field_id"] == field_id]
        if len(field_row) == 0:
            print(f"  SKIP: Field not found")
            errors += 1
            continue

        field_geom = field_row.iloc[0].geometry

        try:
            files = generate_field_properties(
                field_id, field_geom, args.output_dir, args.resolution, args.padding
            )
            if files:
                print(f"  Success: {len(files)} files")
                success += 1
            else:
                errors += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Fields processed: {success}")
    print(f"Fields failed: {errors}")
    print(f"Output directory: {args.output_dir}")
    print("Done!")


if __name__ == "__main__":
    main()
