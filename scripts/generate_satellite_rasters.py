#!/usr/bin/env python3
"""
Generate per-field satellite vegetation index rasters using Copernicus Process API.

Generates raw Float32 GeoTIFFs with actual vegetation index values.
"""

import argparse
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from rasterio.transform import from_bounds

# Configuration
INPUT_GEOJSON = Path("data/assignment-03/fields_complete.geojson")
OUTPUT_DIR = Path("data/assignment-03/satellite")
METADATA_FILE = Path("data/assignment-03/satellite_dates.json")

# Copernicus credentials
CLIENT_ID = "sh-b7c9d9d1-9963-4f33-a0aa-0c8cffa4a246"
CLIENT_SECRET = "cMwfrjg1uUVTUrXepNpR8pgiOiHKjDcL"

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/search"

# Default date range (fallback)
DEFAULT_DATE_START = "2024-04-01"
DEFAULT_DATE_END = "2024-09-30"

# Indices to compute
INDICES = ["ndvi", "msavi", "evi", "ndmi"]

# Search parameters (adjustable via CLI)
CLOUD_THRESHOLD = 30
SEARCH_WINDOW_DAYS = 30


def get_oauth_token():
    """Get OAuth token from Copernicus."""
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    response = requests.post(TOKEN_URL, data=data, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def find_closest_scene(token, bounds, target_date_str):
    """Search for closest scene with acceptable cloud cover to target date."""
    minx, miny, maxx, maxy = bounds
    
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    from_date = (target_date - timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y-%m-%d")
    to_date = (target_date + timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y-%m-%d")
    
    search_body = {
        "bbox": [minx, miny, maxx, maxy],
        "datetime": f"{from_date}/{to_date}",
        "collections": ["sentinel-2-l2a"],
        "limit": 100,
        "query": {
            "eo:cloud_cover": {
                "lte": CLOUD_THRESHOLD
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    
    try:
        response = requests.post(CATALOG_URL, json=search_body, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"    Catalog search error: HTTP {response.status_code}")
            return None
        
        results = response.json()
        features = results.get("features", [])
        
        if not features:
            # Expand search window as fallback
            expanded_from = (target_date - timedelta(days=60)).strftime("%Y-%m-%d")
            expanded_to = (target_date + timedelta(days=60)).strftime("%Y-%m-%d")
            search_body["datetime"] = f"{expanded_from}/{expanded_to}"
            
            response = requests.post(CATALOG_URL, json=search_body, headers=headers, timeout=30)
            if response.status_code == 200:
                results = response.json()
                features = results.get("features", [])
        
        if not features:
            print(f"    No scenes found within search window")
            return None
        
        # Find closest date to target
        target_ts = target_date.timestamp()
        closest = None
        min_diff = float('inf')
        
        for feat in features:
            date_str = feat["properties"]["datetime"]
            # Parse date (handle both formats)
            if "T" in date_str:
                scene_date = datetime.strptime(date_str.split("T")[0], "%Y-%m-%d")
            else:
                scene_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            
            diff = abs((scene_date - target_date).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest = {
                    "date": scene_date.strftime("%Y-%m-%d"),
                    "cloud_cover": feat["properties"].get("eo:cloud_cover", 0),
                    "id": feat["id"]
                }
        
        if closest:
            print(f"    Found scene: {closest['date']} (cloud cover: {closest['cloud_cover']}%)")
        
        return closest
        
    except Exception as e:
        print(f"    Catalog search exception: {e}")
        return None


def create_evalscript(metric_name):
    """Create evalscript for a given metric."""
    formulas = {
        "ndvi": "(B08 - B04) / (B08 + B04)",
        "msavi": "(2 * B08 + 1 - ((2 * B08 + 1) ** 2 - 8 * (B08 - B04)) ** 0.5) / 2",
        "evi": "2.5 * (B08 - B04) / (B08 + 2.4 * B04 + 1)",
        "ndmi": "(B08 - B11) / (B08 + B11)",
    }
    formula = formulas.get(metric_name, formulas["ndvi"])
    
    return f"""//VERSION=3
function setup() {{
    return {{
        input: [{{ bands: ['B04', 'B08', 'B11', 'dataMask'] }}],
        output: [{{ id: 'metric', bands: 1, sampleType: 'FLOAT32' }}]
    }};
}}
function evaluatePixel(sample) {{
    var B04 = sample.B04;
    var B08 = sample.B08;
    var B11 = sample.B11;
    var metric = 0;
    metric = {formula};
    return {{ metric: [sample.dataMask === 0 ? NaN : metric] }};
}}"""


def degrees_to_meters(lat_min, lat_max, lon_min, lon_max):
    """Convert bounding box from degrees to meters using haversine."""
    lat_center = (lat_min + lat_max) / 2
    
    meters_per_degree_lat = 111320
    meters_per_degree_lon = 111320 * math.cos(math.radians(lat_center))
    
    width_m = (lon_max - lon_min) * meters_per_degree_lon
    height_m = (lat_max - lat_min) * meters_per_degree_lat
    
    return width_m, height_m


def process_field_for_index(token, field_id, field_bounds, metric_name, output_path, target_date):
    """Process a single field for a single metric using Process API."""
    minx, miny, maxx, maxy = field_bounds
    
    width_m, height_m = degrees_to_meters(miny, maxy, minx, maxx)
    
    dx = (maxx - minx) * 0.1
    dy = (maxy - miny) * 0.1
    padded_minx = minx - dx
    padded_miny = miny - dy
    padded_maxx = maxx + dx
    padded_maxy = maxy + dy
    
    padded_width_m, padded_height_m = degrees_to_meters(padded_miny, padded_maxy, padded_minx, padded_maxx)
    
    width = max(5, round(padded_width_m / 10))
    height = max(5, round(padded_height_m / 10))
    
    evalscript = create_evalscript(metric_name)
    
    request_body = {
        "input": {
            "bounds": {
                "bbox": [padded_minx, padded_miny, padded_maxx, padded_maxy],
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": f"{target_date}T00:00:00Z",
                        "to": f"{target_date}T23:59:59Z",
                    },
                },
            }],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "metric", "format": {"type": "image/tiff"}}],
        },
        "evalscript": evalscript,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "image/tiff",
        "Authorization": f"Bearer {token}",
    }
    
    try:
        response = requests.post(PROCESS_URL, json=request_body, headers=headers, timeout=60)
        
        if response.status_code != 200:
            print(f"    Error: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"    Error details: {error_data}")
            except:
                print(f"    Error response: {response.text[:200]}")
            return None
        
        if len(response.content) < 1000:
            print(f"    Error response: {response.content[:200]}")
            return None
        
        from rasterio.io import MemoryFile
        
        try:
            with MemoryFile(response.content) as memfile:
                with memfile.open() as src:
                    data_array = src.read(1).astype(np.float32)
                    tiff_bounds = src.bounds
        except Exception as e:
            print(f"    TIFF decode error: {e}")
            return None
        
        valid = data_array[~np.isnan(data_array)]
        if len(valid) == 0:
            print(f"    No valid data")
            return None
            
        vmin, vmax = float(np.min(valid)), float(np.max(valid))
        
        transform = from_bounds(padded_minx, padded_miny, padded_maxx, padded_maxy, data_array.shape[1], data_array.shape[0])
        
        profile = {
            "driver": "GTiff",
            "height": data_array.shape[0],
            "width": data_array.shape[1],
            "count": 1,
            "dtype": "float32",
            "transform": transform,
            "crs": "EPSG:4326",
            "nodata": "nan",
        }
        
        import rasterio
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(data_array, 1)
        
        return {"vmin": vmin, "vmax": vmax, "pixels": len(valid)}
        
    except Exception as e:
        print(f"    Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_field(token, field_id, field_bounds, target_date, metadata):
    """Process a single field for all metrics."""
    results = {}
    
    scene_info = find_closest_scene(token, field_bounds, target_date)
    
    if not scene_info:
        print(f"    No suitable scene found, using target date: {target_date}")
        actual_date = target_date
        cloud_cover = None
    else:
        actual_date = scene_info["date"]
        cloud_cover = scene_info["cloud_cover"]
    
    metadata[field_id] = {
        "date": actual_date,
        "cloud_cover": cloud_cover
    }
    
    for metric_name in INDICES:
        output_path = OUTPUT_DIR / f"{field_id}_{metric_name}.tif"
        print(f"    Computing {metric_name.upper()}...")
        
        result = process_field_for_index(token, field_id, field_bounds, metric_name, output_path, actual_date)
        
        if result:
            print(f"    {metric_name.upper()}: {result['vmin']:.3f} to {result['vmax']:.3f} ({result['pixels']} pixels)")
            results[metric_name] = result
        else:
            print(f"    {metric_name.upper()} failed")
    
    return results


def load_metadata():
    """Load existing metadata or create new."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_metadata(metadata):
    """Save metadata to JSON file."""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def main():
    global CLOUD_THRESHOLD
    
    parser = argparse.ArgumentParser(description='Generate satellite vegetation index rasters')
    parser.add_argument('--date', type=str, default=None,
                        help='Target date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--cloud-threshold', type=int, default=30,
                        help='Max cloud cover percentage (default: 30)')
    args = parser.parse_args()
    
    CLOUD_THRESHOLD = args.cloud_threshold
    
    target_date = args.date or datetime.now().strftime('%Y-%m-%d')
    
    print(f"Target date: {target_date}")
    print(f"Cloud threshold: {CLOUD_THRESHOLD}%")
    print(f"Search window: ±{SEARCH_WINDOW_DAYS} days")
    
    print(f"\nLoading {INPUT_GEOJSON}...")
    gdf = gpd.read_file(INPUT_GEOJSON)
    
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf_wgs84 = gdf.to_crs("EPSG:4326")
    else:
        gdf_wgs84 = gdf
    
    print(f"Getting OAuth token...")
    token = get_oauth_token()
    print(f"Token obtained")
    
    metadata = load_metadata()
    
    print(f"\nProcessing {len(gdf_wgs84)} fields...")
    print(f"Target date: {target_date}")
    
    success = 0
    errors = 0
    
    for idx, (_, field) in enumerate(gdf_wgs84.iterrows()):
        field_id = field["field_id"]
        bounds = gdf_wgs84.geometry.iloc[idx].bounds
        
        print(f"\n[{idx + 1}/{len(gdf_wgs84)}] {field_id}...")
        
        result = process_field(token, field_id, bounds, target_date, metadata)
        
        if result:
            success += 1
        else:
            errors += 1
    
    save_metadata(metadata)
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Fields processed: {success}")
    print(f"Fields failed: {errors}")
    print(f"Rasters saved to: {OUTPUT_DIR}")
    print(f"Metadata saved to: {METADATA_FILE}")
    print("Done!")


if __name__ == "__main__":
    main()
