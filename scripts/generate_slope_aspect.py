#!/usr/bin/env python3
"""
Generate Slope and Aspect Data and PNG Overlays from DEM.

This script:
1. Loads field boundaries from GeoJSON
2. Fetches elevation data from USGS 3DEP with 20% padding (same as DEM PNG)
3. Computes slope (gradient) and aspect (direction) from raw elevation
4. Saves PNG overlays with colormaps
5. Generates CSV statistics
6. Creates slope_bounds.json for web map alignment

Usage:
    python scripts/generate_slope_aspect.py --generate-pngs

Output:
    docs/assignment-03/dem/slope_{field_id}.png
    docs/assignment-03/dem/aspect_{field_id}.png
    docs/assignment-03/dem/slope_bounds.json
    data/assignment-03/field_slope_aspect.csv

Requirements:
    rasterio, numpy, pandas, matplotlib, requests, geopandas
"""

import argparse
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from matplotlib import cm
from rasterio.io import MemoryFile
from PIL import Image

INPUT_GEOJSON = Path("docs/assignment-03/fields_complete_wgs84.geojson")
DEM_DIR = Path("docs/assignment-03/dem")
OUTPUT_PATH = Path("data/assignment-03/field_slope_aspect.csv")

USGS_3DEP_EXPORT = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
)

TARGET_RES_M = 10


def fetch_usgs_elevation(bbox, target_width, target_height):
    """Fetch elevation from USGS 3DEP with specific dimensions to preserve aspect ratio."""
    minx, miny, maxx, maxy = bbox

    params = {
        "f": "image",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{target_width},{target_height}",
        "format": "tiff",
        "pixelType": "F32",
        "noData": "-9999",
        "interpolation": "RSP_BilinearInterpolation",
    }

    try:
        r = requests.get(USGS_3DEP_EXPORT, params=params, timeout=120)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if ctype.startswith("image/") or "tiff" in ctype:
            return r.content
        return None
    except Exception as e:
        print(f"    Error fetching: {e}")
        return None


def get_viridis_colormap():
    """Return viridis colormap as RGB array."""
    cmap = cm.get_cmap("viridis", 256)
    return cmap(np.linspace(0, 1, 256))[:, :3]


def get_hsv_colormap():
    """Return HSV-style cyclic colormap for aspect (0-360°)."""
    colors = []
    for i in range(256):
        hue = i / 256.0
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        colors.append([r, g, b])
    return np.array(colors)


def apply_colormap(data, colormap, vmin, vmax):
    """Apply colormap to data array."""
    if data.ndim > 2:
        data = data.squeeze()
    
    valid = ~np.isnan(data)
    normalized = np.zeros_like(data)
    normalized[valid] = np.clip((data[valid] - vmin) / (vmax - vmin), 0, 1)
    indices = np.clip((normalized * 255).astype(int), 0, 255)
    
    result = colormap[indices] * 255
    return result.astype(np.uint8)


def calculate_slope_aspect(elevation, transform, bounds):
    """Calculate slope and aspect from elevation array."""
    nodata = -9999
    
    elevation_clean = np.where(elevation == nodata, np.nan, elevation)
    
    pixel_width_deg = abs(transform.a)
    pixel_height_deg = abs(transform.e)
    lat = (bounds.bottom + bounds.top) / 2
    meters_per_deg_lon = 111320 * math.cos(math.radians(lat))
    
    pixel_width = pixel_width_deg * meters_per_deg_lon
    pixel_height = pixel_height_deg * 111320
    
    dy, dx = np.gradient(elevation_clean, pixel_height, pixel_width)
    
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    
    aspect_rad = np.arctan2(dx, -dy)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)
    aspect_deg = np.where(slope_deg < 0.1, np.nan, aspect_deg)
    
    return slope_deg, aspect_deg


def save_png(field_id, data, colormap, vmin, vmax, output_path):
    """Save data as colored PNG with transparency for NaN."""
    data_2d = data.squeeze()
    
    img = apply_colormap(data_2d, colormap, vmin, vmax)
    
    valid = ~np.isnan(data_2d)
    
    h, w = data_2d.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = img
    rgba[:, :, 3] = (valid * 255).astype(np.uint8)
    
    pil_img = Image.fromarray(rgba, 'RGBA')
    pil_img.save(output_path)


def process_field(field_id, field_bounds_wgs84):
    """Process a single field: fetch DEM, calculate slope/aspect, save PNGs."""
    dx = (field_bounds_wgs84[2] - field_bounds_wgs84[0]) * 0.2
    dy = (field_bounds_wgs84[3] - field_bounds_wgs84[1]) * 0.2
    padded_bbox = (
        field_bounds_wgs84[0] - dx,
        field_bounds_wgs84[1] - dy,
        field_bounds_wgs84[2] + dx,
        field_bounds_wgs84[3] + dy,
    )
    
    minx, miny, maxx, maxy = padded_bbox
    mid_lat = (miny + maxy) / 2
    
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, math.cos(math.radians(mid_lat))))
    
    res_deg = TARGET_RES_M * deg_per_m_lon
    lon_range = maxx - minx
    lat_range = maxy - miny
    
    target_width = max(64, int(math.ceil(lon_range / res_deg)))
    target_height = max(64, int(math.ceil(lat_range / res_deg)))
    
    tif_bytes = fetch_usgs_elevation(padded_bbox, target_width, target_height)
    
    if tif_bytes is None:
        print(f"    Failed to fetch elevation")
        return None
    
    try:
        with MemoryFile(tif_bytes) as memfile:
            with memfile.open() as src:
                elevation = src.read(1)
                bounds = src.bounds
                
                valid = elevation[elevation != -9999]
                if len(valid) == 0:
                    print(f"    No valid elevation data")
                    return None
                
                slope_deg, aspect_deg = calculate_slope_aspect(
                    elevation, src.transform, bounds
                )
                
                slope_clean = slope_deg[~np.isnan(slope_deg)]
                aspect_clean = aspect_deg[~np.isnan(aspect_deg)]
                
                if len(slope_clean) == 0:
                    print(f"    No valid slope data")
                    return None
                
                stats = {
                    'slope_mean': float(np.mean(slope_clean)),
                    'slope_min': float(np.min(slope_clean)),
                    'slope_max': float(np.max(slope_clean)),
                    'slope_std': float(np.std(slope_clean)),
                    'aspect_mean': float(np.mean(aspect_clean)) if len(aspect_clean) > 0 else np.nan,
                }
                
                viridis = get_viridis_colormap()
                hsv = get_hsv_colormap()
                
                save_png(field_id, slope_deg, viridis, 0, 90, DEM_DIR / f"slope_{field_id}.png")
                save_png(field_id, aspect_deg, hsv, 0, 360, DEM_DIR / f"aspect_{field_id}.png")
                
                return {
                    'stats': stats,
                    'bounds': [bounds.left, bounds.bottom, bounds.right, bounds.top],
                    'shape': (elevation.shape[1], elevation.shape[0]),
                }
                
    except Exception as e:
        print(f"    Error processing: {e}")
        import traceback
        traceback.print_exc()
        return None


def main(generate_pngs=False):
    """Main function to process all fields."""
    print("=" * 60)
    print("Slope & Aspect Generation from USGS 3DEP")
    print("=" * 60)
    
    DEM_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading {INPUT_GEOJSON}...")
    gdf = gpd.read_file(INPUT_GEOJSON)
    
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf_wgs84 = gdf.to_crs("EPSG:4326")
    else:
        gdf_wgs84 = gdf
    
    print(f"Processing {len(gdf_wgs84)} fields...")
    
    results = []
    bounds_data = {}
    success = 0
    errors = 0
    
    for idx, (_, field) in enumerate(gdf_wgs84.iterrows()):
        field_id = field["field_id"]
        bounds = gdf_wgs84.geometry.iloc[idx].bounds
        
        print(f"  [{idx + 1}/{len(gdf_wgs84)}] {field_id}...", end=" ")
        
        if generate_pngs:
            result = process_field(field_id, bounds)
            
            if result:
                success += 1
                stats = result['stats']
                stats['field_id'] = field_id
                results.append(stats)
                bounds_data[field_id] = result['bounds']
                print(f"slope={stats['slope_mean']:.2f}°, aspect={stats['aspect_mean']:.1f}°")
            else:
                errors += 1
                print("FAILED")
        else:
            results.append({'field_id': field_id})
            print("skipped (PNG generation disabled)")
    
    if not results:
        print("No data processed!")
        return
    
    import pandas as pd
    df = pd.DataFrame(results)
    
    if 'slope_mean' in df.columns:
        cols = ['field_id', 'slope_mean', 'slope_min', 'slope_max', 'slope_std', 'aspect_mean']
        df = df[cols]
        df.to_csv(OUTPUT_PATH, index=False)
        
        print(f"\n✅ Saved {len(df)} records to {OUTPUT_PATH}")
        print(f"\nSummary Statistics:")
        print(df.describe())
    
    if generate_pngs and bounds_data:
        bounds_file = DEM_DIR / "slope_bounds.json"
        with open(bounds_file, 'w') as f:
            json.dump(bounds_data, f, indent=2)
        print(f"\n✅ Saved bounds to {bounds_file}")
        print(f"   Created {len(bounds_data)} slope PNGs")
        print(f"   Created {len(bounds_data)} aspect PNGs")
    
    print(f"\n=== Summary ===")
    print(f"Success: {success}, Errors: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate slope and aspect data from USGS')
    parser.add_argument('--generate-pngs', action='store_true', 
                        help='Generate PNG overlays for web map')
    args = parser.parse_args()
    
    main(generate_pngs=args.generate_pngs)
