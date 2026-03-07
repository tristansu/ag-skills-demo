#!/usr/bin/env python3
"""
Generate Slope and Aspect Data from DEM Rasters.

This script:
1. Loads existing DEM TIF files for each field
2. Computes slope (gradient) using GDAL
3. Computes aspect (direction) using GDAL
4. Aggregates to field-level statistics
5. Saves to CSV for analysis

Usage:
    python scripts/generate_slope_aspect.py

Output:
    data/assignment-03/field_slope_aspect.csv

Requirements:
    rasterio, numpy, pandas
"""

import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd

DEM_DIR = Path("docs/assignment-03/dem")
OUTPUT_PATH = Path("data/assignment-03/field_slope_aspect.csv")


def install_deps():
    """Install required packages."""
    packages = ["rasterio", "numpy", "pandas"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def calculate_slope_aspect(dem_path):
    """Calculate slope and aspect from a DEM raster using GDAL."""
    from osgeo import gdal
    
    gdal.UseExceptions()
    
    dataset = gdal.Open(str(dem_path))
    if dataset is None:
        raise RuntimeError(f"Could not open {dem_path}")
    
    band = dataset.GetRasterBand(1)
    elevation = band.ReadAsArray()
    
    no_data = band.GetNoDataValue()
    if no_data is not None:
        elevation = np.where(elevation == no_data, np.nan, elevation)
    
    geotransform = dataset.GetGeoTransform()
    pixel_width = abs(geotransform[1])
    pixel_height = abs(geotransform[5])
    
    elevation = np.nan_to_num(elevation, nan=0)
    
    dy, dx = np.gradient(elevation, pixel_height, pixel_width)
    
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    
    aspect_rad = np.arctan2(dx, -dy)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)
    aspect_deg = np.where(slope_deg < 0.1, np.nan, aspect_deg)
    
    slope_clean = slope_deg[~np.isnan(slope_deg)]
    aspect_clean = aspect_deg[~np.isnan(aspect_deg)]
    
    if len(slope_clean) == 0:
        return {
            'slope_mean': np.nan,
            'slope_min': np.nan,
            'slope_max': np.nan,
            'slope_std': np.nan,
            'aspect_mean': np.nan
        }
    
    return {
        'slope_mean': float(np.mean(slope_clean)),
        'slope_min': float(np.min(slope_clean)),
        'slope_max': float(np.max(slope_clean)),
        'slope_std': float(np.std(slope_clean)),
        'aspect_mean': float(np.mean(aspect_clean))
    }


def get_field_ids():
    """Get list of field IDs from DEM files."""
    dem_files = sorted(DEM_DIR.glob("dem_WV_AG_*.tif"))
    field_ids = []
    for f in dem_files:
        field_id = f.stem.replace("dem_", "")
        field_ids.append(field_id)
    return field_ids


def main():
    """Main function to process all DEMs."""
    print("=" * 60)
    print("Slope & Aspect Generation from DEM")
    print("=" * 60)
    
    try:
        from osgeo import gdal
    except ImportError:
        print("GDAL not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdal"], check=True)
        from osgeo import gdal
    
    output_dir = OUTPUT_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    field_ids = get_field_ids()
    print(f"Found {len(field_ids)} DEM files")
    
    results = []
    for i, field_id in enumerate(field_ids):
        dem_path = DEM_DIR / f"dem_{field_id}.tif"
        
        if not dem_path.exists():
            print(f"  {field_id}: DEM file not found, skipping")
            continue
        
        print(f"  Processing {field_id} ({i+1}/{len(field_ids)})...", end=" ")
        
        try:
            stats = calculate_slope_aspect(dem_path)
            stats['field_id'] = field_id
            results.append(stats)
            print(f"slope={stats['slope_mean']:.2f}°, aspect={stats['aspect_mean']:.1f}°")
        except Exception as e:
            print(f"Error: {e}")
    
    if not results:
        print("No data processed!")
        return
    
    df = pd.DataFrame(results)
    cols = ['field_id', 'slope_mean', 'slope_min', 'slope_max', 'slope_std', 'aspect_mean']
    df = df[cols]
    
    df.to_csv(OUTPUT_PATH, index=False)
    
    print(f"\n✅ Saved {len(df)} records to {OUTPUT_PATH}")
    print(f"\nSummary Statistics:")
    print(df.describe())
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
