# Field Mapping 04 - Spatial Correlation Analysis Plan

## Overview

Create a Jupyter notebook analyzing spatial correlations between satellite metrics, soil properties, and terrain data for 4 randomly selected fields (from all 50). All 50 fields will have terrain/soil TIFFs generated; correlation analysis focuses on 4 fields.

---

## Data Available

| Data Type     | Location                                     | Format  | Metrics/Properties                       |
| ------------- | -------------------------------------------- | ------- | ---------------------------------------- |
| **Fields**    | `data/assignment-03/fields_complete.geojson` | GeoJSON | 50 fields with metadata                  |
| **Satellite** | `data/assignment-03/satellite/`              | GeoTIFF | ndvi, msavi, evi, ndmi (~10m resolution) |
| **Soil**      | `docs/assignment-03/soil/`                   | PNG     | ph, om, clay, sand, cec (skip drainage)  |

---

## Data to Generate

| Data Type         | Script                                   | Output                                   | Resolution      |
| ----------------- | ---------------------------------------- | ---------------------------------------- | --------------- |
| Terrain TIFFs     | `lat_lon_polygon_to_dem_slope_aspect.py` | elevation, slope, aspect (all 50 fields) | ~5-10m          |
| Soil TIFFs        | `lat_lon_polygon_to_ssurgo_soil.py`      | soil raster with mukeys (all 50 fields)  | ~5m             |
| Resampled Terrain | Helper function                          | Bilinear resample to match satellite     | Match satellite |
| Resampled Soil    | Helper function                          | Bilinear resample to match satellite     | Match satellite |

---

## Helper Functions (included in notebook)

### Configuration Parameter (top of notebook)

```python
MIN_PIXEL_COUNT = 30  # Minimum pixels required for valid correlation
SATELLITE_METRICS = ['ndvi', 'msavi', 'evi', 'ndmi']
SOIL_PROPERTIES = ['ph', 'om', 'clay', 'sand', 'cec']  # NO drainage
TERRAIN_PROPERTIES = ['elevation', 'slope', 'aspect']
```

### Function 1: Resample Raster to Match Reference

```python
from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio

def resample_to_match(source_path, reference_path, output_path):
    """Resample source raster to match reference raster (satellite) resolution using bilinear interpolation."""
    with rasterio.open(reference_path) as ref:
        ref_crs, ref_width, ref_height = ref.crs, ref.width, ref.height
        ref_bounds = ref.bounds

    with rasterio.open(source_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, ref_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({'crs': ref_crs, 'transform': transform, 'width': width, 'height': height})

        with rasterio.open(output_path, 'w', **kwargs) as dst:
            reproject(source=src.read(1), destination=np.zeros((height, width)),
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=transform, dst_crs=ref_crs,
                      resampling=Resampling.bilinear)
```

### Function 2: Convert Soil Mukey to Property Values

```python
def load_soil_with_properties(soil_tiff_path, labels_json_path, property_column):
    """Convert soil mukey integers to property values using labels JSON."""
    with open(labels_json_path) as f:
        labels = json.load(f)
    mukey_to_value = {int(k): v.get(property_column, np.nan) for k, v in labels.items()}

    with rasterio.open(soil_tiff_path) as src:
        data = src.read(1)
    output = np.full_like(data, np.nan, dtype=np.float64)
    for mukey, value in mukey_to_value.items():
        output[data == mukey] = value
    return output
```

### Function 3: Calculate Correlation with Valid Pixels

```python
def calculate_pixel_correlation(array1, array2, min_pixels=MIN_PIXEL_COUNT):
    """
    Calculate Pearson correlation between two masked arrays.
    Returns (r, p_value, n_pixels) or (np.nan, np.nan, 0) if insufficient valid pixels.
    """
    # Create combined valid mask
    valid_mask = ~np.isnan(array1) & ~np.isnan(array2)
    valid_count = np.sum(valid_mask)

    if valid_count < min_pixels:
        return np.nan, np.nan, valid_count

    x = array1[valid_mask]
    y = array2[valid_mask]

    r, p = stats.pearsonr(x, y)
    return r, p, valid_count
```

---

## Notebook Structure

### Section 1: Setup & Imports

- Import: pandas, numpy, matplotlib, seaborn, rasterio, rasterio.warp, geopandas, scipy.stats, json
- Seed: 42
- **Configurable Parameter**: `MIN_PIXEL_COUNT = 30` (at top of notebook)
- Define paths: satellite (`data/assignment-03/satellite/`), terrain (`data/assignment-04/terrain/`), soil (`data/assignment-04/soil/`)

### Section 2: Data Generation (execute script calls)

```bash
# Generate for all 50 fields
python scripts/lat_lon_polygon_to_dem_slope_aspect.py \
    --input data/assignment-03/fields_complete.geojson \
    --output-dir data/assignment-04/terrain --padding 0.2

python scripts/lat_lon_polygon_to_ssurgo_soil.py \
    --input data/assignment-03/fields_complete.geojson \
    --output-dir data/assignment-04/soil --padding 0.2
```

### Section 3: Data Loading

- Load `fields_complete.geojson` → gdf
- Load `field_slope_aspect.csv` → slope_df

### Section 4: Field Selection

- Randomly select 4 fields (seed=42)
- Display table: field_id, area_acres, cdl_crop, lat, lon

### Section 5: Per-Field Visualizations (4 subsections, one per field)

For each field:

- **CDL Map**: Plot field polygon colored by cdl_crop
- **Soil Maps**: 2x3 grid of soil property PNGs (ph, om, clay, sand, cec) — **NO drainage**
- **Terrain Maps**: 1x3 grid (dem, slope, aspect) from PNGs
- **Satellite Maps**: 2x2 grid (ndvi, msavi, evi, ndmi) from TIFFs

### Section 6: Per-Field Histograms (4 subsections)

For each field:

- **Satellite Histograms**: 2x2 grid - load each TIFF, extract valid pixels, plot histogram with KDE. Statistics table below.
- **Terrain Histograms**: 1x3 grid - load resampled terrain TIFFs, plot histograms with KDE. Statistics table.

### Section 7: Spatial Correlation Analysis

**7.1 Satellite vs Soil Correlations**

- Loop through each of 4 fields
- For each satellite metric in SATELLITE_METRICS:
  - Load satellite TIFF → extract valid pixels
  - For each soil property in SOIL_PROPERTIES:
    - Load soil TIFF + labels JSON → convert to property values → extract valid pixels
    - Align pixel arrays (matching valid mask)
    - Calculate Pearson r and p-value using `calculate_pixel_correlation()`
- **Output table**: Field | Satellite | Soil Property | r | p-value | n_pixels | Significant (Y/N)
- **Heatmap**: Rows = field+metric combinations, Cols = soil properties
- **Summary**: Mean r, std, count significant (p<0.05)

**7.2 Satellite vs Terrain Correlations**

- Loop through each of 4 fields
- For each satellite metric:
  - Load satellite TIFF → extract valid pixels
  - For each terrain property:
    - Load resampled terrain TIFF → extract valid pixels
    - Align pixel arrays
    - Calculate Pearson r and p-value
- **Output table**: Field | Satellite | Terrain Property | r | p-value | n_pixels | Significant (Y/N)
- **Heatmap**: Rows = field+metric combinations, Cols = terrain properties
- **Summary**: Mean r, std, count significant (p<0.05)

**7.3 Key Findings**

- List all significant correlations (p < 0.05) from both analyses
- Narrative: Which soil properties most correlated with which satellite indices?
- Narrative: Which terrain property shows strongest satellite correlation?
- Compare: Soil vs Terrain - which explains more satellite variance?

---

## Output Files

```
/data/assignment-04/
├── terrain/
│   ├── WV_AG_001_elevation.tif, slope.tif, aspect.tif
│   └── ... (50 fields x 3)
├── terrain_resampled/        # After resampling
│   └── ...
├── soil/
│   ├── WV_AG_001_soil.tif, _labels.json
│   └── ... (50 fields x 2)
└── soil_resampled/           # After resampling
    └── ...

/notebooks/
└── field_mapping_04.ipynb    # Main notebook
```

---

## Execution Order

1. **Create /notebooks/field_mapping_04_plan.md** (this document)
2. **Run terrain generation script** (all 50 fields)
3. **Run soil generation script** (all 50 fields)
4. **Build notebook** with helper functions and visualization code
5. **Process fields one at a time** for correlation (clear memory between)
6. **Generate all tables and heatmaps** in notebook
