#!/usr/bin/env python3
"""
Generate soil property maps from field boundary GeoJSON.

This script:
1. Takes GeoJSON with field boundaries (Polygon or MultiPolygon)
2. Queries NRCS Soil Data Access API for SSURGO soil data
3. Generates float GeoTIFFs for: OM%, clay%, silt%, sand%, CEC, AWC, pH, drainage
4. Creates JSON metadata with bounds, source, and resolution

=============================================================================
DETAILED USAGE
=============================================================================

Prerequisites:
    - Python 3.9+
    - Dependencies: geopandas, rasterio, numpy, requests, pandas, shapely
    - Internet access to NRCS Soil Data Access API

Input Format:
    GeoJSON file with:
    - A "field_id" property for each feature (or auto-generated if missing)
    - Polygon or MultiPolygon geometries in WGS84 (EPSG:4326)

    Example GeoJSON:
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "properties": {"field_id": "WV_AG_001"},
          "geometry": {
            "type": "Polygon",
            "coordinates": [[[-122.9, 44.9], [-122.8, 44.9], ...]]
          }
        }
      ]
    }

Basic Usage:
    # Process all fields in GeoJSON
    python scripts/generate_soil_maps.py --input data/fields.geojson --output-dir ./soil_output

    # Process single field by ID
    python scripts/generate_soil_maps.py --input data/fields.geojson --output-dir ./soil_output --field-id WV_AG_001

    # Custom padding and resolution
    python scripts/generate_soil_maps.py --input data/fields.geojson --output-dir ./soil_output --padding 0.15 --resolution 10

Full Options:
    --input        Path to GeoJSON file with field boundaries (required)
    --output-dir   Output directory (default: soil_maps)
    --padding      Padding around polygon as fraction (default: 0.10 = 10%%)
    --resolution   Target resolution in meters (default: 5)
    --field-id     Process single field by ID (default: all fields)

Output Structure:
    {output-dir}/
    └── {field_id}/
        ├── {field_id}_om_pct.tif       # Organic Matter (%)
        ├── {field_id}_clay_pct.tif      # Clay content (%)
        ├── {field_id}_silt_pct.tif      # Silt content (%)
        ├── {field_id}_sand_pct.tif      # Sand content (%)
        ├── {field_id}_cec.tif           # Cation Exchange Capacity (meq/100g)
        ├── {field_id}_awc.tif          # Available Water Capacity (cm/cm)
        ├── {field_id}_ph.tif           # pH
        ├── {field_id}_drainage.tif     # Drainage class (encoded as integer)
        └── {field_id}_soil_metadata.json

    Drainage encoding:
        1 = Well drained
        2 = Moderately well drained
        3 = Somewhat poorly drained
        4 = Poorly drained
        5 = Very poorly drained
        6 = Excessively drained
        7 = Somewhat excessively drained

Metadata JSON includes:
    - field_id
    - properties: min/max values and units for each property
    - spatial: bounds, CRS, resolution, padding
    - data_source: USDA NRCS SSURGO

Example:
    python scripts/generate_soil_maps.py \\
        --input data/fields_oregon_willamette_ag_2025.geojson \\
        --output-dir ./soil_maps \\
        --field-id WV_AG_001 \\
        --padding 0.10 \\
        --resolution 5
"""

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely import wkt
from shapely.geometry import shape, box


SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

DRAINAGE_ENCODING = {
    "Well drained": 1,
    "Moderately well drained": 2,
    "Somewhat poorly drained": 3,
    "Poorly drained": 4,
    "Very poorly drained": 5,
    "Excessively drained": 6,
    "Somewhat excessively drained": 7,
}


def parse_geojson(input_path):
    """Parse GeoJSON file and return GeoDataFrame in WGS84."""
    gdf = gpd.read_file(input_path)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


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
    sql = f"""
    SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt_geom}')
    """
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

    properties = {}
    for row in rows:
        mukey = str(row[0]) if row[0] else None
        if mukey and mukey not in properties:
            properties[mukey] = {
                "mukey": mukey,
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
                polygons.append({
                    "mukey": mukey,
                    "geometry": geom,
                })
            except Exception:
                pass
    return polygons


def create_raster(padded_bounds, target_resolution=5):
    """Create empty raster array and transform."""
    minx, miny, maxx, maxy = padded_bounds

    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, abs(np.cos(np.radians(mid_lat)))))

    width = int(np.ceil((maxx - minx) / (target_resolution * deg_per_m_lon)))
    height = int(np.ceil((maxy - miny) / (target_resolution * deg_per_m_lat)))

    width = max(64, width)
    height = max(64, height)

    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    return width, height, transform


def generate_soil_property_tifs(
    soil_gdf,
    properties,
    padded_bounds,
    output_dir,
    field_id,
    target_resolution=5
):
    """Generate float GeoTIFFs for each soil property."""
    width, height, transform = create_raster(padded_bounds, target_resolution)

    unique_mukeys = soil_gdf['mukey'].unique()
    mukey_to_label = {mukey: i + 1 for i, mukey in enumerate(unique_mukeys)}
    label_to_mukey = {v: k for k, v in mukey_to_label.items()}

    shapes = [(row['geometry'], mukey_to_label[str(row['mukey'])]) for _, row in soil_gdf.iterrows()]

    label_raster = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=True
    )

    PROPERTIES = [
        ("om_pct", "om_r", "percent"),
        ("clay_pct", "claytotal_r", "percent"),
        ("silt_pct", "silttotal_r", "percent"),
        ("sand_pct", "sandtotal_r", "percent"),
        ("cec", "cec7_r", "meq/100g"),
        ("awc", "awc_r", "cm/cm"),
        ("ph", "ph1to1h2o_r", "pH"),
        ("drainage", "drainagecl", None),
    ]

    property_stats = {}
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "crs": "EPSG:4326",
        "nodata": np.nan,
        "compress": "lzw",
    }

    for prop_key, db_col, unit in PROPERTIES:
        output_data = np.full((height, width), np.nan, dtype=np.float32)

        for label_id, mukey in label_to_mukey.items():
            if mukey in properties:
                prop = properties[mukey]
                value = prop.get(db_col)

                if prop_key == "drainage":
                    if value:
                        value = DRAINAGE_ENCODING.get(value, None)
                    else:
                        value = np.nan
                elif value is None:
                    value = np.nan

                if value is not None and not (isinstance(value, float) and np.isnan(value)):
                    mask = label_raster == label_id
                    output_data[mask] = float(value)

        output_path = output_dir / f"{field_id}_{prop_key}.tif"
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(output_data.astype(np.float32), 1)

        valid_values = output_data[~np.isnan(output_data)]
        if len(valid_values) > 0:
            property_stats[prop_key] = {
                "min": float(np.min(valid_values)),
                "max": float(np.max(valid_values)),
                "unit": unit,
            }
            if prop_key == "drainage":
                property_stats[prop_key]["encoding"] = DRAINAGE_ENCODING.copy()
        else:
            property_stats[prop_key] = {"min": None, "max": None, "unit": unit}

    return property_stats


def generate_soil_maps(input_geojson, output_dir, padding=0.10, resolution=5, single_field_id=None):
    """Generate soil maps for all fields in GeoJSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading fields from {input_geojson}...")
    gdf = parse_geojson(input_geojson)

    if "field_id" not in gdf.columns:
        gdf["field_id"] = [f"field_{i}" for i in range(len(gdf))]

    if single_field_id:
        gdf = gdf[gdf["field_id"] == single_field_id]
        if len(gdf) == 0:
            raise ValueError(f"Field ID '{single_field_id}' not found in GeoJSON")

    print(f"Processing {len(gdf)} field(s)...")

    results = []
    for idx, (_, row) in enumerate(gdf.iterrows()):
        field_id = row["field_id"]
        geometry = row.geometry

        field_output_dir = output_dir / field_id
        field_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{idx + 1}/{len(gdf)}] Processing {field_id}...")

        padded_bounds = calculate_padded_bounds(geometry.bounds, padding)
        print(f"  Bounds: {geometry.bounds}")
        print(f"  Padded: {padded_bounds}")

        print(f"  Querying NRCS Soil Data Access API...")
        mukeys = get_mukeys_for_geometry(geometry)

        if not mukeys:
            print(f"  WARNING: No SSURGO data found for {field_id}")
            continue

        print(f"  Found {len(mukeys)} soil map units")

        properties = get_soil_properties(mukeys)
        print(f"  Retrieved properties for {len(properties)} map units")

        polygons = get_soil_polygons(geometry, mukeys)
        print(f"  Retrieved {len(polygons)} soil polygons")

        if not polygons:
            print(f"  WARNING: Could not retrieve soil polygons for {field_id}")
            continue

        soil_gdf = gpd.GeoDataFrame(polygons, crs="EPSG:4326")

        clip_geom = box(*padded_bounds)
        soil_gdf['geometry'] = soil_gdf['geometry'].intersection(clip_geom)
        soil_gdf = soil_gdf[~soil_gdf.is_empty]

        if len(soil_gdf) == 0:
            print(f"  WARNING: No valid soil polygons after clipping for {field_id}")
            continue

        print(f"  Generating property rasters...")
        property_stats = generate_soil_property_tifs(
            soil_gdf,
            properties,
            padded_bounds,
            field_output_dir,
            field_id,
            resolution
        )

        metadata = {
            "field_id": field_id,
            "properties": property_stats,
            "spatial": {
                "bounds": list(padded_bounds),
                "crs": "EPSG:4326",
                "resolution_m": resolution,
                "padding_pct": int(padding * 100),
            },
            "data_source": "USDA NRCS SSURGO",
        }

        metadata_path = field_output_dir / f"{field_id}_soil_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"  Generated {len(property_stats)} property TIFs")
        print(f"  Metadata: {metadata_path}")

        results.append({
            "field_id": field_id,
            "output_dir": str(field_output_dir),
            "num_soil_units": len(properties),
            "property_stats": property_stats,
        })

    print(f"\n=== Summary ===")
    print(f"Total fields: {len(gdf)}")
    print(f"Processed: {len(results)}")
    print(f"Output: {output_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate soil property maps from field boundary GeoJSON"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to GeoJSON file with field boundaries",
    )
    parser.add_argument(
        "--output-dir",
        default="soil_maps",
        help="Output directory (default: soil_maps)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.10,
        help="Padding around polygon bounds as fraction (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=5,
        help="Target resolution in meters (default: 5)",
    )
    parser.add_argument(
        "--field-id",
        default=None,
        help="Process single field by ID (default: all fields)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Soil Map Generation")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m")
    if args.field_id:
        print(f"Field ID: {args.field_id}")
    print("-" * 60)

    try:
        results = generate_soil_maps(
            args.input,
            args.output_dir,
            padding=args.padding,
            resolution=args.resolution,
            single_field_id=args.field_id,
        )
        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
