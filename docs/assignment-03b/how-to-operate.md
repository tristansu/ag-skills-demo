# How to Operate: Assignment-03b Field Map Generation

This document provides comprehensive instructions for generating all data required for the interactive field map web application, from initial field boundaries to final satellite, DEM, and soil overlays.

## Overview

The field map web application (`field_map_7b.html`) displays agricultural fields with:

- **Field polygons** colored by crop type
- **Satellite overlays** (NDVI, MSAVI, EVI, NDMI)
- **DEM overlays** showing elevation
- **Soil overlays** showing SSURGO soil properties (pH, OM, Clay, Sand, CEC, Drainage)
- **Weather data** displayed in popups
- **Soil data** displayed in popups

This guide explains how to generate all required data files from scratch.

---

## Prerequisites

### System Requirements

- **Python**: 3.12 or higher
- **Disk Space**: ~500MB for 50 fields (more for larger datasets)
- **Internet**: Required for API access (NASA, USGS, Copernicus, NRCS)

### Python Dependencies

Install required packages:

```bash
pip install geopandas pandas numpy matplotlib requests rasterio Pillow
```

### API Credentials

The following APIs are used (some have free tiers):

| API                   | Purpose                  | Credential Required    |
| --------------------- | ------------------------ | ---------------------- |
| NASA POWER            | Weather data             | No (public)            |
| USGS 3DEP             | Elevation/DEM            | No (public)            |
| Copernicus Data Space | Satellite imagery        | Yes (included in code) |
| NRCS Soil Data Access | Soil polygons/properties | No (public)            |

---

## Input Configuration

Before running the pipeline, determine your inputs:

| Parameter            | Description                       | Example             |
| -------------------- | --------------------------------- | ------------------- |
| **State**            | US state abbreviation             | OR, WA, ID          |
| **Region**           | Named region within state         | "Willamette Valley" |
| **Number of fields** | How many fields to process        | 50                  |
| **Crop codes**       | CDL crop codes to filter          | 24, 36, 37, 74, 75  |
| **Minimum acres**    | Minimum field size                | 10                  |
| **Satellite date**   | Target date for satellite imagery | 2024-07-15          |

### Common Crop Codes

| Code | Crop                           |
| ---- | ------------------------------ |
| 24   | Winter Wheat                   |
| 27   | Spring Wheat                   |
| 36   | Alfalfa                        |
| 37   | Other Hay                      |
| 38   | Small Grains                   |
| 74   | Horticulture (includes grapes) |
| 75   | Berries                        |
| 204  | Christmas Trees                |

---

## Step-by-Step Pipeline

The data generation pipeline consists of 11 steps. Each step builds on the output of previous steps.

---

### Step 1: Get Field Boundaries

**Script**: `scripts/get_specialty_fields.py`

**Purpose**: Download USDA NASS Crop Sequence Boundaries and filter to desired fields

**What it does**:

1. Downloads the national CSB dataset (if not cached)
2. Filters to specified state and bounding box
3. Filters to specified crop types
4. Filters to fields >= minimum acres
5. Samples the specified number of fields

**Usage**:

```bash
python scripts/get_specialty_fields.py \
    --state OR \
    --region willamette_valley \
    --n-fields 50 \
    --crop-codes 24,36,37,38,74,75 \
    --min-acres 10
```

**Output**:

- `data/assignment-02/fields_oregon_willamette_ag_2025.geojson`

**If fields already exist**, you can skip this step and provide your own GeoJSON with field boundaries.

---

### Step 2: Get Weather Data

**Script**: `scripts/get_weather.py`

**Purpose**: Fetch historical weather data from NASA POWER for each field

**What it does**:

1. Loads field boundaries
2. Calculates centroid for each field
3. Queries NASA POWER API for each field
4. Downloads daily temperature, precipitation, radiation, humidity, wind

**Usage**:

```bash
python scripts/get_weather.py
```

**Configuration** (edit in script or use defaults):

- `START_DATE`: "20200101"
- `END_DATE`: "20251231"
- `PARAMS`: "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,RH2M,WS10M"

**Output**:

- `data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv`

---

### Step 3: Get Soil Data

**Script**: `scripts/get_soil.py`

**Purpose**: Download SSURGO soil properties from NRCS Soil Data Access

**What it does**:

1. Loads field boundaries
2. Queries NRCS SDA API for each field centroid
3. Downloads soil properties (pH, OM, texture, drainage, CEC)

**Usage**:

```bash
python scripts/get_soil.py
```

**Output**:

- `data/assignment-02/soil_oregon_willamette_ag_2025.csv`

---

### Step 4: Merge Field Data

**Script**: `scripts/merge_field_data.py`

**Purpose**: Combine all data sources into a single GeoJSON

**What it does**:

1. Loads field boundaries
2. Loads and joins CDL crop data
3. Loads and joins soil data (selects dominant soil per field)
4. Loads and joins weather data
5. Converts to WGS84 (EPSG:4326) for web display

**Usage**:

```bash
python scripts/merge_field_data.py
```

**Output**:

- `data/assignment-02/fields_complete.geojson` (original CRS)
- `data/assignment-03/fields_complete.geojson` (copy)
- `docs/assignment-03/fields_complete_wgs84.geojson` (WGS84 for web)

---

### Step 5: Generate DEM Rasters

**Scripts**:

- `scripts/generate_elevation_rasters.py` (raw rasters)
- `scripts/generate_dem_png.py` (colored overlays)

**Purpose**: Fetch elevation data from USGS and create colored overlays

**What it does**:

1. Loads field boundaries
2. For each field:
   - Queries USGS 3DEP API for elevation
   - Applies 20% padding to bounds
   - Downloads raster at 10m resolution
   - Applies inferno colormap
   - Saves as PNG

**Usage**:

```bash
# First generate raw rasters (optional - generate_dem_png does both)
# python scripts/generate_elevation_rasters.py

# Then generate PNG overlays
python scripts/generate_dem_png.py
```

**Output**:

- `data/assignment-03/dem/dem_{field_id}.tif` (raw)
- `docs/assignment-03/dem/dem_{field_id}.png` (colored overlay)
- `docs/assignment-03/dem/dem_bounds.json` (bounds for web display)

---

### Step 6: Generate Satellite Rasters

**Script**: `scripts/generate_satellite_rasters.py`

**Purpose**: Download Sentinel-2 imagery and compute vegetation indices

**What it does**:

1. For each field:
   - Searches for Sentinel-2 scene closest to target date (±30 days)
   - Filters by cloud cover (<30%)
   - Downloads scene
   - Computes NDVI, MSAVI, EVI, NDMI indices

**Usage**:

```bash
python scripts/generate_satellite_rasters.py --date 2024-07-15
```

**Configuration**:

- `--date`: Target date (YYYY-MM-DD format)
- `--cloud-threshold`: Maximum cloud cover percentage (default: 30)

**Output**:

- `data/assignment-03/satellite/{field_id}_{index}.tif` (for each index)
- `data/assignment-03/satellite_dates.json` (metadata)

---

### Step 7: Generate Satellite PNGs

**Script**: `scripts/generate_satellite_png.py`

**Purpose**: Apply colormaps to satellite rasters for web display

**What it does**:

1. Loads satellite TIFFs
2. Applies colormap based on index type
3. Saves as PNG with transparency

**Colormap Configuration**:

| Index | Colormap | Range       |
| ----- | -------- | ----------- |
| NDVI  | viridis  | -0.2 to 1.0 |
| MSAVI | plasma   | -0.2 to 1.0 |
| EVI   | magma    | -0.2 to 1.0 |
| NDMI  | Blues_r  | -0.5 to 0.6 |

**Usage**:

```bash
python scripts/generate_satellite_png.py
```

**Output**:

- `docs/assignment-03/satellite/{field_id}_{index}.png`

---

### Step 8: Add Weather Averages

**Script**: `scripts/add_weather_averages.py`

**Purpose**: Pre-compute monthly weather averages for web display

**What it does**:

1. Loads weather data from GeoJSON
2. Groups by month across all years
3. Computes averages for avg_high_c, avg_low_c, avg_rain_in
4. Adds weather_avg_monthly property

**Usage**:

```bash
python scripts/add_weather_averages.py
```

**Output**:

- Updates `docs/assignment-03/fields_complete_wgs84.geojson` with weather_avg_monthly

---

### Step 9: Generate SSURGO Soil Polygons

**Script**: `scripts/generate_ssurgo_polygons.py`

**Purpose**: Download soil polygon boundaries from NRCS

**What it does**:

1. Loads field boundaries
2. For each field:
   - Queries NRCS SDA for mukeys intersecting field
   - Gets soil polygon geometries
   - Joins with soil properties

**Usage**:

```bash
python scripts/generate_ssurgo_polygons.py
```

**Output**:

- `docs/assignment-03b/soil_data/ssurgo_polygons.geojson`
- `docs/assignment-03b/soil_data/ssurgo_properties.csv`

---

### Step 10: Generate Soil Overlays

**Script**: `scripts/generate_soil_overlays.py`

**Purpose**: Render soil properties as colored PNG overlays

**What it does**:

1. Loads soil polygons and properties
2. Merges data
3. For each field and property:
   - Renders polygon with appropriate colormap
   - Adds field boundary outline
   - Saves as PNG

**Soil Properties**:

| Property       | Colormap    | Range     |
| -------------- | ----------- | --------- |
| pH             | viridis     | 4.0 - 7.5 |
| Organic Matter | greens      | 0 - 10%   |
| Clay %         | oranges     | 0 - 50%   |
| Sand %         | yellows     | 0 - 80%   |
| CEC            | purples     | 0 - 40    |
| Drainage       | categorical | 6 classes |

**Usage**:

```bash
python scripts/generate_soil_overlays.py
```

**Output**:

- `docs/assignment-03b/soil/soil_{field_id}_{property}.png` (300 files for 50 fields × 6 properties)
- `docs/assignment-03b/soil/soil_bounds.json`

---

### Step 11: Setup Web Directory

**Manual Step**: Copy/create the web directory structure

The web application requires:

```
docs/assignment-03b/
├── field_map_7b.html           # Web interface (pre-built template)
├── fields_complete_wgs84.geojson  # Field data
├── satellite/                  # Satellite PNGs (Step 7)
├── dem/                        # DEM PNGs + bounds.json (Step 5)
├── soil/                       # Soil PNGs + bounds.json (Step 10)
└── soil_data/                  # Raw SSURGO data (Step 9)
```

**Note**: `field_map_7b.html` is a pre-built template that includes all the JavaScript for:

- Popup displays with charts
- Overlay toggles (satellite, DEM, soil)
- Colorbar rendering
- Opacity sliders

---

## Master Script

Instead of running each step manually, use the master script:

```bash
python scripts/generate_assignment_03b.py \
    --state OR \
    --region "Willamette Valley" \
    --n-fields 50 \
    --crop-codes 24,36,37,38,74,75 \
    --min-acres 10 \
    --satellite-date 2024-07-15 \
    --output-dir docs/assignment-03b
```

This script:

1. Creates necessary directories
2. Runs all generation steps in sequence
3. Reports progress and any errors
4. Provides a summary when complete

---

## Expected Output Summary

For 50 fields, you should generate:

| Data Type      | Count     | Location                       |
| -------------- | --------- | ------------------------------ |
| Field GeoJSON  | 2 files   | docs/assignment-03/            |
| Satellite PNGs | 200 files | docs/assignment-03/satellite/  |
| DEM PNGs       | ~45 files | docs/assignment-03/dem/        |
| Soil PNGs      | 300 files | docs/assignment-03b/soil/      |
| Bounds JSON    | 3 files   | Various                        |
| Raw SSURGO     | 2 files   | docs/assignment-03b/soil_data/ |

**Total**: ~550 files, ~400MB

---

## Troubleshooting

### Common Issues

**API Rate Limits**

- Copernicus has rate limits. If you get errors, wait and retry.
- The scripts include basic error handling but may need adjustment for high volumes.

**No Satellite Data**

- If target date is in winter, there may be no suitable Sentinel-2 scenes
- Try a summer date (June-August)

**Missing Soil Data**

- Some areas don't have SSURGO coverage
- Fields may have "No data" for certain properties

**Memory Issues**

- If processing fails, try reducing the number of fields
- Some operations load all data into memory

---

## Testing the Web Application

After generating all data:

1. Start a local web server:

   ```bash
   cd docs/assignment-03b
   python -m http.server 8000
   ```

2. Open in browser:

   ```
   http://localhost:8000/field_map_7b.html
   ```

3. Test features:
   - Click on a field to see popup with charts
   - Select satellite metric and toggle overlay
   - Select DEM and toggle overlay
   - Select soil property and toggle overlay
   - Use opacity sliders
   - Click Clear button to reset

---

## File Locations Summary

| Step | Output File                                        | Used By       |
| ---- | -------------------------------------------------- | ------------- |
| 1    | `data/assignment-02/fields_*.geojson`              | Steps 2, 3, 4 |
| 2    | `data/assignment-02/weather_*.csv`                 | Step 4        |
| 3    | `data/assignment-02/soil_*.csv`                    | Step 4        |
| 4    | `docs/assignment-03/fields_complete_wgs84.geojson` | Web app       |
| 5    | `docs/assignment-03/dem/*.png`                     | Web app       |
| 7    | `docs/assignment-03/satellite/*.png`               | Web app       |
| 8    | (updates GeoJSON)                                  | Web app       |
| 9    | `docs/assignment-03b/soil_data/*.geojson`          | Step 10       |
| 10   | `docs/assignment-03b/soil/*.png`                   | Web app       |

---

## Questions?

If you encounter issues or need to modify the pipeline:

- Check API documentation for rate limits and available parameters
- Review script comments for configuration options
- See `data/assignment-03/satellite_design.md` for additional design details
