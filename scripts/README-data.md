# Data Acquisition Scripts

Self-contained scripts for generating agricultural data for Oregon Willamette Valley fields.

## Scripts

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
