#!/usr/bin/env python3
"""
Generate monthly solar radiation rasters from lat/lon polygon coordinates.

This script:
1. Takes polygon coordinates (GeoJSON or simple [lon,lat] list)
2. Fetches/generates slope and aspect rasters
3. Calculates monthly average solar radiation (MJ/m^2/day) for each pixel
4. Outputs 12 GeoTIFFs (one per month)

The calculation accounts for:
- Latitude (from polygon centroid)
- Slope (from terrain)
- Aspect (from terrain, compass convention)
- Day length variation throughout the year

Usage:
    python scripts/lat_lon_polygon_to_solar_radiation.py \
        --input /path/to/polygon.geojson \
        --output-dir ./solar_output \
        --field-id my_field

    # Or with existing slope/aspect rasters:
    python scripts/lat_lon_polygon_to_solar_radiation.py \
        --input "[[-122.9,44.8],[-122.8,44.8],...]" \
        --slope-tif ./slope.tif \
        --aspect-tif ./aspect.tif \
        --output-dir ./solar_output

Output:
    {field_id}_solar_jan.tif  - January (MJ/m^2/day)
    {field_id}_solar_feb.tif  - February
    ... 
    {field_id}_solar_dec.tif  - December

Requirements:
    numpy, rasterio, geopandas
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds


# Solar constant (MJ/m^2/min)
GSC = 0.0820

# Month mapping to representative day of year (day 15 of each month)
MONTH_DAYS = {
    1: 15,   # January
    2: 46,   # February
    3: 74,   # March
    4: 105,  # April
    5: 135,  # May
    6: 166,  # June
    7: 196,  # July
    8: 227,  # August
    9: 258,  # September
    10: 288, # October
    11: 319, # November
    12: 349, # December
}

MONTH_NAMES = {
    1: 'jan', 2: 'feb', 3: 'mar', 4: 'apr',
    5: 'may', 6: 'jun', 7: 'jul', 8: 'aug',
    9: 'sep', 10: 'oct', 11: 'nov', 12: 'dec'
}


def parse_polygon_input(input_str):
    """Parse polygon input from various formats."""
    input_str = input_str.strip()

    # Check if it's a file path
    input_path = Path(input_str)
    if input_path.exists():
        with open(input_path, 'r') as f:
            data = json.load(f)
    else:
        try:
            data = json.loads(input_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input: {e}")

    # Handle GeoJSON format
    if isinstance(data, dict):
        if data.get('type') == 'Polygon':
            coords = data['coordinates'][0]
        elif data.get('type') == 'Feature' and data.get('geometry', {}).get('type') == 'Polygon':
            coords = data['geometry']['coordinates'][0]
        elif 'coordinates' in data and isinstance(data['coordinates'], list):
            coords = data['coordinates'][0] if isinstance(data['coordinates'][0], list) else data['coordinates']
        else:
            raise ValueError("Unknown GeoJSON format")
    elif isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], list) and len(data[0]) == 2:
            coords = data
        else:
            raise ValueError("Expected list of [lon, lat] pairs")
    else:
        raise ValueError("Invalid input format")

    # Calculate bounds and centroid
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    bounds = (min(lons), min(lats), max(lons), max(lats))
    centroid_lon = sum(lons) / len(lons)
    centroid_lat = sum(lats) / len(lats)

    return {
        'type': 'Polygon',
        'coordinates': [coords],
        'bounds': bounds,
        'centroid': (centroid_lon, centroid_lat)
    }


def calculate_padded_bounds(bounds, padding):
    """Apply padding to bounds."""
    minx, miny, maxx, maxy = bounds
    dx = (maxx - minx) * padding
    dy = (maxy - miny) * padding
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def calculate_day_angle(day_of_year):
    """Calculate day angle in radians."""
    return 2 * math.pi * (day_of_year - 1) / 365


def calculate_eccentricity(day_angle):
    """Calculate eccentricity correction factor."""
    return 1 + 0.033 * math.cos(day_angle)


def calculate_declination(day_of_year):
    """Calculate solar declination in degrees."""
    return 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))


def calculate_sunset_hour_angle(latitude_rad, declination_rad):
    """Calculate sunset hour angle in radians."""
    tan_product = -math.tan(latitude_rad) * math.tan(declination_rad)
    # Clamp to valid range for arccos
    tan_product = max(-1, min(1, tan_product))
    return math.acos(tan_product)


def calculate_extraterrestrial_radiation(latitude_rad, declination_rad, sunset_angle, eccentricity):
    """
    Calculate extraterrestrial radiation on horizontal surface.
    Returns Ra in MJ/m^2/day.
    """
    term1 = sunset_angle * math.sin(latitude_rad) * math.sin(declination_rad)
    term2 = math.cos(latitude_rad) * math.cos(declination_rad) * math.sin(sunset_angle)
    
    Ra = (24 * 60 / math.pi) * GSC * eccentricity * (term1 + term2)
    return max(0, Ra)


def calculate_slope_radiation_vectorized(Ra, slope_array, aspect_array, declination_rad, sunset_angle):
    """
    Calculate radiation on sloped surface for each pixel.
    
    Parameters:
        Ra: float, extraterrestrial radiation on horizontal surface
        slope_array: numpy array of slope in degrees
        aspect_array: numpy array of aspect in degrees (compass: 0=N, 90=E, 180=S, 270=W)
        declination_rad: float, solar declination in radians
        sunset_angle: float, sunset hour angle in radians
    
    Returns:
        numpy array of radiation on sloped surface (MJ/m^2/day)
    """
    # Convert aspect from compass convention to solar convention
    # Compass: 0=N, 90=E, 180=S, 270=W
    # Solar: 0=south-facing, positive=east, negative=west
    # Conversion: alpha_solar = 180 - aspect_compass
    aspect_solar = 180 - aspect_array
    
    # Convert to radians
    slope_rad = np.radians(slope_array)
    aspect_solar_rad = np.radians(aspect_solar)
    decl = declination_rad
    omega = sunset_angle
    
    # Calculate radiation on slope
    # Rs = Ra * [cos(beta)*cos(delta)*sin(omega) + (pi/180)*omega*sin(beta)*sin(alpha_solar)*sin(delta)]
    term1 = np.cos(slope_rad) * np.cos(decl) * np.sin(omega)
    term2 = (math.pi / 180) * omega * np.sin(slope_rad) * np.sin(aspect_solar_rad) * np.sin(decl)
    
    Rs = Ra * (term1 + term2)
    
    # Handle edge cases
    # Flat areas (slope ~ 0): use horizontal radiation
    flat_mask = (slope_array < 0.1) | np.isnan(slope_array)
    Rs[flat_mask] = Ra
    
    # Negative radiation (shouldn't happen but just in case)
    Rs = np.maximum(0, Rs)
    
    # Handle NaN
    Rs = np.where(np.isnan(Ra), np.nan, Rs)
    
    return Rs


def calculate_monthly_solar(latitude_deg, slope_array, aspect_array, month):
    """
    Calculate monthly average solar radiation.
    
    Parameters:
        latitude_deg: float, latitude in degrees
        slope_array: numpy array of slope in degrees
        aspect_array: numpy array of aspect in degrees
        month: int, month (1-12)
    
    Returns:
        numpy array of radiation in MJ/m^2/day
    """
    day_of_year = MONTH_DAYS[month]
    
    # Calculate solar parameters
    day_angle = calculate_day_angle(day_of_year)
    eccentricity = calculate_eccentricity(day_angle)
    declination = calculate_declination(day_of_year)
    declination_rad = math.radians(declination)
    
    latitude_rad = math.radians(latitude_deg)
    sunset_angle = calculate_sunset_hour_angle(latitude_rad, declination_rad)
    
    # Calculate horizontal radiation
    Ra = calculate_extraterrestrial_radiation(
        latitude_rad, declination_rad, sunset_angle, eccentricity
    )
    
    # Calculate slope radiation for each pixel
    Rs = calculate_slope_radiation_vectorized(
        Ra, slope_array, aspect_array, declination_rad, sunset_angle
    )
    
    return Rs


def load_raster_as_array(tif_path):
    """Load a GeoTIFF as numpy array."""
    with rasterio.open(tif_path) as src:
        data = src.read(1)
        transform = src.transform
        bounds = src.bounds
        nodata = src.nodata
        crs = src.crs
    
    # Replace nodata with NaN for processing
    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)
    
    return data, transform, bounds, crs


def save_float_geotiff(output_path, data, transform, crs="EPSG:4326", nodata=-9999):
    """Save Float32 GeoTIFF."""
    # Replace NaN with nodata
    data_clean = np.where(np.isnan(data), nodata, data).astype(np.float32)
    
    height, width = data_clean.shape
    
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "transform": transform,
        "crs": crs,
        "nodata": nodata,
    }
    
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data_clean, 1)


def fetch_slope_aspect_from_polygon(polygon_data, output_dir, resolution=5, padding=0.15):
    """Generate slope and aspect rasters from polygon using USGS 3DEP."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from lat_lon_polygon_to_dem_slope_aspect import (
        parse_polygon_input as parse_poly,
        calculate_padded_bounds as calc_bounds,
        fetch_usgs_elevation_preserving_aspect,
        fetch_usgs_elevation,
        calculate_slope_aspect,
    )
    
    bounds = polygon_data['bounds']
    padded_bounds = calculate_padded_bounds(bounds, padding)
    minx, miny, maxx, maxy = padded_bounds
    
    # Calculate dimensions
    mid_lat = (miny + maxy) / 2
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * max(0.01, abs(math.cos(math.radians(mid_lat)))))
    
    res_deg = resolution * deg_per_m_lon
    width = max(64, int(math.ceil((maxx - minx) / res_deg)))
    height = max(64, int(math.ceil((maxy - miny) / res_deg)))
    
    # Fetch DEM
    print(f"  Fetching USGS 3DEP at {resolution}m...")
    tif_bytes = fetch_usgs_elevation_preserving_aspect(padded_bounds, width, height)
    
    if tif_bytes is None and resolution == 5:
        print(f"    5m failed, trying 10m...")
        tif_bytes = fetch_usgs_elevation(padded_bounds, 10)
    
    if tif_bytes is None:
        raise RuntimeError("Failed to fetch DEM from USGS 3DEP")
    
    # Process DEM
    from rasterio.io import MemoryFile
    with MemoryFile(tif_bytes) as memfile:
        with memfile.open() as src:
            elevation = src.read(1)
            bounds = src.bounds
            transform = src.transform
            
            # Calculate slope and aspect
            print(f"  Calculating slope and aspect...")
            slope_deg, aspect_deg = calculate_slope_aspect(elevation, transform, bounds)
    
    return slope_deg, aspect_deg, transform, bounds


def generate_solar_radiation(polygon_data, output_dir, slope_tif=None, aspect_tif=None,
                            resolution=5, padding=0.15, field_id=None):
    """
    Generate monthly solar radiation rasters.
    
    Returns:
        dict with paths to generated files and metadata
    """
    # Generate field_id if not provided
    if field_id is None:
        bounds = polygon_data['bounds']
        field_id = f"polygon_{int(bounds[0]*1000)}_{int(bounds[1]*1000)}"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get latitude from centroid
    centroid_lon, centroid_lat = polygon_data['centroid']
    latitude = centroid_lat
    
    print(f"  Latitude: {latitude:.4f}°")
    
    # Load or generate slope and aspect
    if slope_tif and aspect_tif:
        print(f"  Loading slope from {slope_tif}...")
        slope_array, transform, bounds, crs = load_raster_as_array(slope_tif)
        
        print(f"  Loading aspect from {aspect_tif}...")
        aspect_array, _, _, _ = load_raster_as_array(aspect_tif)
    else:
        print(f"  Generating slope and aspect from polygon...")
        slope_array, aspect_array, transform, bounds = fetch_slope_aspect_from_polygon(
            polygon_data, output_dir, resolution, padding
        )
    
    print(f"  Array shape: {slope_array.shape}")
    
    # Generate monthly solar radiation
    output_files = {}
    
    for month in range(1, 13):
        month_name = MONTH_NAMES[month]
        print(f"  Calculating {month_name}...")
        
        # Calculate radiation for this month
        radiation = calculate_monthly_solar(latitude, slope_array, aspect_array, month)
        
        # Save to GeoTIFF
        output_path = output_dir / f"{field_id}_solar_{month_name}.tif"
        save_float_geotiff(output_path, radiation, transform, crs="EPSG:4326")
        
        output_files[month_name] = str(output_path)
        
        # Print statistics
        valid = radiation[~np.isnan(radiation)]
        if len(valid) > 0:
            print(f"    {month_name}: min={valid.min():.2f}, max={valid.max():.2f}, mean={valid.mean():.2f} MJ/m²/day")
    
    return {
        'output_dir': str(output_dir),
        'files': output_files,
        'latitude': latitude,
        'field_id': field_id,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate monthly solar radiation rasters from lat/lon polygon"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Polygon as GeoJSON string, simple [lon,lat] list, or path to .geojson file",
    )
    parser.add_argument(
        "--output-dir",
        default="solar_rasters",
        help="Output directory (default: solar_rasters)",
    )
    parser.add_argument(
        "--slope-tif",
        default=None,
        help="Path to slope GeoTIFF (optional)",
    )
    parser.add_argument(
        "--aspect-tif",
        default=None,
        help="Path to aspect GeoTIFF (optional)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=5,
        help="Resolution in meters (default: 5)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.15,
        help="Padding around polygon bounds as fraction (default: 0.15 = 15%%)",
    )
    parser.add_argument(
        "--field-id",
        default=None,
        help="Field ID for output filenames (default: auto-generated)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Monthly Solar Radiation Generation")
    print("=" * 60)
    print(f"Input: {args.input[:100]}{'...' if len(args.input) > 100 else ''}")
    print(f"Output: {args.output_dir}")
    print(f"Resolution: {args.resolution}m")
    print(f"Padding: {args.padding * 100:.0f}%")
    if args.slope_tif and args.aspect_tif:
        print(f"Slope: {args.slope_tif}")
        print(f"Aspect: {args.aspect_tif}")
    print("-" * 60)

    try:
        # Parse input
        print("Parsing input polygon...")
        polygon_data = parse_polygon_input(args.input)
        bounds = polygon_data['bounds']
        centroid = polygon_data['centroid']
        print(f"  Bounds: {bounds[0]:.6f}, {bounds[1]:.6f} to {bounds[2]:.6f}, {bounds[3]:.6f}")
        print(f"  Centroid: {centroid[0]:.6f}, {centroid[1]:.6f}")

        # Generate solar radiation
        result = generate_solar_radiation(
            polygon_data,
            args.output_dir,
            slope_tif=args.slope_tif,
            aspect_tif=args.aspect_tif,
            resolution=args.resolution,
            padding=args.padding,
            field_id=args.field_id,
        )

        print("-" * 60)
        print("Generated files:")
        for month_name, path in result['files'].items():
            print(f"  {month_name}: {path}")
        print(f"\nLatitude: {result['latitude']:.4f}°")
        print("=" * 60)
        print("Done!")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
