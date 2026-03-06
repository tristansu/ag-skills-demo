#!/usr/bin/env python3
"""
Generate per-field satellite vegetation index rasters using Copernicus Process API.

Generates raw Float32 GeoTIFFs with actual vegetation index values.
"""

import json
import math
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from rasterio.transform import from_bounds

# Configuration
INPUT_GEOJSON = Path("data/assignment-03/fields_complete.geojson")
OUTPUT_DIR = Path("data/assignment-03/satellite")

# Copernicus credentials
CLIENT_ID = "sh-b7c9d9d1-9963-4f33-a0aa-0c8cffa4a246"
CLIENT_SECRET = "cMwfrjg1uUVTUrXepNpR8pgiOiHKjDcL"

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

# Date range
DATE_START = "2024-04-01"
DATE_END = "2024-09-30"

# Indices to compute
INDICES = ["ndvi", "msavi", "evi", "ndmi"]


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
    lon_center = (lon_min + lon_max) / 2
    
    lat_range = lat_max - lat_min
    lon_range = lon_max - lon_min
    
    meters_per_degree_lat = 111320
    meters_per_degree_lon = 111320 * math.cos(math.radians(lat_center))
    
    width_m = lon_range * meters_per_degree_lon
    height_m = lat_range * meters_per_degree_lat
    
    return width_m, height_m


def process_field_for_index(token, field_id, field_bounds, metric_name, output_path):
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
                        "from": f"{DATE_START}T00:00:00Z",
                        "to": f"{DATE_END}T23:59:59Z",
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
        
        # Check if response is too small (error message)
        if len(response.content) < 1000:
            print(f"    Error response: {response.content[:200]}")
            return None
        
        # Decode TIFF using rasterio from MemoryFile
        from rasterio.io import MemoryFile
        
        try:
            with MemoryFile(response.content) as memfile:
                with memfile.open() as src:
                    data_array = src.read(1).astype(np.float32)
                    tiff_bounds = src.bounds
        except Exception as e:
            print(f"    TIFF decode error: {e}")
            return None
        
        # Get valid statistics
        valid = data_array[~np.isnan(data_array)]
        if len(valid) == 0:
            print(f"    No valid data")
            return None
            
        vmin, vmax = float(np.min(valid)), float(np.max(valid))
        
        # Save as Float32 GeoTIFF
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


def process_field(token, field_id, field_bounds):
    """Process a single field for all metrics."""
    results = {}
    
    for metric_name in INDICES:
        output_path = OUTPUT_DIR / f"{field_id}_{metric_name}.tif"
        print(f"    Computing {metric_name.upper()}...")
        
        result = process_field_for_index(token, field_id, field_bounds, metric_name, output_path)
        
        if result:
            print(f"    {metric_name.upper()}: {result['vmin']:.3f} to {result['vmax']:.3f} ({result['pixels']} pixels)")
            results[metric_name] = result
        else:
            print(f"    {metric_name.upper()} failed")
    
    return results


def main():
    print(f"Loading {INPUT_GEOJSON}...")
    gdf = gpd.read_file(INPUT_GEOJSON)
    
    # Convert to WGS84 if needed
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf_wgs84 = gdf.to_crs("EPSG:4326")
    else:
        gdf_wgs84 = gdf
    
    print(f"Getting OAuth token...")
    token = get_oauth_token()
    print(f"Token obtained")
    
    print(f"Processing {len(gdf_wgs84)} fields...")
    print(f"Date range: {DATE_START} to {DATE_END}")
    
    success = 0
    errors = 0
    
    for idx, (_, field) in enumerate(gdf_wgs84.iterrows()):
        field_id = field["field_id"]
        bounds = gdf_wgs84.geometry.iloc[idx].bounds  # (minx, miny, maxx, maxy)
        
        print(f"\n[{idx + 1}/{len(gdf_wgs84)}] {field_id}...")
        
        result = process_field(token, field_id, bounds)
        
        if result:
            success += 1
        else:
            errors += 1
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Fields processed: {success}")
    print(f"Fields failed: {errors}")
    print(f"Rasters saved to: {OUTPUT_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()
