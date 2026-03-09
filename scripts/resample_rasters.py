#!/usr/bin/env python3
"""
Resample rasters to target resolution.

Since satellite imagery is not available (Copernicus API down), this script
resamples terrain and soil property rasters to 10m resolution to match the
expected satellite resolution.

Usage:
    python scripts/resample_rasters.py
"""

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pathlib import Path

TARGET_RESOLUTION = 10  # meters
TARGET_CRS = "EPSG:4326"  # WGS84

INPUT_TERRAIN = Path("data/terrain")
INPUT_SOIL_PROPS = Path("data/soil_properties")
OUTPUT_TERRAIN = Path("data/terrain_resampled")
OUTPUT_SOIL_PROPS = Path("data/soil_properties_resampled")

OUTPUT_TERRAIN.mkdir(exist_ok=True)
OUTPUT_SOIL_PROPS.mkdir(exist_ok=True)

def resample_raster(input_path, output_path, target_res=TARGET_RESOLUTION):
    """Resample a single raster to target resolution."""
    
    with rasterio.open(input_path) as src:
        src_crs = src.crs
        
        transform, width, height = calculate_default_transform(
            src_crs, TARGET_CRS, src.width, src.height, *src.bounds
        )
        
        mid_lat = (src.bounds.top + src.bounds.bottom) / 2
        deg_per_m_lat = 1.0 / 111_320.0
        deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, np.cos(np.radians(mid_lat))))
        
        target_width = int((src.bounds.right - src.bounds.left) / (target_res * deg_per_m_lon))
        target_height = int((src.bounds.top - src.bounds.bottom) / (target_res * deg_per_m_lat))
        
        target_width = max(10, target_width)
        target_height = max(10, target_height)
        
        target_transform = rasterio.transform.from_bounds(
            src.bounds.left, src.bounds.bottom,
            src.bounds.right, src.bounds.top,
            target_width, target_height
        )
        
        profile = src.profile.copy()
        profile.update({
            "crs": TARGET_CRS,
            "transform": target_transform,
            "width": target_width,
            "height": target_height,
        })
        
        data = src.read(1)
        
        resampled = np.zeros((target_height, target_width), dtype=src.dtypes[0])
        
        reproject(
            source=data,
            destination=resampled,
            src_transform=src.transform,
            src_crs=src_crs,
            dst_transform=target_transform,
            dst_crs=TARGET_CRS,
            resampling=Resampling.bilinear,
        )
        
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(resampled, 1)
        
        return target_width, target_height

def main():
    print("Resampling terrain rasters...")
    terrain_files = list(INPUT_TERRAIN.glob("*.tif"))
    
    for tif_path in terrain_files:
        field_id = tif_path.stem.rsplit('_', 1)[0]
        metric = tif_path.stem.rsplit('_', 1)[-1]
        output_path = OUTPUT_TERRAIN / f"{field_id}_{metric}.tif"
        
        if output_path.exists():
            continue
        
        try:
            w, h = resample_raster(tif_path, output_path)
            print(f"  {output_path.name}: {w}x{h}")
        except Exception as e:
            print(f"  Error processing {tif_path.name}: {e}")
    
    print(f"\nResampling soil property rasters...")
    soil_files = list(INPUT_SOIL_PROPS.glob("*.tif"))
    
    for tif_path in soil_files:
        output_path = OUTPUT_SOIL_PROPS / tif_path.name
        
        if output_path.exists():
            continue
        
        try:
            w, h = resample_raster(tif_path, output_path)
            print(f"  {output_path.name}: {w}x{h}")
        except Exception as e:
            print(f"  Error processing {tif_path.name}: {e}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
