# Data Regeneration and Analysis Status - March 9, 2026

## Overview

This document tracks the regeneration of geospatial data for 50 agricultural fields in Oregon's Willamette Valley and subsequent correlation analysis in the notebook.

---

## Data Generation Summary

| Component                          | Fields | Status      | Resolution         | Output Location                                              |
| ---------------------------------- | ------ | ----------- | ------------------ | ------------------------------------------------------------ |
| Satellite (NDVI, NDMI, MSAVI, EVI) | 50     | ✅ Complete | ~10m               | `/data/satellite/`                                           |
| Terrain (elevation, slope, aspect) | 50     | ✅ Complete | 5m → 10m resampled | `/data/terrain/`, `/data/terrain_resampled/`                 |
| Soil Types                         | 50     | ✅ Complete | 5m                 | `/data/soil/`                                                |
| Soil Properties                    | 50×7   | ✅ Complete | 5m → 10m resampled | `/data/soil_properties/`, `/data/soil_properties_resampled/` |
| Solar Radiation                    | 50×13  | ✅ Complete | 5m                 | `/data/solar/`                                               |

**Total: 2,300+ files generated**

---

## Phase 1: Data Generation ✅ COMPLETE

### Key Scripts Used

| Script                                                | Purpose                                                    |
| ----------------------------------------------------- | ---------------------------------------------------------- |
| `scripts/lat_lon_polygon_to_dem_slope_aspect.py`      | Terrain (DEM, slope, aspect)                               |
| `scripts/lat_lon_polygon_to_ssurgo_soil.py`           | SSURGO soil types                                          |
| `scripts/generate_soil_property_rasters.py`           | Soil property rasters (pH, OM, clay, sand, silt, CEC, AWC) |
| `scripts/generate_satellite_rasters.py`               | Satellite imagery (Sentinel-2)                             |
| `scripts/lat_lon_polygon_to_solar_radiation_daily.py` | Solar radiation                                            |
| `scripts/resample_rasters.py`                         | Resample terrain/soil to 10m                               |

### Key Fixes Applied

1. **Copernicus API**: Switched from deprecated catalog API to STAC API
2. **Padding**: Changed from 10% to 15% on all rasters
3. **MultiPolygon support**: Added to terrain and solar scripts
4. **Path updates**: All scripts now use new `data/` structure

### Batch Scripts Created

- `scripts/batch_terrain.py` - Process all 50 fields for terrain
- `scripts/batch_soil.py` - Process all 50 fields for SSURGO soil
- `scripts/batch_solar.py` - Process all 50 fields for solar radiation

---

## Phase 2: PNG Generation ✅ COMPLETE

| Type       | Script                              | Output                         |
| ---------- | ----------------------------------- | ------------------------------ |
| Terrain    | `scripts/generate_terrain_png.py`   | 150 PNGs in `/data/terrain/`   |
| Soil Types | `scripts/generate_soil_png.py`      | 50 PNGs in `/data/soil/`       |
| Satellite  | `scripts/generate_satellite_png.py` | 200 PNGs in `/data/satellite/` |

### Slope PNG Fix (March 9, 2026)

**Issue**: Slope PNGs appeared washed out due to fixed colormap range (0-45°) while actual values were 0-6° for most fields.

**Fix**: Changed `scripts/generate_terrain_png.py` line 19:

```python
# Before
"slope": ("YlOrRd", 0, 45),

# After
"slope": ("YlOrRd", None, None),  # Auto-scale to actual data range
```

**Output**: `data/terrain/slope_ranges.json` created with per-field statistics for colorbar generation.

---

## Phase 3: Notebook Analysis ✅ COMPLETE

**File**: `notebooks/field_mapping_04.ipynb`

### Fixes Applied

1. **SOIL_PROPERTIES list**: Extended from 5 to 7 properties:

   ```python
   SOIL_PROPERTIES = ['ph', 'om_pct', 'clay_pct', 'sand_pct', 'cec', 'awc', 'silt_pct']
   ```

2. **Data paths**: Updated all directory references:
   - `data/assignment-03/` → `docs/assignment-03/`
   - `data/assignment-04/terrain` → `data/terrain`
   - `data/assignment-04/soil` → `data/soil`
   - `data/assignment-03/soil_properties` → `data/soil_properties`
   - `data/assignment-03/satellite` → `data/satellite`

3. **Slope data path**: Fixed to load from correct location:

   ```python
   slope_df = pd.read_csv(f'{PROJECT_ROOT}/data/field_slope_aspect.csv')
   ```

4. **Added `SOIL_PROPS_RESAMPLED_DIR`** for correlation analysis

### Correlation Analysis Verified ✅

The notebook correctly implements pixel-by-pixel correlations:

- `calculate_pixel_correlation()` properly handles NaN and nodata values
- Uses resampled 10m terrain and soil property rasters to match satellite resolution
- Computes Pearson correlation with statistical significance

### Known Limitation

- `SOIL_PROPERTY_DISPLAY` dict still missing `'silt_pct'` and `'awc'` entries (cosmetic only - correlations work fine)

---

## File Inventory

| Category                | Count | Location                           |
| ----------------------- | ----- | ---------------------------------- |
| Satellite TIFs          | 200   | `/data/satellite/`                 |
| Satellite PNGs          | 200   | `/data/satellite/`                 |
| Terrain TIFs            | 150   | `/data/terrain/`                   |
| Terrain PNGs            | 150   | `/data/terrain/`                   |
| Terrain Resampled       | 150   | `/data/terrain_resampled/`         |
| Soil Type TIFs          | 50    | `/data/soil/`                      |
| Soil Type PNGs          | 50    | `/data/soil/`                      |
| Soil Type JSONs         | 50    | `/data/soil/`                      |
| Soil Property TIFs      | 350   | `/data/soil_properties/`           |
| Soil Property Resampled | 350   | `/data/soil_properties_resampled/` |
| Solar TIFs              | 650   | `/data/solar/`                     |
| Slope Ranges JSON       | 1     | `/data/terrain/slope_ranges.json`  |

---

## Notes

- All outputs use EPSG:4326 (WGS84) coordinate system
- All rasters have 15% padding around field boundaries
- Two fields (WV_AG_029, WV_AG_038) initially failed terrain generation but were recovered
- The notebook runs correlation analysis on 4 randomly selected fields (seed=42)
