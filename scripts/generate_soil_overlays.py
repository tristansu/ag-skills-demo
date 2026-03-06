#!/usr/bin/env python3
"""
Generate PNG overlays from SSURGO soil polygons.

Reads SSURGO polygons and renders them as colored PNG overlays for each field
and soil property combination.
"""

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

INPUT_POLYGONS = Path("docs/assignment-03/soil_data/ssurgo_polygons.geojson")
INPUT_PROPERTIES = Path("docs/assignment-03/soil_data/ssurgo_properties.csv")
FIELD_GEOJSON = Path("docs/assignment-03/fields_complete_wgs84.geojson")
OUTPUT_DIR = Path("docs/assignment-03/soil")
OUTPUT_BOUNDS = OUTPUT_DIR / "soil_bounds.json"

OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

SOIL_PROPERTIES = {
    "ph": {"column": "ph1to1h2o_r", "name": "pH", "colormap": "viridis", "vmin": 4.0, "vmax": 7.5},
    "om": {"column": "om_r", "name": "Organic Matter", "colormap": "greens", "vmin": 0, "vmax": 10},
    "clay": {"column": "claytotal_r", "name": "Clay %", "colormap": "oranges", "vmin": 0, "vmax": 50},
    "sand": {"column": "sandtotal_r", "name": "Sand %", "colormap": "yellows", "vmin": 0, "vmax": 80},
    "cec": {"column": "cec7_r", "name": "CEC", "colormap": "purples", "vmin": 0, "vmax": 40},
    "drainage": {"column": "drainagecl", "name": "Drainage", "colormap": "drainage", "vmin": 0, "vmax": 1},
}

DRAINAGE_COLORS = {
    "Well drained": "#2ecc71",
    "Somewhat poorly drained": "#f1c40f",
    "Poorly drained": "#e67e22",
    "Very poorly drained": "#e74c3c",
    "Somewhat excessively drained": "#3498db",
    "Excessively drained": "#2980b9",
    "Not rated": "#95a5a6",
    None: "#95a5a6",
}


def get_colormap(name):
    """Get matplotlib colormap by name."""
    if name == "greens":
        return LinearSegmentedColormap.from_list("greens", ["#f0fdf4", "#166534"], N=256)
    elif name == "oranges":
        return LinearSegmentedColormap.from_list("oranges", ["#fff7ed", "#7c2d12"], N=256)
    elif name == "yellows":
        return LinearSegmentedColormap.from_list("yellows", ["#fefce8", "#713f12"], N=256)
    elif name == "purples":
        return LinearSegmentedColormap.from_list("purples", ["#faf5ff", "#581c87"], N=256)
    else:
        return plt.get_cmap(name)


def get_drainage_color(drainage):
    """Get color for drainage class."""
    return DRAINAGE_COLORS.get(drainage, "#95a5a6")


def render_field_overlay(field_id, field_geom, merged_gdf, prop_key, prop_config):
    """Render a PNG overlay for a single field and property."""
    column = prop_config["column"]
    
    # Filter to this field
    field_data = merged_gdf[merged_gdf["field_id"] == field_id]
    if len(field_data) == 0:
        return None
    
    field_bounds = field_geom.bounds
    padding = 0.1
    dx = (field_bounds[2] - field_bounds[0]) * padding
    dy = (field_bounds[3] - field_bounds[1]) * padding
    
    xlim = (field_bounds[0] - dx, field_bounds[2] + dx)
    ylim = (field_bounds[1] - dy, field_bounds[3] + dy)
    
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    
    try:
        if prop_key == "drainage":
            # Categorical - plot each unique value
            unique_drainages = field_data['drainagecl'].dropna().unique()
            for drainage in unique_drainages:
                if drainage is None or pd.isna(drainage):
                    continue
                subset = field_data[field_data['drainagecl'] == drainage]
                if len(subset) > 0:
                    color = get_drainage_color(drainage)
                    subset.plot(ax=ax, facecolor=color, edgecolor="white", linewidth=0.5)
        else:
            # Continuous - use colormap
            vmin = prop_config["vmin"]
            vmax = prop_config["vmax"]
            cmap = get_colormap(prop_config["colormap"])
            
            # Fill NaN with vmin
            field_data_plot = field_data.copy()
            if column in field_data_plot.columns:
                field_data_plot[column] = field_data_plot[column].fillna(vmin)
                field_data_plot.plot(
                    ax=ax,
                    column=column,
                    cmap=cmap,
                    vmin=vmin,
                    vmax=vmax,
                    edgecolor="white",
                    linewidth=0.5,
                    missing_kwds={'color': '#cccccc'}
                )
        
        # Add field boundary outline
        field_gdf = gpd.read_file(FIELD_GEOJSON)
        field_row = field_gdf[field_gdf["field_id"] == field_id]
        if len(field_row) > 0:
            field_row.boundary.plot(ax=ax, edgecolor="black", linewidth=2)
        
        output_path = OUTPUT_DIR / f"soil_{field_id}_{prop_key}.png"
        plt.savefig(output_path, dpi=100, bbox_inches="tight", pad_inches=0, transparent=True)
        plt.close()
        
        return {
            "field_id": field_id,
            "property": prop_key,
            "bounds": [xlim[0], ylim[0], xlim[1], ylim[1]]
        }
    except Exception as e:
        print(f"    Error rendering {field_id} - {prop_key}: {e}")
        plt.close()
        return None


def main():
    print(f"Loading SSURGO polygons from {INPUT_POLYGONS}...")
    soil_gdf = gpd.read_file(INPUT_POLYGONS)
    print(f"  Loaded {len(soil_gdf)} soil polygons")
    
    print(f"Loading properties from {INPUT_PROPERTIES}...")
    properties_df = pd.read_csv(INPUT_PROPERTIES)
    print(f"  Loaded {len(properties_df)} property records")
    
    # Fix mukey type mismatch - convert both to string
    soil_gdf['mukey'] = soil_gdf['mukey'].astype(str)
    properties_df['mukey'] = properties_df['mukey'].astype(str)
    
    print("Merging polygons with properties...")
    # Get first record per mukey for each field to avoid duplicates
    props_unique = properties_df.drop_duplicates(subset=['mukey', 'field_id'], keep='first')
    
    # Merge all properties at once
    merged_gdf = soil_gdf.merge(
        props_unique[['mukey', 'ph1to1h2o_r', 'om_r', 'claytotal_r', 'sandtotal_r', 'cec7_r', 'drainagecl']],
        on='mukey',
        how='left'
    )
    print(f"  Merged data has {len(merged_gdf)} rows")
    
    print(f"Loading fields from {FIELD_GEOJSON}...")
    field_gdf = gpd.read_file(FIELD_GEOJSON)
    fields = field_gdf["field_id"].unique()
    print(f"  {len(fields)} fields")
    
    field_geoms = {row["field_id"]: row.geometry for _, row in field_gdf.iterrows()}
    
    all_bounds = {}
    total = len(fields) * len(SOIL_PROPERTIES)
    current = 0
    success = 0
    errors = 0
    
    for field_id in fields:
        if field_id not in field_geoms:
            continue
            
        field_geom = field_geoms[field_id]
        
        # Check if this field has any soil data
        field_polys = merged_gdf[merged_gdf["field_id"] == field_id]
        if len(field_polys) == 0:
            print(f"  Skipping {field_id} - no soil polygons")
            continue
        
        for prop_key, prop_config in SOIL_PROPERTIES.items():
            current += 1
            print(f"  [{current}/{total}] {field_id} - {prop_key}")
            
            try:
                result = render_field_overlay(
                    field_id, field_geom, merged_gdf, prop_key, prop_config
                )
                if result:
                    all_bounds[f"{field_id}_{prop_key}"] = result["bounds"]
                    success += 1
                else:
                    errors += 1
            except Exception as e:
                print(f"    Error: {e}")
                errors += 1
    
    plt.close('all')
    
    print(f"\nSaving bounds to {OUTPUT_BOUNDS}...")
    with open(OUTPUT_BOUNDS, "w") as f:
        json.dump(all_bounds, f, indent=2)
    
    print(f"\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Errors: {errors}")
    print(f"PNG files generated: {len(all_bounds)}")
    print("Done!")


if __name__ == "__main__":
    main()
