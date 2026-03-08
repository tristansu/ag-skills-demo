#!/usr/bin/env python3
"""
Generate SSURGO soil raster from lat/lon polygon coordinates.

This script:
1. Takes polygon coordinates (GeoJSON or simple [lon,lat] list)
2. Queries NRCS Soil Data Access API for SSURGO soil data
3. Rasterizes soil polygons to GeoTIFF with integer labels (mukey)
4. Outputs JSON with soil type definitions

Usage:
    # GeoJSON polygon format:
    python scripts/lat_lon_polygon_to_ssurgo_soil.py \
        --input '{"type":"Polygon","coordinates":[[[-122.9,44.8],[-122.8,44.8],...]]}' \
        --output-dir ./soil_output

    # Simple list format:
    python scripts/lat_lon_polygon_to_ssurgo_soil.py \
        --input "[[-122.9,44.8],[-122.8,44.8],[-122.85,44.7]]" \
        --output-dir ./soil_output

    # From file:
    python scripts/lat_lon_polygon_to_ssurgo_soil.py \
        --input path/to/polygon.geojson \
        --output-dir ./soil_output \
        --padding 0.15 \
        --field-id my_field

Output:
    {field_id}_soil.tif          - GeoTIFF with soil labels (mukey integers)
    {field_id}_soil_labels.json - JSON with soil type definitions

Requirements:
    geopandas, rasterio, requests, shapely, pandas
"""

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from rasterio.features import rasterize
from shapely import wkt
from shapely.geometry import shape


SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"


def parse_polygon_input(input_str):
    """
    Parse polygon input from various formats.

    Args:
        input_str: JSON string (GeoJSON or simple list) OR path to .geojson/.json file

    Returns:
        dict with 'type' (str), 'coordinates' (list), 'bounds' (tuple), and 'geometry' (shapely geometry)
    """
    input_str = input_str.strip()

    # Check if it's a file path
    input_path = Path(input_str)
    if input_path.exists():
        with open(input_path, 'r') as f:
            data = json.load(f)
    else:
        # Try to parse as JSON
        try:
            data = json.loads(input_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}")

    # Handle GeoJSON format
    if isinstance(data, dict):
        if data.get('type') == 'Polygon':
            coords = data['coordinates'][0]
            geom = shape(data)
        elif data.get('type') == 'Feature' and data.get('geometry', {}).get('type') == 'Polygon':
            coords = data['geometry']['coordinates'][0]
            geom = shape(data['geometry'])
        elif data.get('type') == 'MultiPolygon':
            geom = shape(data)
            coords = None
        elif 'coordinates' in data and isinstance(data['coordinates'], list):
            coords = data['coordinates'][0] if isinstance(data['coordinates'][0], list) else data['coordinates']
            geom = {'type': 'Polygon', 'coordinates': [coords]}
            geom = shape(geom)
        else:
            raise ValueError("Unknown GeoJSON format")
    elif isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], list) and len(data[0]) == 2:
            coords = data
            geom = {'type': 'Polygon', 'coordinates': [coords]}
            geom = shape(geom)
        else:
            raise ValueError("Expected list of [lon, lat] pairs")
    else:
        raise ValueError("Invalid input format")

    if coords:
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        bounds = (min(lons), min(lats), max(lons), max(lats))
    else:
        bounds = geom.bounds

    return {
        'type': 'Polygon' if coords else 'MultiPolygon',
        'coordinates': coords,
        'bounds': bounds,
        'geometry': geom
    }


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


def rasterize_soil_map(soil_gdf, padded_bounds, target_resolution=5):
    """Rasterize soil polygons to GeoTIFF."""
    import rasterio
    from rasterio.transform import from_bounds

    minx, miny, maxx, maxy = padded_bounds
    
    # Calculate dimensions
    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, abs(np.cos(np.radians(mid_lat)))))
    
    width = int(np.ceil((maxx - minx) / (target_resolution * deg_per_m_lon)))
    height = int(np.ceil((maxy - miny) / (target_resolution * deg_per_m_lat)))
    
    width = max(64, width)
    height = max(64, height)
    
    transform = from_bounds(minx, miny, maxx, maxy, width, height)
    
    # Create label mapping (mukey -> sequential integer)
    unique_mukeys = soil_gdf['mukey'].unique()
    label_map = {mukey: i + 1 for i, mukey in enumerate(unique_mukeys)}
    reverse_map = {v: k for k, v in label_map.items()}
    
    # Rasterize
    shapes = [(row['geometry'], label_map[str(row['mukey'])]) for _, row in soil_gdf.iterrows()]
    
    raster = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=True
    )
    
    return raster, transform, label_map, reverse_map


def save_soil_geotiff(output_path, data, transform, crs="EPSG:4326", nodata=0):
    """Save soil label GeoTIFF."""
    import rasterio

    height, width = data.shape

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "transform": transform,
        "crs": crs,
        "nodata": nodata,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data, 1)


def generate_soil_raster(polygon_data, output_dir, padding=0.15, target_resolution=5, field_id=None):
    """
    Generate soil raster from polygon.

    Args:
        polygon_data: dict from parse_polygon_input()
        output_dir: Path to output directory
        padding: Padding fraction (e.g., 0.15 for 15%)
        target_resolution: Target resolution in meters
        field_id: Optional field ID for output filenames

    Returns:
        dict with paths and soil definitions
    """
    geometry = polygon_data['geometry']
    padded_bounds = calculate_padded_bounds(polygon_data['bounds'], padding)
    
    if field_id is None:
        minx, miny, maxx, maxy = polygon_data['bounds']
        field_id = f"polygon_{int(minx*1000)}_{int(miny*1000)}"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"  Querying NRCS Soil Data Access API...")
    
    # Get mukeys
    print(f"  Getting mukeys for polygon...")
    mukeys = get_mukeys_for_geometry(geometry)
    
    if not mukeys:
        raise RuntimeError("No SSURGO soil data found for the requested area")
    
    print(f"  Found {len(mukeys)} soil map units")
    
    # Get soil properties
    print(f"  Getting soil properties...")
    properties = get_soil_properties(mukeys)
    print(f"  Retrieved properties for {len(properties)} map units")
    
    # Get polygon geometries
    print(f"  Getting polygon geometries...")
    polygons = get_soil_polygons(geometry, mukeys)
    print(f"  Retrieved {len(polygons)} soil polygons")
    
    if not polygons:
        raise RuntimeError("Could not retrieve soil polygon geometries")
    
    # Create GeoDataFrame
    soil_gdf = gpd.GeoDataFrame(polygons, crs="EPSG:4326")
    
    # Clip to padded bounds
    from shapely.geometry import box
    clipGeom = box(*padded_bounds)
    soil_gdf['geometry'] = soil_gdf['geometry'].intersection(clipGeom)
    soil_gdf = soil_gdf[~soil_gdf.is_empty]
    
    if len(soil_gdf) == 0:
        raise RuntimeError("No valid soil polygons after clipping")
    
    print(f"  Rasterizing {len(soil_gdf)} soil polygons...")
    
    # Rasterize
    raster, transform, label_map, reverse_map = rasterize_soil_map(
        soil_gdf, padded_bounds, target_resolution
    )
    
    print(f"  Raster dimensions: {raster.shape[1]}x{raster.shape[0]}")
    
    # Create soil definitions JSON
    soil_definitions = {}
    for label, mukey in reverse_map.items():
        if mukey in properties:
            prop = properties[mukey]
            soil_definitions[str(label)] = {
                "mukey": prop["mukey"],
                "muname": prop["muname"],
                "comppct_r": prop["comppct_r"],
                "compname": prop["compname"],
                "drainagecl": prop["drainagecl"],
                "horizon_top_cm": prop["hzdept_r"],
                "horizon_bottom_cm": prop["hzdepb_r"],
                "om_pct": prop["om_r"],
                "ph": prop["ph1to1h2o_r"],
                "clay_pct": prop["claytotal_r"],
                "sand_pct": prop["sandtotal_r"],
                "silt_pct": prop["silttotal_r"],
                "cec": prop["cec7_r"],
                "awc": prop["awc_r"],
            }
    
    # Save GeoTIFF
    tif_path = output_dir / f"{field_id}_soil.tif"
    print(f"  Saving {tif_path}...")
    save_soil_geotiff(tif_path, raster, transform)
    
    # Save labels JSON
    labels_path = output_dir / f"{field_id}_soil_labels.json"
    print(f"  Saving {labels_path}...")
    
    # Create output JSON with label -> definition mapping
    output_json = {
        "label_to_mukey": {str(k): v for k, v in reverse_map.items()},
        "soil_definitions": soil_definitions,
        "bounds": list(padded_bounds),
        "resolution_m": target_resolution,
    }
    
    with open(labels_path, 'w') as f:
        json.dump(output_json, f, indent=2)
    
    return {
        'geotiff': str(tif_path),
        'labels_json': str(labels_path),
        'num_soil_units': len(soil_definitions),
        'bounds': padded_bounds,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate SSURGO soil raster from lat/lon polygon coordinates"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Polygon as GeoJSON string, simple [lon,lat] list, or path to .geojson file",
    )
    parser.add_argument(
        "--output-dir",
        default="soil_rasters",
        help="Output directory (default: soil_rasters)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.15,
        help="Padding around polygon bounds as fraction (default: 0.15 = 15%%)",
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
        help="Field ID for output filenames (default: auto-generated)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("SSURGO Soil Raster Generation")
    print("=" * 60)
    print(f"Input: {args.input[:100]}{'...' if len(args.input) > 100 else ''}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m")
    print("-" * 60)

    try:
        # Parse input
        print("Parsing input polygon...")
        polygon_data = parse_polygon_input(args.input)
        bounds = polygon_data['bounds']
        print(f"  Bounds: {bounds[0]:.6f}, {bounds[1]:.6f} to {bounds[2]:.6f}, {bounds[3]:.6f}")

        # Generate soil raster
        result = generate_soil_raster(
            polygon_data,
            args.output_dir,
            padding=args.padding,
            target_resolution=args.resolution,
            field_id=args.field_id,
        )

        print("-" * 60)
        print("Generated files:")
        print(f"  GeoTIFF: {result['geotiff']}")
        print(f"  Labels JSON: {result['labels_json']}")
        print(f"\n  Soil map units found: {result['num_soil_units']}")
        print("=" * 60)
        print("Done!")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
