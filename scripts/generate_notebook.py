#!/usr/bin/env python3
"""Generate field_mapping_04.ipynb notebook."""

import json
import os

# Base paths
PROJECT_ROOT = '/workspaces/ag-skills-demo'

# Helper function to create a code cell
def code_cell(source, execution_count=None):
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "metadata": {},
        "outputs": [],
        "source": source if isinstance(source, list) else [source]
    }

# Helper function to create a markdown cell
def markdown_cell(source):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source if isinstance(source, list) else [source]
    }

cells = []

# Title and Executive Summary
cells.append(markdown_cell("# Field Mapping 04 - Spatial Correlation Analysis\n\n**Report Date:** March 2026  \n**Dataset:** Oregon Willamette Valley Agricultural Fields (50 fields)"))
cells.append(markdown_cell("## Executive Summary\n\nThis notebook analyzes spatial correlations between satellite metrics, soil properties, and terrain data for 4 randomly selected fields from the 50-field dataset.\n\n### Data Sources (10m Resolution)\n\n| Source | Variables | Purpose |\n|--------|-----------|---------|\n| Satellite | NDVI, MSAVI, EVI, NDMI | Vegetation and moisture indices |\n| Terrain | Elevation, Slope, Aspect | Topographic features |\n| Soil | pH, OM%, Clay%, Sand%, CEC, AWC, Silt% | Soil properties |"))
cells.append(markdown_cell("## Section 1: Setup & Imports"))

# Section 1: Setup & Imports
section1_code = '''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy import stats
import json
import os
import random
import ipywidgets as widgets
from IPython.display import display, clear_output

# Set random seed for reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Configuration Parameters
MIN_PIXEL_COUNT = 30  # Minimum pixels required for valid correlation
SATELLITE_METRICS = ['ndvi', 'msavi', 'evi', 'ndmi']
SOIL_PROPERTIES = ['ph', 'om_pct', 'clay_pct', 'sand_pct', 'cec', 'awc', 'silt_pct']
TERRAIN_PROPERTIES = ['elevation', 'slope', 'aspect']

# Define absolute paths
PROJECT_ROOT = '/workspaces/ag-skills-demo'
FIELDS_GEOJSON = os.path.join(PROJECT_ROOT, 'data/fields_oregon_willamette_ag_2025.geojson')
TERRAIN_RESAMPLED_DIR = os.path.join(PROJECT_ROOT, 'data/terrain_resampled')
SOIL_PROPS_RESAMPLED_DIR = os.path.join(PROJECT_ROOT, 'data/soil_properties_resampled')
SATELLITE_DIR = os.path.join(PROJECT_ROOT, 'data/satellite')
TERRAIN_PNG_DIR = os.path.join(PROJECT_ROOT, 'data/terrain')

# Display configuration
print('Configuration loaded:')
print(f'  MIN_PIXEL_COUNT: {MIN_PIXEL_COUNT}')
print(f'  SATELLITE_METRICS: {SATELLITE_METRICS}')
print(f'  SOIL_PROPERTIES: {SOIL_PROPERTIES}')
print(f'  TERRAIN_PROPERTIES: {TERRAIN_PROPERTIES}')
print(f'  Fields GeoJSON: {FIELDS_GEOJSON}')'''
cells.append(code_cell(section1_code, 1))

cells.append(markdown_cell("## Section 2: Helper Functions"))

# Section 2: Helper Functions
section2_code = '''def load_raster(path, nodata=-9999):
    """Load raster and return data with valid mask."""
    if not os.path.exists(path):
        return None, None, None
    with rasterio.open(path) as src:
        data = src.read(1)
        valid_mask = (data != nodata) & ~np.isnan(data)
        bounds = src.bounds
    return data, valid_mask, bounds

def get_field_boundary(field_id, gdf):
    """Extract field boundary coordinates from GeoDataFrame."""
    field_gdf = gdf[gdf['field_id'] == field_id]
    if len(field_gdf) == 0:
        return None
    geom = field_gdf.geometry.iloc[0]
    if geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)[:-1]  # Remove closing point
        return [coords]
    elif geom.geom_type == 'MultiPolygon':
        return [list(p.exterior.coords)[:-1] for p in geom.geoms]
    return None

def transform_bounds_to_pixels(bounds, width, height):
    """Convert raster bounds to pixel coordinates for boundary overlay."""
    minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top
    xs = np.linspace(minx, maxx, width)
    ys = np.linspace(maxy, miny, height)
    return xs, ys

def plot_image_with_boundary(ax, data, cmap, title, bounds, field_boundary,
                            vmin=None, vmax=None, nodata=-9999):
    """Plot raster image with field boundary overlay."""
    plot_data = data.astype(float)
    plot_data = np.where(plot_data == nodata, np.nan, plot_data)
    
    if vmin is None:
        vmin = np.nanpercentile(plot_data, 2)
    if vmax is None:
        vmax = np.nanpercentile(plot_data, 98)
    
    ax.imshow(plot_data, cmap=cmap, vmin=vmin, vmax=vmax, origin='upper')
    
    # Overlay field boundary
    if field_boundary is not None and bounds is not None:
        width, height = data.shape[1], data.shape[0]
        xs = np.linspace(bounds.left, bounds.right, width)
        ys = np.linspace(bounds.top, bounds.bottom, height)
        
        for poly_coords in field_boundary:
            px = np.interp([c[0] for c in poly_coords], xs, np.arange(len(xs)))
            py = np.interp([c[1] for c in poly_coords], ys, np.arange(len(ys)))
            ax.plot(px, py, 'r-', linewidth=2)
    
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.axis('off')
    
    # Add scale bar
    height, width = data.shape
    scale_length = width // 5
    scale_meters = int(scale_length * 10)
    ax.plot([10, 10 + scale_length], [height - 15, height - 15], 'k-', lw=3)
    ax.text(width // 2, height - 8, f'~{scale_meters}m', ha='center',
            fontsize=8, color='white', fontweight='bold')

def calculate_pixel_correlation(array1, array2, min_pixels=MIN_PIXEL_COUNT):
    """Calculate Pearson correlation with p-value. Handles different-shaped arrays."""
    # Ensure arrays are same shape by cropping to minimum dimensions
    if array1.shape != array2.shape:
        min_h = min(array1.shape[0], array2.shape[0])
        min_w = min(array1.shape[1], array2.shape[1])
        array1 = array1[:min_h, :min_w]
        array2 = array2[:min_h, :min_w]
    
    valid_mask = ~np.isnan(array1) & ~np.isnan(array2)
    valid_count = np.sum(valid_mask)
    
    if valid_count < min_pixels:
        return np.nan, np.nan, valid_count
    
    x = array1[valid_mask]
    y = array2[valid_mask]
    
    if np.std(x) == 0 or np.std(y) == 0:
        return np.nan, np.nan, valid_count
    
    r, p = stats.pearsonr(x, y)
    return r, p, valid_count

def get_all_dataset_options():
    """Build list of all available datasets for correlation analysis."""
    options = []
    for metric in SATELLITE_METRICS:
        options.append(('Satellite', metric, f'sat_{metric}'))
    for prop in TERRAIN_PROPERTIES:
        options.append(('Terrain', prop, f'terrain_{prop}'))
    for prop in SOIL_PROPERTIES:
        options.append(('Soil', prop, f'soil_{prop}'))
    return options

print("Helper functions defined." )'''
cells.append(code_cell(section2_code, 2))

cells.append(markdown_cell("## Section 3: Load Field Boundaries & Select 4 Fields"))

# Section 3: Load Fields
section3_code = '''# Load field boundaries from GeoJSON
gdf = gpd.read_file(FIELDS_GEOJSON)
print(f"Loaded {len(gdf)} fields from GeoJSON")
print(f"Columns: {list(gdf.columns)}")

# Randomly select 4 fields
selected_fields = random.sample(list(gdf['field_id']), 4)
print(f"\\nSelected fields (seed={RANDOM_SEED}): {selected_fields}")

# Display field information (load crop data from CDL CSV)
cdl_df = pd.read_csv(os.path.join(PROJECT_ROOT, 'data/cdl_oregon_willamette_ag_2025.csv'))
field_info = gdf[gdf['field_id'].isin(selected_fields)][
    ['field_id', 'area_acres', 'lat', 'lon']
].copy()
field_info = field_info.merge(cdl_df[['field_id', 'cdl_crop']], on='field_id', how='left')
field_info = field_info.sort_values('area_acres', ascending=False)
print("\n=== Selected Field Information ===")
display(field_info)

# Verify data files exist for each field
print("\\n=== Data Availability Check ===")
for field_id in selected_fields:
    sat_files = sum(1 for m in SATELLITE_METRICS 
                   if os.path.exists(f'{SATELLITE_DIR}/{field_id}_{m}.tif'))
    terr_files = sum(1 for p in TERRAIN_PROPERTIES 
                    if os.path.exists(f'{TERRAIN_RESAMPLED_DIR}/{field_id}_{p}.tif'))
    soil_files = sum(1 for p in SOIL_PROPERTIES 
                    if os.path.exists(f'{SOIL_PROPS_RESAMPLED_DIR}/{field_id}_soil_{p}.tif'))
    print(f"{field_id}: {sat_files}/4 sat, {terr_files}/3 terrain, {soil_files}/7 soil")'''
cells.append(code_cell(section3_code, 3))

cells.append(markdown_cell("## Section 4: Image Viewer (Select Field from Dropdown)\n\nSelect a field to view satellite, terrain, and soil property images with field boundaries overlaid."))

# Section 4: Image Viewer
section4_code = '''# Image viewer with dropdown for field selection

def display_field_images(field_id):
    """Display all satellite, terrain, and soil images for a field."""
    # Get field boundary
    boundary = get_field_boundary(field_id, gdf)
    
    # Set up figure
    fig, axes = plt.subplots(3, 4, figsize=(16, 10))
    fig.suptitle(f'Field: {field_id}', fontsize=14, fontweight='bold')
    
    # Colormap definitions
    colormaps = {
        'ndvi': ('RdYlGn', 'NDVI'),
        'msavi': ('viridis', 'MSAVI'),
        'evi': ('viridis', 'EVI'),
        'ndmi': ('RdBu', 'NDMI'),
        'elevation': ('terrain', 'Elevation (m)'),
        'slope': ('YlOrRd', 'Slope (deg)'),
        'aspect': ('hsv', 'Aspect (deg)'),
        'ph': ('coolwarm', 'pH'),
        'om_pct': ('YlGn', 'OM %'),
        'clay_pct': ('YlOrBr', 'Clay %'),
        'sand_pct': ('YlGnBu', 'Sand %'),
        'cec': ('Purples', 'CEC'),
        'awc': ('Blues', 'AWC'),
        'silt_pct': ('YlGn', 'Silt %')
    }
    
    # Row 1: Satellite images (PNG files)
    for i, metric in enumerate(SATELLITE_METRICS):
        png_path = f'{SATELLITE_DIR}/{field_id}_{metric}.png'
        tif_path = f'{SATELLITE_DIR}/{field_id}_{metric}.tif'
        
        ax = axes[0, i]
        if os.path.exists(png_path):
            img = plt.imread(png_path)
            ax.imshow(img, origin='upper')
            # Add boundary overlay
            if boundary:
                # Get bounds from tif if available
                if os.path.exists(tif_path):
                    with rasterio.open(tif_path) as src:
                        bounds = src.bounds
                        width, height = src.width, src.height
                    xs = np.linspace(bounds.left, bounds.right, width)
                    ys = np.linspace(bounds.top, bounds.bottom, height)
                    for poly_coords in boundary:
                        px = np.interp([c[0] for c in poly_coords], xs, np.arange(len(xs)))
                        py = np.interp([c[1] for c in poly_coords], ys, np.arange(len(ys)))
                        ax.plot(px, py, 'r-', linewidth=2)
        elif os.path.exists(tif_path):
            data, _, bounds = load_raster(tif_path)
            cmap, label = colormaps[metric]
            plot_image_with_boundary(ax, data, cmap, label.upper(), bounds, boundary)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(metric.upper())
        ax.axis('off')
    
    # Hide empty subplot in row 1
    axes[0, 3].axis('off')
    
    # Row 2: Terrain images (use PNGs)
    for i, prop in enumerate(TERRAIN_PROPERTIES):
        png_path = f'{TERRAIN_PNG_DIR}/{field_id}_{prop}.png'
        tif_path = f'{TERRAIN_RESAMPLED_DIR}/{field_id}_{prop}.tif'
        
        ax = axes[1, i]
        if os.path.exists(png_path):
            img = plt.imread(png_path)
            ax.imshow(img, origin='upper')
            # Add boundary overlay
            if os.path.exists(tif_path):
                with rasterio.open(tif_path) as src:
                    bounds = src.bounds
                    width, height = src.width, src.height
                xs = np.linspace(bounds.left, bounds.right, width)
                ys = np.linspace(bounds.top, bounds.bottom, height)
                for poly_coords in boundary:
                    px = np.interp([c[0] for c in poly_coords], xs, np.arange(len(xs)))
                    py = np.interp([c[1] for c in poly_coords], ys, np.arange(len(ys)))
                    ax.plot(px, py, 'r-', linewidth=2)
        elif os.path.exists(tif_path):
            data, _, bounds = load_raster(tif_path)
            cmap, label = colormaps[prop]
            plot_image_with_boundary(ax, data, cmap, label, bounds, boundary)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title(prop.capitalize(), fontsize=11, fontweight='bold')
        ax.axis('off')
    
    # Hide empty subplot in row 2
    axes[1, 3].axis('off')
    
    # Row 3: Soil property images (rasters)
    soil_display = ['ph', 'cec', 'silt_pct']  # Display 3 of 7
    for i, prop in enumerate(soil_display):
        tif_path = f'{SOIL_PROPS_RESAMPLED_DIR}/{field_id}_soil_{prop}.tif'
        
        ax = axes[2, i]
        if os.path.exists(tif_path):
            data, _, bounds = load_raster(tif_path)
            cmap, label = colormaps[prop]
            plot_image_with_boundary(ax, data, cmap, label, bounds, boundary)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(prop.replace('_', ' ').capitalize())
        ax.axis('off')
    
    # Hide empty subplot in row 3
    axes[2, 3].axis('off')
    
    plt.tight_layout()
    plt.show()

# Create dropdown widget
field_dropdown = widgets.Dropdown(
    options=selected_fields,
    value=selected_fields[0],
    description='Field:',
    style={'description_width': '60px'}
)

# Interactive display
widgets.interact(display_field_images, field_id=field_dropdown)'''
cells.append(code_cell(section4_code, 4))

cells.append(markdown_cell("## Section 5: Histograms (Select Field from Dropdown)\n\nHistograms of pixel values within each field boundary.\n\n**Note**: Soil properties are excluded as they are too coarse for meaningful pixel histograms."))

# Section 5: Histograms
section5_code = '''def display_field_histograms(field_id):
    """Display histograms for satellite and terrain metrics within field."""
    # Get terrain data for resampling reference
    terr_path = f'{TERRAIN_RESAMPLED_DIR}/{field_id}_elevation.tif'
    if not os.path.exists(terr_path):
        print(f"No terrain data for {field_id}")
        return
    
    with rasterio.open(terr_path) as src:
        ref_data = src.read(1)
        ref_bounds = src.bounds
        ref_transform = src.transform
        ref_crs = src.crs
    
    # Create figure
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    fig.suptitle(f'Field: {field_id} - Pixel Value Distributions', fontsize=14, fontweight='bold')
    
    # Helper to extract values within field
    def get_values_in_field(tif_path, ref_data):
        if not os.path.exists(tif_path):
            return np.array([])
        with rasterio.open(tif_path) as src:
            data = src.read(1)
        # Use same shape as reference
        min_h = min(ref_data.shape[0], data.shape[0])
        min_w = min(ref_data.shape[1], data.shape[1])
        return ref_data[:min_h, :min_w], data[:min_h, :min_w]
    
    # Row 1: Satellite histograms
    for i, metric in enumerate(SATELLITE_METRICS):
        tif_path = f'{SATELLITE_DIR}/{field_id}_{metric}.tif'
        ref, data = get_values_in_field(tif_path, ref_data)
        
        ax = axes[0, i]
        if data.size > 0:
            valid = (ref != -9999) & ~np.isnan(ref) & (data != -9999) & ~np.isnan(data)
            values = data[valid]
            ax.hist(values, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
            ax.set_title(metric.upper(), fontsize=11, fontweight='bold')
            ax.set_xlabel('Value')
            ax.set_ylabel('Frequency')
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        ax.axis('on')
    
    axes[0, 3].axis('off')
    
    # Row 2: Terrain histograms  
    for i, prop in enumerate(TERRAIN_PROPERTIES):
        tif_path = f'{TERRAIN_RESAMPLED_DIR}/{field_id}_{prop}.tif'
        ref, data = get_values_in_field(tif_path, ref_data)
        
        ax = axes[1, i]
        if data.size > 0:
            valid = (ref != -9999) & ~np.isnan(ref) & (data != -9999) & ~np.isnan(data) & (data != -9999)
            values = data[valid]
            ax.hist(values, bins=50, color='darkorange', alpha=0.7, edgecolor='black')
            unit = 'm' if prop == 'elevation' else 'deg'
            ax.set_title(prop.capitalize(), fontsize=11, fontweight='bold')
            ax.set_xlabel(f'Value ({unit})')
            ax.set_ylabel('Frequency')
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        ax.axis('on')
    
    axes[1, 3].axis('off')
    
    plt.tight_layout()
    plt.show()

# Create dropdown for histograms
hist_dropdown = widgets.Dropdown(
    options=selected_fields,
    value=selected_fields[0],
    description='Field:',
    style={'description_width': '60px'}
)

widgets.interact(display_field_histograms, field_id=hist_dropdown)'''
cells.append(code_cell(section5_code, 5))

cells.append(markdown_cell("## Section 6: Interactive Correlation Scatter Plot\n\nSelect field, X-axis variable, and Y-axis variable to explore pixel-by-pixel correlations.\nAll data is at 10m resolution for proper alignment."))

# Section 6: Correlation Scatter
section6_code = '''def load_field_data_10m(field_id):
    """Load all 10m resolution data for a field."""
    data = {}
    
    # Get reference from first satellite file
    ref_path = f'{SATELLITE_DIR}/{field_id}_ndvi.tif'
    if os.path.exists(ref_path):
        with rasterio.open(ref_path) as src:
            ref_shape = (src.height, src.width)
    else:
        ref_path = f'{TERRAIN_RESAMPLED_DIR}/{field_id}_elevation.tif'
        if os.path.exists(ref_path):
            with rasterio.open(ref_path) as src:
                ref_shape = (src.height, src.width)
        else:
            return None
    
    # Load satellite data
    for metric in SATELLITE_METRICS:
        path = f'{SATELLITE_DIR}/{field_id}_{metric}.tif'
        if os.path.exists(path):
            with rasterio.open(path) as src:
                data[f'sat_{metric}'] = src.read(1)[:ref_shape[0], :ref_shape[1]]
    
    # Load terrain data
    for prop in TERRAIN_PROPERTIES:
        path = f'{TERRAIN_RESAMPLED_DIR}/{field_id}_{prop}.tif'
        if os.path.exists(path):
            with rasterio.open(path) as src:
                data[f'terrain_{prop}'] = src.read(1)[:ref_shape[0], :ref_shape[1]]
    
    # Load soil data
    for prop in SOIL_PROPERTIES:
        path = f'{SOIL_PROPS_RESAMPLED_DIR}/{field_id}_soil_{prop}.tif'
        if os.path.exists(path):
            with rasterio.open(path) as src:
                data[f'soil_{prop}'] = src.read(1)[:ref_shape[0], :ref_shape[1]]
    
    return data

def plot_correlation(field_id, x_var, y_var):
    """Plot scatter plot with correlation."""
    # Load data
    data = load_field_data_10m(field_id)
    if data is None or x_var not in data or y_var not in data:
        print(f"Missing data for {field_id}")
        return
    
    x = data[x_var]
    y = data[y_var]
    
    # Calculate correlation
    r, p, n = calculate_pixel_correlation(x, y)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Flatten and mask
    valid = ~np.isnan(x) & ~np.isnan(y) & (x != -9999) & (y != -9999)
    x_flat = x[valid].flatten()
    y_flat = y[valid].flatten()
    
    # Scatter
    ax.scatter(x_flat, y_flat, alpha=0.3, s=10, c='steelblue', edgecolors='none')
    
    # Regression line if correlation exists
    if not np.isnan(r) and np.std(x_flat) > 0 and np.std(y_flat) > 0:
        z = np.polyfit(x_flat, y_flat, 1)
        p_line = np.poly1d(z)
        x_line = np.linspace(np.min(x_flat), np.max(x_flat), 100)
        ax.plot(x_line, p_line(x_line), 'r-', lw=2, label=f'r = {r:.3f}')
    
    # Labels
    x_label = x_var.replace('sat_', '').replace('terrain_', '').replace('soil_', '').upper()
    y_label = y_var.replace('sat_', '').replace('terrain_', '').replace('soil_', '').upper()
    domain = x_var.split('_')[0].capitalize()
    domain_y = y_var.split('_')[0].capitalize()
    
    ax.set_xlabel(f'{x_label} ({domain})', fontsize=11)
    ax.set_ylabel(f'{y_label} ({domain_y})', fontsize=11)
    ax.set_title(f'{field_id}: {x_label} vs {y_label}', fontsize=12, fontweight='bold')
    
    # Add statistics
    if not np.isnan(r):
        sig = '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else ''))
        stats_text = f'r = {r:.3f}\\np = {p:.2e}\\nn = {n} {sig}'
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
                va='top', ha='left', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.legend(loc='lower right')
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

# Build option lists for dropdowns
dataset_options = get_all_dataset_options()
x_options = [f'{d[2]}' for d in dataset_options]
y_options = [f'{d[2]}' for d in dataset_options]

# Create widgets
field_widget = widgets.Dropdown(options=selected_fields, value=selected_fields[0], description='Field:')
x_widget = widgets.Dropdown(options=x_options, value=x_options[0], description='X-axis:')
y_widget = widgets.Dropdown(options=y_options, value=y_options[1], description='Y-axis:')

# Layout
ui = widgets.VBox([
    widgets.HBox([field_widget, x_widget, y_widget])
])

# Interactive output
out = widgets.interactive_output(plot_correlation, {'field_id': field_widget, 'x_var': x_widget, 'y_var': y_widget})
display(ui, out)'''
cells.append(code_cell(section6_code, 6))

cells.append(markdown_cell("## Section 7: Correlation Matrix\n\nShows correlation coefficients between all pairs of variables for each field. Cells with p < 0.05 are marked with asterisks."))

# Section 7: Correlation Matrix
section7_code = '''def compute_correlation_matrix(field_id):
    """Compute full correlation matrix for a field."""
    data = load_field_data_10m(field_id)
    if data is None:
        return None, None
    
    vars_list = list(data.keys())
    n_vars = len(vars_list)
    corr_matrix = np.zeros((n_vars, n_vars))
    p_matrix = np.zeros((n_vars, n_vars))
    
    for i, var1 in enumerate(vars_list):
        for j, var2 in enumerate(vars_list):
            if i == j:
                corr_matrix[i, j] = 1.0
                p_matrix[i, j] = 0.0
            else:
                r, p, n = calculate_pixel_correlation(data[var1], data[var2])
                corr_matrix[i, j] = r if not np.isnan(r) else 0.0
                p_matrix[i, j] = p if not np.isnan(p) else 1.0
    
    return corr_matrix, p_matrix, vars_list

def plot_correlation_matrix(field_id):
    """Display correlation matrix heatmap."""
    result = compute_correlation_matrix(field_id)
    if result[0] is None:
        print(f"No data for {field_id}")
        return
    
    corr, p_vals, vars_list = result
    
    # Shorten variable names for display
    display_names = []
    for v in vars_list:
        parts = v.split('_')
        prefix = {'sat': 'Sat', 'terrain': 'Terr', 'soil': 'Soil'}.get(parts[0], '')
        name = parts[1] if len(parts) > 1 else v
        display_names.append(f"{prefix}:{name}")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Mask invalid correlations
    mask = np.isnan(corr)
    
    # Plot heatmap
    sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r',
                center=0, vmin=-1, vmax=1, xticklabels=display_names,
                yticklabels=display_names, ax=ax, annot_kws={'size': 8})
    
    # Add significance markers
    for i in range(len(vars_list)):
        for j in range(len(vars_list)):
            if p_vals[i, j] < 0.05 and i != j:
                ax.text(j + 0.5, i + 0.75, '*', ha='center', va='center',
                       fontsize=10, fontweight='bold', color='black')
            if p_vals[i, j] < 0.01 and i != j:
                ax.text(j + 0.5, i + 0.85, '*', ha='center', va='center',
                       fontsize=12, fontweight='bold', color='black')
    
    ax.set_title(f'Correlation Matrix: {field_id}\\n(* p<0.05, ** p<0.01)', fontsize=12, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.show()

# Dropdown for correlation matrix
matrix_dropdown = widgets.Dropdown(
    options=selected_fields,
    value=selected_fields[0],
    description='Field:',
    style={'description_width': '60px'}
)

widgets.interact(plot_correlation_matrix, field_id=matrix_dropdown)'''
cells.append(code_cell(section7_code, 7))

cells.append(markdown_cell("## Section 8: Summary & Analysis\n\nAnalysis of significant correlations across all selected fields."))

# Section 8: Summary
section8_code = '''# Collect all significant correlations across fields
all_results = []

for field_id in selected_fields:
    result = compute_correlation_matrix(field_id)
    if result[0] is None:
        continue
    
    corr, p_vals, vars_list = result
    
    # Find significant correlations
    for i, var1 in enumerate(vars_list):
        for j, var2 in enumerate(vars_list):
            if i < j:  # Upper triangle only
                r = corr[i, j]
                p = p_vals[i, j]
                if p < 0.05 and not np.isnan(r):
                    all_results.append({
                        'field': field_id,
                        'var1': var1,
                        'var2': var2,
                        'r': r,
                        'p_value': p,
                        'significant': 'Yes' if p < 0.05 else 'No'
                    })

# Create summary DataFrame
if all_results:
    summary_df = pd.DataFrame(all_results)
    summary_df = summary_df.sort_values(['var1', 'var2', 'field'])
    
    print("=== Significant Correlations (p < 0.05) ===\\n")
    print(f"Total significant correlations found: {len(summary_df)}\\n")
    
    # Group by variable pair
    for (v1, v2), group in summary_df.groupby(['var1', 'var2']):
        print(f"--- {v1} vs {v2} ---")
        for _, row in group.iterrows():
            sig = '**' if row['p_value'] < 0.01 else '*'
            print(f"  {row['field']}: r = {row['r']:.3f}, p = {row['p_value']:.2e} {sig}")
        print()
    
    # Save to CSV
    summary_df.to_csv('/workspaces/ag-skills-demo/notebooks/output/significant_correlations.csv', index=False)
    print("Results saved to: notebooks/output/significant_correlations.csv")
else:
    print("No significant correlations found." if all_results else "Could not compute correlations.")
    
# Create summary table
print("\\n=== Summary Table ===\\n")
if all_results:
    # Pivot to show fields as columns
    pivot_df = summary_df.pivot_table(
        index=['var1', 'var2'], 
        columns='field', 
        values='r', 
        aggfunc='first'
    ).reset_index()
    display(pivot_df.round(3))'''
cells.append(code_cell(section8_code, 8))

cells.append(markdown_cell("## End of Notebook"))

# Build notebook structure
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

# Write notebook
output_path = os.path.join(PROJECT_ROOT, 'notebooks/field_mapping_04.ipynb')
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w') as f:
    json.dump(notebook, f, indent=1)

print(f"Generated notebook: {output_path}")
print(f"Total cells: {len(cells)}")
