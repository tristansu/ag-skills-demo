#!/usr/bin/env python3
"""
Generate PNG versions of terrain TIFFs (elevation, slope, aspect) with colormaps.

Reads from existing terrain TIFFs in /data/terrain/ and outputs PNGs to the same directory.
Uses 15% padding to match the original generation settings.
"""

import numpy as np
import rasterio
from pathlib import Path
from matplotlib import cm
from PIL import Image

TIFF_DIR = Path("data/terrain")

COLORMAPS = {
    "elevation": ("inferno", None, None),
    "slope": ("YlOrRd", None, None),
    "aspect": ("hsv", 0, 360),
}

def apply_colormap(data, cmap_name, vmin=None, vmax=None):
    """Apply colormap to normalized data."""
    if vmin is None:
        valid = data[~np.isnan(data)]
        if len(valid) == 0:
            return None
        vmin, vmax = float(np.min(valid)), float(np.max(valid))
    
    data_normalized = np.clip((data - vmin) / (vmax - vmin + 0.001), 0, 1)
    cmap = cm.get_cmap(cmap_name, 256)
    colored = cmap(data_normalized)
    rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    return rgb, vmin, vmax

def main():
    tif_files = list(TIFF_DIR.glob("*_elevation.tif")) + list(TIFF_DIR.glob("*_slope.tif")) + list(TIFF_DIR.glob("*_aspect.tif"))
    print(f"Processing {len(tif_files)} terrain TIFF files...")
    
    for tiff_path in tif_files:
        field_id = tiff_path.stem.rsplit('_', 1)[0]
        metric = tiff_path.stem.rsplit('_', 1)[-1]
        
        if metric not in COLORMAPS:
            continue
        
        output_png = tiff_path.with_suffix('.png')
        if output_png.exists():
            continue
        
        cmap_name, vmin_default, vmax_default = COLORMAPS[metric]
        
        with rasterio.open(tiff_path) as src:
            data = src.read(1)
            height, width = data.shape
            
            rgb, vmin, vmax = apply_colormap(data, cmap_name, vmin_default, vmax_default)
            
            if rgb is None:
                print(f"  Skipping {tiff_path.name}: no valid data")
                continue
            
            valid = data[~np.isnan(data)]
            valid_count = len(valid)
            
            img = Image.fromarray(rgb, mode="RGB")
            img.save(output_png)
            
            print(f"  {output_png.name}: {width}x{height}, range {vmin:.1f} to {vmax:.1f} ({valid_count} pixels)")
    
    print("Done!")

if __name__ == "__main__":
    main()
