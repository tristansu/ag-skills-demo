#!/usr/bin/env python3
"""
Generate soil property maps from field boundary GeoJSON.

This script:
1. Takes GeoJSON with field boundaries (Polygon or MultiPolygon)
2. Queries SoilGrids for global soil data via WCS
3. Generates float GeoTIFFs for: OM%, clay%, silt%, sand%, CEC, AWC, pH
4. Creates JSON metadata with bounds, source, and resolution

================================================================================
GLOBAL VERSION - Non-US Coverage
================================================================================

This is the global version of generate_soil_maps.py using SoilGrids instead of
USDA SSURGO. Use this version for locations outside the United States.

Key Differences from US Version:
- Data Source: SoilGrids250m (global) vs USDA SSURGO (US only)
- Resolution: 250m (vs 5m target in US) - SIGNIFICANT DOWNSGRADE
- Drainage Class: NOT AVAILABLE in SoilGrids

Resolution Warning:
- SoilGrids provides 250m resolution, which is significantly coarser than
  SSURGO (~10m). This is a fundamental limitation of global soil data.

Drainage Class Note:
- Drainage class is not available in SoilGrids. The drainage output file
  will contain nodata values.

Property Mapping (SoilGrids to output):
- om_pct: soil organic carbon (soc) at 0-5cm depth
- clay_pct: clay content at 0-5cm depth
- silt_pct: silt content at 0-5cm depth
- sand_pct: sand content at 0-5cm depth
- cec: cation exchange capacity (cec) at 0-5cm depth
- awc: volumetric water content at field capacity (wfc) - approximated
- ph: pH in water (phh2o) at 0-5cm depth
- drainage: NOT AVAILABLE

================================================================================
DETAILED USAGE
================================================================================

Prerequisites:
    - Python 3.9+
    - Dependencies: geopandas, rasterio, numpy, owslib, requests, pandas, shapely
    - Internet access to SoilGrids WCS API

Input Format:
    GeoJSON file with:
    - A "field_id" property for each feature (or auto-generated if missing)
    - Polygon or MultiPolygon geometries in WGS84 (EPSG:4326)

    Example GeoJSON:
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "properties": {"field_id": "DE_FIELD_001"},
          "geometry": {
            "type": "Polygon",
            "coordinates": [[[10.0, 50.0], [10.5, 50.0], ...]]
          }
        }
      ]
    }

Basic Usage:
    # Process all fields in GeoJSON
    python scripts/generate_soil_maps_global.py --input data/fields_germany.geojson --output-dir ./soil_maps_global

    # Process single field by ID
    python scripts/generate_soil_maps_global.py --input data/fields_germany.geojson --output-dir ./soil_maps_global --field-id DE_FIELD_001

Full Options:
    --input        Path to GeoJSON file with field boundaries (required)
    --output-dir   Output directory (default: soil_maps_global)
    --padding      Padding around polygon as fraction (default: 0.10 = 10%%)
    --resolution   Target resolution in meters (default: 250)
    --field-id     Process single field by ID (default: all fields)

Output Structure:
    {output-dir}/
    └── {field_id}/
        ├── {field_id}_om_pct.tif       # Organic Matter (%) - from SOC
        ├── {field_id}_clay_pct.tif      # Clay content (%)
        ├── {field_id}_silt_pct.tif      # Silt content (%)
        ├── {field_id}_sand_pct.tif      # Sand content (%)
        ├── {field_id}_cec.tif           # Cation Exchange Capacity (cmolc/kg)
        ├── {field_id}_awc.tif          # Available Water Capacity (cm/cm) - from wfc
        ├── {field_id}_ph.tif           # pH
        ├── {field_id}_drainage.tif     # Drainage class - NOT AVAILABLE (nodata)
        └── {field_id}_soil_metadata.json

Metadata JSON includes:
    - field_id
    - centroid_values: soil properties at field centroid (lat, lon, and parameters)
    - properties: min/max values and units for each property
    - spatial: bounds, CRS, resolution, padding
    - data_source: ISRIC SoilGrids250m
    - resolution_note: 250m native resolution

Example:
    python scripts/generate_soil_maps_global.py \\
        --input data/fields_germany.geojson \\
        --output-dir ./soil_maps_global \\
        --field-id DE_FIELD_001 \\
        --padding 0.10
"""

import argparse
import io
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.geometry import box, Point
from owslib.wcs import WebCoverageService


SOILGRIDS_PROPERTIES = {
    "om_pct": {"layer": "soc", "depth": "0-5cm", "unit": "g/kg", "scale": 0.1},  # SOC in g/kg, convert to %
    "clay_pct": {"layer": "clay", "depth": "0-5cm", "unit": "g/kg", "scale": 0.1},
    "silt_pct": {"layer": "silt", "depth": "0-5cm", "unit": "g/kg", "scale": 0.1},
    "sand_pct": {"layer": "sand", "depth": "0-5cm", "unit": "g/kg", "scale": 0.1},
    "cec": {"layer": "cec", "depth": "0-5cm", "unit": "cmolc/kg", "scale": 0.1},
    "ph": {"layer": "phh2o", "depth": "0-5cm", "unit": "pH x 10", "scale": 0.1},
}

# Not available in SoilGrids - will be set to nodata
SKIP_PROPERTIES = ["awc", "drainage"]


def parse_geojson(input_path):
    """Parse GeoJSON file and return GeoDataFrame in WGS84."""
    gdf = gpd.read_file(input_path)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def calculate_padded_bounds(bounds, padding):
    """Apply padding to bounds."""
    minx, miny, maxx, maxy = bounds
    dx = (maxx - minx) * padding
    dy = (maxy - miny) * padding
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def fetch_soilgrids_layer(layer_name, depth, bbox, resolution=250):
    """Fetch a soil property layer from SoilGrids via VRT.
    
    Args:
        layer_name: SoilGrids layer name (e.g., 'soc', 'clay', 'phh2o')
        depth: Depth interval (e.g., '0-5cm', '5-15cm')
        bbox: (minx, miny, maxx, maxy) in EPSG:4326
        resolution: Target resolution in meters
    
    Returns:
        tuple: (numpy_array, rasterio_profile) or (None, None) on failure
    """
    from pyproj import Transformer
    
    # Build the VRT URL for SoilGrids
    identifier = f"{layer_name}_{depth}_mean"
    vrt_url = f"/vsicurl?max_retry=3&retry_delay=1&url=https://files.isric.org/soilgrids/latest/data/{layer_name}/{identifier}.vrt"
    
    try:
        with rasterio.open(vrt_url) as src:
            # Transform bounding box from EPSG:4326 to SoilGrids CRS
            minx, miny, maxx, maxy = bbox
            
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            sg_minx, sg_maxy = transformer.transform(minx, maxy)
            sg_maxx, sg_miny = transformer.transform(maxx, miny)
            
            # Window for the bounding box in SoilGrids CRS
            window = rasterio.windows.from_bounds(sg_minx, sg_miny, sg_maxx, sg_maxy, src.transform)
            
            # Read the data in the window
            data = src.read(window=window)
            
            if data.size == 0:
                print(f"    No data for {identifier} in bounding box")
                return None, None
            
            # Calculate the new transform for the window
            new_transform = src.window_transform(window)
            
            # Squeeze to remove band dimension
            data = data.squeeze()
            
            profile = {
                'driver': 'GTiff',
                'height': data.shape[0],
                'width': data.shape[1],
                'count': 1,
                'dtype': 'int16',
                'crs': src.crs,
                'transform': new_transform,
                'nodata': src.nodata if src.nodata is not None else -9999,
            }
        return data, profile
    except Exception as e:
        print(f"    Failed to fetch {identifier}: {e}")
        return None, None


def create_raster(padded_bounds, target_resolution=250):
    """Create empty raster array and transform."""
    minx, miny, maxx, maxy = padded_bounds

    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, abs(np.cos(np.radians(mid_lat)))))

    width = int(np.ceil((maxx - minx) / (target_resolution * deg_per_m_lon)))
    height = int(np.ceil((maxy - miny) / (target_resolution * deg_per_m_lat)))

    width = max(64, width)
    height = max(64, height)

    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    return width, height, transform


def generate_soil_property_tifs(
    padded_bounds,
    output_dir,
    field_id,
    target_resolution=250
):
    """Generate float GeoTIFFs for each soil property."""
    width, height, transform = create_raster(padded_bounds, target_resolution)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "crs": "EPSG:4326",
        "nodata": np.nan,
        "compress": "lzw",
    }

    property_stats = {}
    property_arrays = {}
    
    print(f"    Fetching soil properties from SoilGrids (250m resolution)...")

    for prop_key, prop_info in SOILGRIDS_PROPERTIES.items():
        layer = prop_info["layer"]
        depth = prop_info["depth"]
        
        print(f"      Fetching {prop_key} ({layer}, {depth})...")
        
        data, src_profile = fetch_soilgrids_layer(layer, depth, padded_bounds, target_resolution)
        
        if data is None:
            print(f"      WARNING: Failed to fetch {prop_key}, using nodata")
            output_data = np.full((height, width), np.nan, dtype=np.float32)
            property_arrays[prop_key] = output_data
            property_stats[prop_key] = {"min": None, "max": None, "unit": prop_info["unit"]}
            continue
        
        # Resample if needed to match our target grid
        if src_profile is not None:
            # Create output array
            output_data = np.full((height, width), np.nan, dtype=np.float32)
            
            # Calculate the source bounds
            src_width = src_profile['width']
            src_height = src_profile['height']
            src_transform = src_profile['transform']
            src_bounds = rasterio.transform.array_bounds(src_height, src_width, src_transform)
            
            # Simple nearest neighbor resampling to target resolution
            # Calculate scaling factors
            scale_x = src_width / width
            scale_y = src_height / height
            
            # Create coordinate grids for output
            out_y, out_x = np.mgrid[0:height, 0:width]
            
            # Map to source coordinates
            src_x = np.clip(np.round(out_x * scale_x).astype(int), 0, src_width - 1)
            src_y = np.clip(np.round(out_y * scale_y).astype(int), 0, src_height - 1)
            
            # Extract values
            src_data = data.astype(np.float32)
            output_data = src_data[src_y, src_x]
            
            # Apply scale factor
            if prop_info["scale"] != 1.0:
                output_data = output_data * prop_info["scale"]
            
            # Handle nodata
            src_nodata = src_profile.get('nodata', -9999)
            output_data = np.where(output_data == src_nodata, np.nan, output_data)
        else:
            output_data = np.full((height, width), np.nan, dtype=np.float32)
        
        property_arrays[prop_key] = output_data
        
        # Calculate statistics
        valid_values = output_data[~np.isnan(output_data)]
        if len(valid_values) > 0:
            property_stats[prop_key] = {
                "min": float(np.min(valid_values)),
                "max": float(np.max(valid_values)),
                "unit": prop_info["unit"],
            }
        else:
            property_stats[prop_key] = {"min": None, "max": None, "unit": prop_info["unit"]}
    
    # Drainage is not available in SoilGrids
    drainage_data = np.full((height, width), np.nan, dtype=np.float32)
    property_arrays["drainage"] = drainage_data
    property_stats["drainage"] = {"min": None, "max": None, "unit": "class", "note": "not available in SoilGrids"}
    
    # Save all TIFs
    for prop_key, output_data in property_arrays.items():
        output_path = output_dir / f"{field_id}_{prop_key}.tif"
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(output_data.astype(np.float32), 1)

    return property_stats


def get_centroid_soil_values(geometry, property_arrays, target_resolution=250):
    """Get soil properties at the centroid of the field polygon.
    
    Returns a dict with centroid lat/lon and the soil parameters,
    or None if centroid cannot be evaluated.
    """
    centroid = geometry.centroid
    centroid_lat = centroid.y
    centroid_lon = centroid.x
    
    # Calculate pixel position
    minx, miny, maxx, maxy = geometry.bounds
    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, abs(np.cos(np.radians(mid_lat)))))
    
    # Get array shape from any property
    sample_array = next(iter(property_arrays.values()))
    height, width = sample_array.shape
    
    # Calculate pixel coordinates
    x_rel = (centroid_lon - minx) / (maxx - minx)
    y_rel = (centroid_lat - miny) / (maxy - miny)
    
    x_pixel = int(x_rel * width)
    y_pixel = int((1 - y_rel) * height)  # Flip y for array indexing
    
    if x_pixel < 0 or x_pixel >= width or y_pixel < 0 or y_pixel >= height:
        return None
    
    result = {
        "lat": round(centroid_lat, 6),
        "lon": round(centroid_lon, 6),
    }
    
    for prop_key, prop_info in SOILGRIDS_PROPERTIES.items():
        if prop_key in property_arrays:
            arr = property_arrays[prop_key]
            if y_pixel < arr.shape[0] and x_pixel < arr.shape[1]:
                val = arr[y_pixel, x_pixel]
                result[prop_key] = float(val) if not np.isnan(val) else None
    
    result["drainage"] = None  # Not available
    
    return result


def generate_soil_maps(input_geojson, output_dir, padding=0.10, resolution=250, single_field_id=None):
    """Generate soil maps for all fields in GeoJSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading fields from {input_geojson}...")
    gdf = parse_geojson(input_geojson)

    if "field_id" not in gdf.columns:
        gdf["field_id"] = [f"field_{i}" for i in range(len(gdf))]

    if single_field_id:
        gdf = gdf[gdf["field_id"] == single_field_id]
        if len(gdf) == 0:
            raise ValueError(f"Field ID '{single_field_id}' not found in GeoJSON")

    print(f"Processing {len(gdf)} field(s)...")

    results = []
    for idx, (_, row) in enumerate(gdf.iterrows()):
        field_id = row["field_id"]
        geometry = row.geometry

        field_output_dir = output_dir / field_id
        field_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{idx + 1}/{len(gdf)}] Processing {field_id}...")

        padded_bounds = calculate_padded_bounds(geometry.bounds, padding)
        print(f"  Bounds: {geometry.bounds}")
        print(f"  Padded: {padded_bounds}")

        print(f"  Querying SoilGrids WCS API...")
        
        try:
            property_stats = generate_soil_property_tifs(
                padded_bounds,
                field_output_dir,
                field_id,
                resolution
            )
        except Exception as e:
            print(f"  ERROR: Failed to generate soil maps for {field_id}: {e}")
            continue

        print(f"  Generated {len(property_stats)} property TIFs")

        # Get centroid values
        # Create dummy arrays for centroid calculation
        dummy_arrays = {}
        for prop_key in SOILGRIDS_PROPERTIES:
            tif_path = field_output_dir / f"{field_id}_{prop_key}.tif"
            if tif_path.exists():
                with rasterio.open(tif_path) as src:
                    dummy_arrays[prop_key] = src.read(1)
        
        centroid_values = get_centroid_soil_values(geometry, dummy_arrays, resolution)

        metadata = {
            "field_id": field_id,
            "centroid_values": centroid_values,
            "properties": property_stats,
            "spatial": {
                "bounds": list(padded_bounds),
                "crs": "EPSG:4326",
                "resolution_m": resolution,
                "padding_pct": int(padding * 100),
            },
            "data_source": "ISRIC SoilGrids250m",
            "resolution_note": "SoilGrids provides 250m resolution - significantly coarser than SSURGO (~10m). This is a fundamental limitation of global soil data.",
            "limitations": [
                "250m resolution (vs ~10m for US SSURGO)",
                "Drainage class not available",
                "AWC approximated from wilting point (wfc layer)"
            ]
        }

        metadata_path = field_output_dir / f"{field_id}_soil_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"  Metadata: {metadata_path}")

        results.append({
            "field_id": field_id,
            "output_dir": str(field_output_dir),
            "property_stats": property_stats,
        })

    print(f"\n=== Summary ===")
    print(f"Total fields: {len(gdf)}")
    print(f"Processed: {len(results)}")
    print(f"Output: {output_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate soil property maps from field boundary GeoJSON - GLOBAL VERSION"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to GeoJSON file with field boundaries",
    )
    parser.add_argument(
        "--output-dir",
        default="soil_maps_global",
        help="Output directory (default: soil_maps_global)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.10,
        help="Padding around polygon bounds as fraction (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=250,
        help="Target resolution in meters (default: 250)",
    )
    parser.add_argument(
        "--field-id",
        default=None,
        help="Process single field by ID (default: all fields)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Soil Map Generation (Global - SoilGrids)")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output_dir}")
    print(f"Padding: {args.padding * 100:.0f}%")
    print(f"Resolution: {args.resolution}m (SoilGrids native)")
    print("WARNING: SoilGrids resolution (250m) is much coarser than SSURGO (~10m)")
    if args.field_id:
        print(f"Field ID: {args.field_id}")
    print("-" * 60)

    try:
        results = generate_soil_maps(
            args.input,
            args.output_dir,
            padding=args.padding,
            resolution=args.resolution,
            single_field_id=args.field_id,
        )
        print("\n" + "=" * 60)
        print("Done!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
