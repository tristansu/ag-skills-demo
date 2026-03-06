#!/usr/bin/env python3
"""
Master script to generate all data for assignment-03 field map web application.

This script orchestrates the entire data generation pipeline:
1. Field boundaries (from USDA NASS or user-provided)
2. Weather data (NASA POWER)
3. Soil data (NRCS SSURGO)
4. Merge into single GeoJSON
5. DEM/elevation overlays (USGS 3DEP)
6. Satellite imagery and vegetation indices (Copernicus)
7. Weather averages for display
8. Soil polygons and overlays (NRCS SSURGO)

Usage:
    python scripts/generate_assignment_03b.py \\
        --state OR \\
        --region "Willamette Valley" \\
        --n-fields 50 \\
        --crop-codes 24,36,37,38,74,75 \\
        --min-acres 10 \\
        --satellite-date 2024-07-15 \\
        --output-dir docs/assignment-03b

Requirements:
    pip install geopandas pandas numpy matplotlib requests rasterio Pillow

API Access (automatic for public data):
    NASA POWER: No key required
    USGS 3DEP: No key required
    NRCS Soil Data Access: No key required
    Copernicus Data Space: Credentials hardcoded (demo purposes)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_script(script_path, *args, capture_output=True):
    """Run a Python script and return the result."""
    cmd = [sys.executable, str(script_path)] + list(args)
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=True
        )
        if capture_output and result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Script {script_path} failed with return code {e.returncode}")
        if capture_output and e.stderr:
            print(f"STDERR: {e.stderr[:1000]}")
        return False
    except FileNotFoundError:
        print(f"ERROR: Script not found: {script_path}")
        return False


def parse_crop_codes(codes_str):
    """Parse comma-separated crop codes into a list."""
    if not codes_str:
        return [24, 36, 37, 74, 75]  # Default: winter wheat, alfalfa, other hay, horticulture, berries
    return [int(x.strip()) for x in codes_str.split(',')]


def main():
    parser = argparse.ArgumentParser(
        description="Generate all data for assignment-03 field map web application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate for Oregon with default settings (50 fields, specialty crops)
    python scripts/generate_assignment_03b.py

    # Generate for specific region with custom date
    python scripts/generate_assignment_03b.py --state OR --satellite-date 2024-07-15

    # Generate for different crop types
    python scripts/generate_assignment_03b.py --crop-codes 24,27,38 --n-fields 100

    # Generate for different output directory
    python scripts/generate_assignment_03b.py --output-dir docs/my_custom_map
        """
    )
    
    parser.add_argument(
        '--state',
        type=str,
        default='OR',
        help='US state abbreviation (default: OR)'
    )
    
    parser.add_argument(
        '--region',
        type=str,
        default='willamette_valley',
        help='Region name within state (default: willamette_valley)'
    )
    
    parser.add_argument(
        '--n-fields',
        type=int,
        default=50,
        help='Number of fields to process (default: 50)'
    )
    
    parser.add_argument(
        '--crop-codes',
        type=str,
        default='24,36,37,38,74,75',
        help='Comma-separated CDL crop codes (default: 24,36,37,38,74,75)'
    )
    
    parser.add_argument(
        '--min-acres',
        type=float,
        default=10,
        help='Minimum field size in acres (default: 10)'
    )
    
    parser.add_argument(
        '--satellite-date',
        type=str,
        default='2024-07-15',
        help='Target date for satellite imagery YYYY-MM-DD (default: 2024-07-15)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='docs/assignment-03',
        help='Output directory for web files (default: docs/assignment-03)'
    )
    
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip steps if output files already exist'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )
    
    args = parser.parse_args()
    
    # Parse crop codes
    crop_codes = parse_crop_codes(args.crop_codes)
    crop_codes_str = ','.join(map(str, crop_codes))
    
    print("=" * 70)
    print("Assignment-03b Data Generation Pipeline")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  State:           {args.state}")
    print(f"  Region:          {args.region}")
    print(f"  Fields:          {args.n_fields}")
    print(f"  Crop codes:      {crop_codes_str}")
    print(f"  Min acres:       {args.min_acres}")
    print(f"  Satellite date:  {args.satellite_date}")
    print(f"  Output dir:      {args.output_dir}")
    print("=" * 70)
    
    if args.dry_run:
        print("\nDry run complete. No files were generated.")
        print("\nWould execute these steps:")
        print("  1. get_specialty_fields.py")
        print("  2. get_weather.py")
        print("  3. get_soil.py")
        print("  4. merge_field_data.py")
        print("  5. generate_dem_png.py")
        print("  6. generate_satellite_rasters.py")
        print("  7. generate_satellite_png.py")
        print("  8. add_weather_averages.py")
        print("  9. generate_ssurgo_polygons.py")
        print("  10. generate_soil_overlays.py")
        return
    
    # Define base paths
    base_dir = Path("data")
    web_dir = Path(args.output_dir)
    scripts_dir = Path("scripts")
    
    # Create necessary directories
    print("\nCreating output directories...")
    (base_dir / args.state.lower()).mkdir(exist_ok=True)
    (base_dir / "assignment-03").mkdir(exist_ok=True)
    (web_dir).mkdir(parents=True, exist_ok=True)
    (web_dir / "satellite").mkdir(exist_ok=True)
    (web_dir / "dem").mkdir(exist_ok=True)
    (web_dir / "soil").mkdir(exist_ok=True)
    (web_dir / "soil_data").mkdir(exist_ok=True)
    
    success_count = 0
    error_count = 0
    
    # Step 1: Get field boundaries
    print("\n" + "="*70)
    print("STEP 1: Get Field Boundaries")
    print("="*70)
    fields_file = base_dir / f"assignment-02/fields_{args.state.lower()}_{args.region.lower().replace(' ', '_')}_ag_2025.geojson"
    if args.skip_existing and fields_file.exists():
        print(f"Skipping - file exists: {fields_file}")
    else:
        # Build the script arguments
        script_args = [
            "--state", args.state,
            "--region", args.region,
            "--n-fields", str(args.n_fields),
            "--crop-codes", crop_codes_str,
            "--min-acres", str(args.min_acres),
            "--output", str(fields_file)
        ]
        if run_script(scripts_dir / "get_specialty_fields.py", *script_args):
            success_count += 1
        else:
            error_count += 1
    
    # Step 2: Get weather data
    print("\n" + "="*70)
    print("STEP 2: Get Weather Data")
    print("="*70)
    weather_file = base_dir / f"assignment-02/weather_{args.region.lower().replace(' ', '_')}_ag_2020_2025.csv"
    if args.skip_existing and weather_file.exists():
        print(f"Skipping - file exists: {weather_file}")
    else:
        if run_script(scripts_dir / "get_weather.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 3: Get soil data
    print("\n" + "="*70)
    print("STEP 3: Get Soil Data")
    print("="*70)
    soil_file = base_dir / f"assignment-02/soil_{args.state.lower()}_{args.region.lower().replace(' ', '_')}_ag_2025.csv"
    if args.skip_existing and soil_file.exists():
        print(f"Skipping - file exists: {soil_file}")
    else:
        if run_script(scripts_dir / "get_soil.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 4: Merge field data
    print("\n" + "="*70)
    print("STEP 4: Merge Field Data")
    print("="*70)
    merged_file = base_dir / "assignment-03/fields_complete.geojson"
    if args.skip_existing and merged_file.exists():
        print(f"Skipping - file exists: {merged_file}")
    else:
        if run_script(scripts_dir / "merge_field_data.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 5: Generate DEM overlays
    print("\n" + "="*70)
    print("STEP 5: Generate DEM Overlays")
    print("="*70)
    dem_dir = web_dir / "dem"
    if args.skip_existing and (dem_dir / "dem_bounds.json").exists():
        print(f"Skipping - file exists: {dem_dir / 'dem_bounds.json'}")
    else:
        # Generate DEM PNGs
        if run_script(scripts_dir / "generate_dem_png.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 6: Generate satellite rasters
    print("\n" + "="*70)
    print("STEP 6: Generate Satellite Rasters")
    print("="*70)
    satellite_dir = base_dir / "assignment-03/satellite"
    if args.skip_existing and len(list(satellite_dir.glob("*.tif"))) > 0:
        print(f"Skipping - {len(list(satellite_dir.glob('*.tif')))} TIFFs exist")
    else:
        if run_script(scripts_dir / "generate_satellite_rasters.py", "--date", args.satellite_date):
            success_count += 1
        else:
            error_count += 1
    
    # Step 7: Generate satellite PNGs
    print("\n" + "="*70)
    print("STEP 7: Generate Satellite PNGs")
    print("="*70)
    web_satellite_dir = web_dir / "satellite"
    if args.skip_existing and len(list(web_satellite_dir.glob("*.png"))) > 0:
        print(f"Skipping - {len(list(web_satellite_dir.glob('*.png')))} PNGs exist")
    else:
        if run_script(scripts_dir / "generate_satellite_png.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 8: Add weather averages
    print("\n" + "="*70)
    print("STEP 8: Add Weather Averages")
    print("="*70)
    wgs84_file = web_dir / "fields_complete_wgs84.geojson"
    if args.skip_existing and wgs84_file.exists():
        # Check if weather_avg_monthly exists
        import json
        with open(wgs84_file) as f:
            data = json.load(f)
            if 'weather_avg_monthly' in data.get('features', [{}])[0].get('properties', {}):
                print("Skipping - weather_avg_monthly already exists")
            else:
                if run_script(scripts_dir / "add_weather_averages.py"):
                    success_count += 1
                else:
                    error_count += 1
    else:
        if run_script(scripts_dir / "add_weather_averages.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 9: Generate SSURGO soil polygons
    print("\n" + "="*70)
    print("STEP 9: Generate SSURGO Soil Polygons")
    print("="*70)
    soil_data_dir = web_dir / "soil_data"
    if args.skip_existing and (soil_data_dir / "ssurgo_polygons.geojson").exists():
        print(f"Skipping - file exists: {soil_data_dir / 'ssurgo_polygons.geojson'}")
    else:
        if run_script(scripts_dir / "generate_ssurgo_polygons.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Step 10: Generate soil overlays
    print("\n" + "="*70)
    print("STEP 10: Generate Soil Overlays")
    print("="*70)
    soil_dir = web_dir / "soil"
    if args.skip_existing and len(list(soil_dir.glob("*.png"))) > 0:
        print(f"Skipping - {len(list(soil_dir.glob('*.png')))} PNGs exist")
    else:
        if run_script(scripts_dir / "generate_soil_overlays.py"):
            success_count += 1
        else:
            error_count += 1
    
    # Summary
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"Steps completed successfully: {success_count}")
    print(f"Steps with errors: {error_count}")
    print(f"\nOutput directory: {web_dir}")
    print(f"\nNext steps:")
    print(f"  1. Copy field_map_7b.html to {web_dir}/ if not present")
    print(f"  2. Start local server: cd {web_dir} && python -m http.server 8000")
    print(f"  3. Open in browser: http://localhost:8000/field_map_7b.html")
    print("="*70)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
