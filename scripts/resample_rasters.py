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

def resample_raster(input_path, output_path, target_res=TARGET_RESOLUTION, force_resampling=None):
    """Resample a single raster to target resolution.
    
    Args:
        input_path: Path to input raster
        output_path: Path to output raster
        target_res: Target resolution in meters
        force_resampling: Override resampling method detection ('bilinear', 'nearest', or None for auto)
    """
    
    # Determine resampling method based on data type
    # Aspect is angular (0-360) - use nearest-neighbor to avoid interpolation artifacts
    # All other data types use bilinear
    filename = input_path.name.lower()
    if force_resampling:
        resample_method = getattr(Resampling, force_resampling)
    elif '_aspect.' in filename:
        resample_method = Resampling.nearest
    else:
        resample_method = Resampling.bilinear
    
    with rasterio.open(input_path) as src:
        src_crs = src.crs
        
        transform, width, height = calculate_default_transform(
            src_crs, TARGET_CRS, src.width, src.height, *src.bounds
        )
        
        mid_lat = (src.bounds.top + src.bounds.bottom) / 2
        # At latitude lat, 1 meter = 1/111320 degrees in lat, 1/(111320*cos(lat)) degrees in lon
        deg_per_m_lat = 1.0 / 111_320.0
        deg_per_m_lon = 1.0 / (111320.0 * max(0.01, np.cos(np.radians(mid_lat))))
        
        # 10m pixel = 10 * deg_per_m degrees
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
            resampling=resample_method,
        )
        
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(resampled, 1)
        
        return target_width, target_height, resample_method.name

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
            w, h, method = resample_raster(tif_path, output_path)
            print(f"  {output_path.name}: {w}x{h} ({method})")
        except Exception as e:
            print(f"  Error processing {tif_path.name}: {e}")
    
    print(f"\nResampling soil property rasters...")
    soil_files = list(INPUT_SOIL_PROPS.glob("*.tif"))
    
    for tif_path in soil_files:
        output_path = OUTPUT_SOIL_PROPS / tif_path.name
        
        if output_path.exists():
            continue
        
        try:
            w, h, method = resample_raster(tif_path, output_path)
            print(f"  {output_path.name}: {w}x{h} ({method})")
        except Exception as e:
            print(f"  Error processing {tif_path.name}: {e}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
