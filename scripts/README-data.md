# Data Acquisition Scripts

Self-contained scripts for generating agricultural data for Oregon Willamette Valley fields (US) and globally.

## US vs Global Scripts

This project has two versions of map generation scripts:

| Category   | US Version                    | Global Version                       | Data Source                    |
| ---------- | ----------------------------- | ------------------------------------ | ------------------------------ |
| Topography | `generate_topography_maps.py` | `generate_topography_maps_global.py` | USGS 3DEP vs Copernicus GLO-30 |
| Soil       | `generate_soil_maps.py`       | `generate_soil_maps_global.py`       | NRCS SSURGO vs SoilGrids       |
| Solar      | `generate_solar_maps.py`      | `generate_solar_maps_global.py`      | USGS 3DEP vs Copernicus GLO-30 |

### When to Use Which Version

- **US Version**: Fields in the United States — higher resolution (5-10m)
- **Global Version**: Fields outside the US — uses Copernicus GLO-30 (30m) and SoilGrids (250m)

### Resolution Comparison

| Data Type | US (SSURGO/3DEP) | Global (SoilGrids/Copernicus) |
| --------- | ---------------- | ----------------------------- |
| Elevation | 5-10m            | 30m                           |
| Soil      | ~10m             | 250m                          |

### Important Global Limitations

- **Soil resolution**: SoilGrids at 250m is significantly coarser than SSURGO (~10m)
- **Drainage class**: Not available in SoilGrids output
- **GLO-30 restrictions**: Some countries (Armenia, Azerbaijan, etc.) have restricted tiles — fallback to GLO-90 is automatic

---

## Scripts (US Version)

| Script                    | Description                                    | Output                                    |
| ------------------------- | ---------------------------------------------- | ----------------------------------------- |
| `get_field_boundaries.py` | Downloads USDA NASS CSB, extracts 50 WV fields | `fields_oregon_willamette_2025.geojson`   |
| `get_cdl_crops.py`        | Extracts CDL 2024 crop data for each field     | `cdl_oregon_willamette_2025.csv`          |
| `get_soil.py`             | Queries NRCS SSURGO API for soil properties    | `soil_oregon_willamette_2025.csv`         |
| `get_weather.py`          | Queries NASA POWER API for daily weather       | `weather_oregon_willamette_2020_2025.csv` |

## Usage

Run scripts in order:

```bash
# 1. Get field boundaries (downloads ~3.4GB, may take time)
python scripts/get_field_boundaries.py

# 2. Get CDL crop data
python scripts/get_cdl_crops.py

# 3. Get soil data
python scripts/get_soil.py

# 4. Get weather data
python scripts/get_weather.py
```

## Dependencies

Scripts will auto-install required packages. Alternatively:

```bash
pip install geopandas pandas requests rasterio shapely pyproj
```

## Data Sources

| Dataset          | Source                             | API/URL                                                                    |
| ---------------- | ---------------------------------- | -------------------------------------------------------------------------- |
| Field Boundaries | USDA NASS Crop Sequence Boundaries | <https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/> |
| Crop Data        | USDA NASS CDL                      | <https://nassgeodata.gmu.edu/CropScape/>                                   |
| Soil Data        | NRCS SSURGO                        | <https://sdmdataaccess.sc.egov.usda.gov/>                                  |
| Weather Data     | NASA POWER                         | <https://power.larc.nasa.gov/>                                             |

## Output

All outputs go to `data/assignment-02/`:

```
data/assignment-02/
├── fields_oregon_willamette_2025.geojson   # 50 field polygons
├── cdl_oregon_willamette_2025.csv           # CDL crop data
├── soil_oregon_willamette_2025.csv           # SSURGO soil data
└── weather_oregon_willamette_2020_2025.csv  # Daily weather
```

---

## Global Map Generation Scripts

Scripts for generating maps outside the US:

| Script                               | Description                                  | Output Directory          |
| ------------------------------------ | -------------------------------------------- | ------------------------- |
| `generate_topography_maps_global.py` | Elevation, slope, aspect from Copernicus DEM | `topography_maps_global/` |
| `generate_soil_maps_global.py`       | Soil properties from SoilGrids (250m)        | `soil_maps_global/`       |
| `generate_solar_maps_global.py`      | Solar radiation from Copernicus DEM          | `solar_maps_global/`      |

### Dependencies

```bash
pip install dem-stitcher owslib
```

### Usage

```bash
# Generate topography (Germany example)
python scripts/generate_topography_maps_global.py \
    --input data/fields_germany.geojson \
    --output-dir ./topography_maps_global \
    --field-id DE_FIELD_001

# Generate soil (Germany example)
python scripts/generate_soil_maps_global.py \
    --input data/fields_germany.geojson \
    --output-dir ./soil_maps_global \
    --field-id DE_FIELD_001

# Generate solar (Germany example)
python scripts/generate_solar_maps_global.py \
    --input data/fields_germany.geojson \
    --output-dir ./solar_maps_global \
    --field-id DE_FIELD_001 \
    --time-resolution monthly
```

### Global Data Sources

| Dataset           | Source                             | Resolution | Coverage |
| ----------------- | ---------------------------------- | ---------- | -------- |
| Elevation         | Copernicus GLO-30 / GLO-90         | 30m / 90m  | Global   |
| Soil              | ISRIC SoilGrids250m                | 250m       | Global   |
| Solar Calculation | From Copernicus DEM (slope/aspect) | 30m        | Global   |
