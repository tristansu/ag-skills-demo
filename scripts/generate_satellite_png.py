#!/usr/bin/env python3
"""Generate PNG versions of satellite TIFFs with colormaps for web display."""

import numpy as np
import rasterio
from pathlib import Path
from matplotlib import cm
from PIL import Image

TIFF_DIR = Path("data/assignment-03/satellite")
PNG_DIR = Path("docs/assignment-03/satellite")

COLORMAPS = {
    "ndvi": ("viridis", -0.2, 1.0),
    "msavi": ("plasma", -0.2, 1.0),
    "evi": ("magma", -0.2, 1.0),
    "ndmi": ("Blues_r", -0.5, 0.6),
}

def apply_colormap(data, cmap_name, vmin, vmax):
    """Apply colormap to normalized data."""
    data_normalized = np.clip((data - vmin) / (vmax - vmin), 0, 1)
    cmap = cm.get_cmap(cmap_name)
    colored = cmap(data_normalized)
    rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    return rgb

def main():
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    
    tiff_files = list(TIFF_DIR.glob("*.tif"))
    print(f"Processing {len(tiff_files)} TIFF files...")
    
    for tiff_path in tiff_files:
        parts = tiff_path.stem.split("_")
        field_id = "_".join(parts[:-1])
        metric = parts[-1]
        
        if metric not in COLORMAPS:
            continue
            
        cmap_name, vmin, vmax = COLORMAPS[metric]
        output_path = PNG_DIR / f"{field_id}_{metric}.png"
        
        if output_path.exists():
            continue
        
        with rasterio.open(tiff_path) as src:
            data = src.read(1)
            height, width = data.shape
            
            rgb = apply_colormap(data, cmap_name, vmin, vmax)
            
            alpha = ~np.isnan(data)
            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            rgba[:, :, :3] = rgb
            rgba[:, :, 3] = (alpha * 255).astype(np.uint8)
            
            img = Image.fromarray(rgba, mode="RGBA")
            img.save(output_path)
            
            valid = data[~np.isnan(data)]
            print(f"  {output_path.name}: {width}x{height}, range {valid.min():.3f} to {valid.max():.3f}")
    
    print("Done!")

if __name__ == "__main__":
    main()
