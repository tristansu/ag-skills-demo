#!/usr/bin/env python3
"""
Generate Slope and Aspect Data and Overlays from DEM Rasters.

This script:
1. Loads existing DEM TIF files for each field
2. Computes slope (gradient) using rasterio
3. Computes aspect (direction) using rasterio  
4. Aggregates to field-level statistics
5. Optionally generates PNG overlays for web map display
6. Saves to CSV for analysis

Usage:
    # Just CSV output (default):
    python scripts/generate_slope_aspect.py
    
    # Generate CSV + PNG overlays:
    python scripts/generate_slope_aspect.py --generate-pngs

Output:
    data/assignment-03/field_slope_aspect.csv
    docs/assignment-03/dem/slope_{field_id}.png (if --generate-pngs)
    docs/assignment-03/dem/aspect_{field_id}.png (if --generate-pngs)

Requirements:
    rasterio, numpy, pandas, matplotlib
"""

import argparse
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd

DEM_DIR = Path("docs/assignment-03/dem")
OUTPUT_PATH = Path("data/assignment-03/field_slope_aspect.csv")

# Colormaps (similar to generate_dem_png.py)
def get_viridis_colormap():
    """Return viridis colormap as RGB array."""
    import matplotlib.pyplot as plt
    cmap = plt.cm.viridis
    return cmap(np.linspace(0, 1, 256))[:, :3]

def get_hsv_colormap():
    """Return HSV-style cyclic colormap for aspect (0-360°)."""
    # Create a cyclic colormap: red->yellow->green->cyan->blue->magenta->red
    colors = []
    for i in range(256):
        hue = i / 256.0
        # HSV to RGB conversion (simplified)
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        colors.append([r, g, b])
    return np.array(colors)


def apply_colormap(data, colormap, vmin, vmax):
    """Apply colormap to data array."""
    # Ensure 2D
    if data.ndim > 2:
        data = data.squeeze()
    
    # Handle NaN
    data = np.nan_to_num(data, nan=vmin)
    
    normalized = np.clip((data - vmin) / (vmax - vmin), 0, 1)
    indices = np.clip((normalized * 255).astype(int), 0, 255)
    
    # Apply colormap
    result = colormap[indices] * 255
    return result.astype(np.uint8)


def calculate_slope_aspect_with_arrays(dem_path):
    """Calculate slope and aspect from a DEM raster, returning arrays and metadata."""
    import rasterio
    import math
    
    with rasterio.open(dem_path) as dataset:
        elevation = dataset.read(1)
        transform = dataset.transform
        crs = dataset.crs
        bounds = dataset.bounds
        
        nodata = dataset.nodata
        if nodata is not None:
            elevation = np.where(elevation == nodata, np.nan, elevation)
        
        elevation = np.nan_to_num(elevation, nan=0)
        
        # Convert pixel spacing from degrees to meters (DEM is EPSG:4326)
        pixel_width_deg = abs(transform.a)
        pixel_height_deg = abs(transform.e)
        lat = (bounds.bottom + bounds.top) / 2
        meters_per_deg_lon = 111320 * math.cos(math.radians(lat))
        
        pixel_width = pixel_width_deg * meters_per_deg_lon
        pixel_height = pixel_height_deg * 111320
        
        dy, dx = np.gradient(elevation, pixel_height, pixel_width)
        
        slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
        slope_deg = np.degrees(slope_rad)
        
        aspect_rad = np.arctan2(dx, -dy)
        aspect_deg = np.degrees(aspect_rad)
        aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)
        aspect_deg = np.where(slope_deg < 0.1, np.nan, aspect_deg)
        
        return {
            'slope': slope_deg,
            'aspect': aspect_deg,
            'transform': transform,
            'crs': crs,
            'bounds': bounds,
            'nodata': nodata
        }


def calculate_slope_aspect_stats(dem_path):
    """Calculate slope and aspect statistics from a DEM raster using rasterio and numpy."""
    import rasterio
    import math
    
    with rasterio.open(dem_path) as dataset:
        elevation = dataset.read(1)
        transform = dataset.transform
        bounds = dataset.bounds
        
        nodata = dataset.nodata
        if nodata is not None:
            elevation = np.where(elevation == nodata, np.nan, elevation)
        
        elevation = np.nan_to_num(elevation, nan=0)
        
        # Convert pixel spacing from degrees to meters (DEM is EPSG:4326)
        pixel_width_deg = abs(transform.a)
        pixel_height_deg = abs(transform.e)
        lat = (bounds.bottom + bounds.top) / 2
        meters_per_deg_lon = 111320 * math.cos(math.radians(lat))
        
        pixel_width = pixel_width_deg * meters_per_deg_lon
        pixel_height = pixel_height_deg * 111320
        
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


def save_slope_aspect_png(field_id, slope_data, aspect_data, output_dir):
    """Save slope and aspect as colored PNG overlays."""
    from PIL import Image
    
    # Get colormaps
    viridis = get_viridis_colormap()
    hsv = get_hsv_colormap()
    
    # Get the arrays and ensure 2D
    slope_arr = np.array(slope_data['slope']).squeeze()
    aspect_arr = np.array(aspect_data['aspect']).squeeze()
    
    # Apply colormaps
    # Slope: 0-90 degrees
    slope_img = apply_colormap(slope_arr, viridis, 0, 90)
    # Aspect: 0-360 degrees  
    aspect_img = apply_colormap(aspect_arr, hsv, 0, 360)
    
    # Handle NaN values - make them transparent
    slope_valid = ~np.isnan(slope_arr)
    aspect_valid = ~np.isnan(aspect_arr)
    
    # Create RGBA images (H, W, 4)
    h, w = slope_arr.shape
    slope_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    aspect_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    
    # Fill RGB channels
    slope_rgba[:, :, :3] = slope_img
    aspect_rgba[:, :, :3] = aspect_img
    
    # Fill alpha channel
    slope_rgba[:, :, 3] = (slope_valid * 255).astype(np.uint8)
    aspect_rgba[:, :, 3] = (aspect_valid * 255).astype(np.uint8)
    
    # Convert to PIL and save
    slope_pil = Image.fromarray(slope_rgba, 'RGBA')
    aspect_pil = Image.fromarray(aspect_rgba, 'RGBA')
    
    slope_pil.save(output_dir / f"slope_{field_id}.png")
    aspect_pil.save(output_dir / f"aspect_{field_id}.png")


def get_field_ids():
    """Get list of field IDs from DEM files."""
    dem_files = sorted(DEM_DIR.glob("dem_WV_AG_*.tif"))
    field_ids = []
    for f in dem_files:
        field_id = f.stem.replace("dem_", "")
        field_ids.append(field_id)
    return field_ids


def main(generate_pngs=False):
    """Main function to process all DEMs."""
    print("=" * 60)
    print("Slope & Aspect Generation from DEM")
    print("=" * 60)
    
    output_dir = OUTPUT_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    field_ids = get_field_ids()
    print(f"Found {len(field_ids)} DEM files")
    print(f"PNG generation: {'enabled' if generate_pngs else 'disabled'}")
    
    results = []
    bounds_data = {}
    
    for i, field_id in enumerate(field_ids):
        dem_path = DEM_DIR / f"dem_{field_id}.tif"
        
        if not dem_path.exists():
            print(f"  {field_id}: DEM file not found, skipping")
            continue
        
        print(f"  Processing {field_id} ({i+1}/{len(field_ids)})...", end=" ")
        
        try:
            # Get statistics
            stats = calculate_slope_aspect_stats(dem_path)
            stats['field_id'] = field_id
            results.append(stats)
            print(f"slope={stats['slope_mean']:.2f}°, aspect={stats['aspect_mean']:.1f}°")
            
            # Generate PNGs if requested
            if generate_pngs:
                data = calculate_slope_aspect_with_arrays(dem_path)
                save_slope_aspect_png(field_id, data, data, DEM_DIR)
                
                # Store bounds for web display (same as DEM)
                bounds_data[field_id] = [
                    data['bounds'].left,
                    data['bounds'].bottom,
                    data['bounds'].right,
                    data['bounds'].top
                ]
                
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
    
    # Save bounds if PNGs generated
    if generate_pngs and bounds_data:
        bounds_file = DEM_DIR / "slope_bounds.json"
        import json
        with open(bounds_file, 'w') as f:
            json.dump(bounds_data, f)
        print(f"\n✅ Saved bounds to {bounds_file}")
        print(f"   Created {len(bounds_data)} slope PNGs")
        print(f"   Created {len(bounds_data)} aspect PNGs")
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate slope and aspect data from DEM')
    parser.add_argument('--generate-pngs', action='store_true', 
                        help='Generate PNG overlays for web map')
    args = parser.parse_args()
    
    main(generate_pngs=args.generate_pngs)
