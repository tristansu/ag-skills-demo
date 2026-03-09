#!/usr/bin/env python3
"""
Generate PNG versions of soil type TIFFs with categorical colormaps.

Reads from existing soil TIFFs in /data/soil/ and outputs PNGs to the same directory.
"""

import numpy as np
import rasterio
from pathlib import Path
from matplotlib import cm
import matplotlib.colors as mcolors
from PIL import Image

TIFF_DIR = Path("data/soil")

def generate_distinct_colors(n):
    """Generate n distinct colors for categorical data."""
    colors = []
    for i in range(n):
        hue = i / n
        rgb = mcolors.hsv_to_rgb([hue, 0.7, 0.9])
        colors.append(tuple(int(c * 255) for c in rgb))
    return colors

def main():
    tif_files = list(TIFF_DIR.glob("*_soil.tif"))
    print(f"Processing {len(tif_files)} soil type TIFF files...")
    
    for tiff_path in tif_files:
        output_png = tiff_path.with_suffix('.png')
        if output_png.exists():
            continue
        
        with rasterio.open(tiff_path) as src:
            data = src.read(1)
            height, width = data.shape
            
            unique_values = np.unique(data[~np.isnan(data)])
            num_classes = len(unique_values)
            
            if num_classes == 0:
                print(f"  Skipping {tiff_path.name}: no valid data")
                continue
            
            colors = generate_distinct_colors(max(num_classes, 20))
            
            rgb = np.zeros((height, width, 3), dtype=np.uint8)
            
            for i, val in enumerate(unique_values):
                if not np.isnan(val):
                    mask = data == val
                    color_idx = i % len(colors)
                    rgb[mask] = colors[color_idx]
            
            valid_count = np.sum(~np.isnan(data))
            
            img = Image.fromarray(rgb, mode="RGB")
            img.save(output_png)
            
            print(f"  {output_png.name}: {width}xheight, {num_classes} soil types, {valid_count} pixels")
    
    print("Done!")

if __name__ == "__main__":
    main()
