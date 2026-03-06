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
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

INPUT_POLYGONS = Path("docs/assignment-03b/soil_data/ssurgo_polygons.geojson")
INPUT_PROPERTIES = Path("docs/assignment-03b/soil_data/ssurgo_properties.csv")
FIELD_GEOJSON = Path("docs/assignment-03b/fields_complete_wgs84.geojson")
OUTPUT_DIR = Path("docs/assignment-03b/soil")
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


def get_colormap(name, vmin, vmax):
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


def render_field_overlay(field_id, field_geom, soil_gdf, properties_df, prop_key, prop_config):
    """Render a PNG overlay for a single field and property."""
    column = prop_config["column"]
    
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
    
    field_polys = soil_gdf[soil_gdf["field_id"] == field_id]
    
    if prop_key == "drainage":
        unique_drainages = field_polys.merge(
            properties_df[["mukey", column]].drop_duplicates(),
            on="mukey",
            how="left"
        )[column].unique()
        
        for drainage in unique_drainages:
            subset = field_polys[
                field_polys.merge(
                    properties_df[["mukey", column]].drop_duplicates(),
                    on="mukey",
                    how="left"
                )[column] == drainage
            ]
            color = get_drainage_color(drainage)
            subset.plot(ax=ax, facecolor=color, edgecolor="white", linewidth=0.5)
    else:
        merged = field_polys.merge(
            properties_df[["mukey", column]].drop_duplicates(subset=False),
            on="mukey",
            how="left"
        )
        
        values = merged[column].dropna()
        if len(values) > 0:
            vmin = prop_config["vmin"]
            vmax = prop_config["vmax"]
            cmap = get_colormap(prop_config["colormap"], vmin, vmax)
            
            merged[column] = merged[column].fillna(vmin)
            merged.plot(
                ax=ax,
                column=column,
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                edgecolor="white",
                linewidth=0.5,
            )
    
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


def main():
    print(f"Loading SSURGO polygons from {INPUT_POLYGONS}...")
    soil_gdf = gpd.read_file(INPUT_POLYGONS)
    print(f"  Loaded {len(soil_gdf)} soil polygons")
    
    print(f"Loading properties from {INPUT_PROPERTIES}...")
    properties_df = pd.read_csv(INPUT_PROPERTIES)
    print(f"  Loaded {len(properties_df)} property records")
    
    print(f"Loading fields from {FIELD_GEOJSON}...")
    field_gdf = gpd.read_file(FIELD_GEOJSON)
    fields = field_gdf["field_id"].unique()
    print(f"  {len(fields)} fields")
    
    field_geoms = {row["field_id"]: row.geometry for _, row in field_gdf.iterrows()}
    
    all_bounds = {}
    total = len(fields) * len(SOIL_PROPERTIES)
    current = 0
    
    for field_id in fields:
        if field_id not in field_geoms:
            continue
            
        field_geom = field_geoms[field_id]
        
        field_polys = soil_gdf[soil_gdf["field_id"] == field_id]
        if len(field_polys) == 0:
            print(f"  Skipping {field_id} - no soil polygons")
            continue
        
        for prop_key, prop_config in SOIL_PROPERTIES.items():
            current += 1
            print(f"  [{current}/{total}] {field_id} - {prop_key}")
            
            try:
                result = render_field_overlay(
                    field_id, field_geom, soil_gdf, properties_df, prop_key, prop_config
                )
                all_bounds[f"{field_id}_{prop_key}"] = result["bounds"]
            except Exception as e:
                print(f"    Error: {e}")
    
    print(f"\nSaving bounds to {OUTPUT_BOUNDS}...")
    with open(OUTPUT_BOUNDS, "w") as f:
        json.dump(all_bounds, f, indent=2)
    
    print("Done!")


if __name__ == "__main__":
    main()
