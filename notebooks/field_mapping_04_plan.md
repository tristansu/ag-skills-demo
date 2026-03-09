# Field Mapping 04 - Spatial Correlation Analysis Plan

## Overview

Create a Jupyter notebook analyzing spatial correlations between satellite metrics, soil properties, and terrain data for 4 randomly selected fields (from all 50). All 50 fields will have terrain/soil TIFFs generated; correlation analysis focuses on 4 fields.

---

## Data Available

| Data Type     | Location                                     | Format  | Metrics/Properties                                    |
| ------------- | -------------------------------------------- | ------- | ----------------------------------------------------- |
| **Fields**    | `data/assignment-03/fields_complete.geojson` | GeoJSON | 50 fields with metadata                               |
| **Satellite** | `data/assignment-03/satellite/`              | GeoTIFF | ndvi, msavi, evi, ndmi (~10m resolution)              |
| **Terrain**   | `data/assignment-04/terrain/`                | GeoTIFF | elevation, slope, aspect (~5-10m resolution)          |
| **Soil**      | `data/assignment-04/soil/`                   | GeoTIFF | ph, om_pct, clay_pct, sand_pct, cec (via labels.json) |

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
SOIL_PROPERTIES = ['ph', 'om_pct', 'clay_pct', 'sand_pct', 'cec']  # Internal names; displayed as ph, om, clay, sand, cec
TERRAIN_PROPERTIES = ['elevation', 'slope', 'aspect']
```

### Function 1: Resample Raster to Match Reference

```python
from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio
import numpy as np

def resample_to_match(source_path, reference_path, output_path):
    """Resample source raster to match reference raster resolution using bilinear interpolation."""
    with rasterio.open(reference_path) as ref:
        ref_crs = ref.crs
        ref_width = ref.width
        ref_height = ref.height

    with rasterio.open(source_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, ref_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({'crs': ref_crs, 'transform': transform, 'width': width, 'height': height})

        if output_path:
            # Write resampled raster to file
            with rasterio.open(output_path, 'w', **kwargs) as dst:
                for i in range(1, src.count + 1):
                    data = src.read(i)
                    result = np.zeros((height, width), dtype=data.dtype)
                    reproject(
                        source=data, destination=result,
                        src_transform=src.transform, src_crs=src.crs,
                        dst_transform=transform, dst_crs=ref_crs,
                        resampling=Resampling.bilinear
                    )
                    dst.write(result, i)
            return output_path
        else:
            # Return in-memory resampled array
            result = np.zeros((height, width), dtype=src.dtypes[0])
            reproject(source=src.read(1), destination=result,
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=transform, dst_crs=ref_crs,
                      resampling=Resampling.bilinear)
            return result
```

### Function 2: Convert Soil Mukey to Property Values

```python
def load_soil_with_properties(soil_tiff_path, labels_json_path, property_column):
    """Convert soil mukey integers to property values using labels JSON."""
    with open(labels_json_path) as f:
        labels = json.load(f)

    # Build mapping from label_id to property value
    label_to_mukey = labels.get('label_to_mukey', {})
    soil_defs = labels.get('soil_definitions', {})

    label_to_value = {}
    for label_id, mukey_str in label_to_mukey.items():
        soil_def = soil_defs.get(label_id, {})
        value = soil_def.get(property_column)
        if value:
            label_to_value[int(label_id)] = float(value)

    # Load TIFF and convert
    with rasterio.open(soil_tiff_path) as src:
        data = src.read(1)

    output = np.full_like(data, np.nan, dtype=np.float64)
    for label_id, value in label_to_value.items():
        output[data == label_id] = value

    return output
```

### Function 3: Calculate Correlation with Valid Pixels (with NoData handling)

```python
def calculate_pixel_correlation(array1, array2, min_pixels=MIN_PIXEL_COUNT, nodata_value=-9999):
    """Calculate Pearson correlation between two arrays, handling NoData."""
    # Create combined valid mask - exclude NoData from both arrays
    valid_mask = ~np.isnan(array1) & ~np.isnan(array2)
    if nodata_value is not None:
        valid_mask = valid_mask & (array1 != nodata_value) & (array2 != nodata_value)

    valid_count = np.sum(valid_mask)
    if valid_count < min_pixels:
        return np.nan, np.nan, valid_count

    x = array1[valid_mask]
    y = array2[valid_mask]

    # Check for constant arrays
    if np.std(x) == 0 or np.std(y) == 0:
        return np.nan, np.nan, valid_count

    r, p = stats.pearsonr(x, y)
    return r, p, valid_count
```

### Function 3B: Polygon-Based Soil Correlation

```python
def calculate_polygon_correlation(soil_tiff_path, sat_tiff_path, labels_json_path, property_column):
    """
    Calculate correlation between satellite values and soil properties at the polygon level.

    For each soil polygon:
    1. Extract mask for that polygon (where soil_tiff equals the polygon label)
    2. Calculate mean satellite value within that polygon
    3. Get the soil property value for that polygon from labels JSON
    4. After processing all polygons, calculate correlation across polygons (not pixels)
    """
    # Load labels
    with open(labels_json_path) as f:
        labels = json.load(f)

    # Load soil raster and satellite raster
    with rasterio.open(soil_tiff_path) as src:
        soil_data = src.read(1)

    with rasterio.open(sat_tiff_path) as src:
        sat_data = src.read(1)

    # Match shapes
    min_h = min(sat_data.shape[0], soil_data.shape[0])
    min_w = min(sat_data.shape[1], soil_data.shape[1])
    sat_crop = sat_data[:min_h, :min_w]
    soil_crop = soil_data[:min_h, :min_w]

    # For each soil polygon (label), compute mean satellite value
    polygon_means = []
    polygon_values = []

    label_to_mukey = labels.get('label_to_mukey', {})
    soil_defs = labels.get('soil_definitions', {})

    for label_id, mukey_str in label_to_mukey.items():
        label_int = int(label_id)
        soil_def = soil_defs.get(label_id, {})
        property_value = soil_def.get(property_column)

        if property_value is None:
            continue

        # Mask for this polygon
        polygon_mask = (soil_crop == label_int)

        if np.sum(polygon_mask) == 0:
            continue

        # Mean satellite value in this polygon
        sat_values_in_polygon = sat_crop[polygon_mask]
        sat_mean = np.nanmean(sat_values_in_polygon)

        polygon_means.append(sat_mean)
        polygon_values.append(float(property_value))

    # Calculate correlation across polygons (not pixels)
    if len(polygon_means) < 3:
        return np.nan, np.nan, len(polygon_means)

    r, p = stats.pearsonr(polygon_means, polygon_values)
    return r, p, len(polygon_means)
```

### Function 3C: Get Polygon Statistics

```python
def get_polygon_stats(soil_tiff_path, sat_tiff_path, labels_json_path, property_column):
    """Get per-polygon statistics for display."""
    with open(labels_json_path) as f:
        labels = json.load(f)

    with rasterio.open(soil_tiff_path) as src:
        soil_data = src.read(1)

    with rasterio.open(sat_tiff_path) as src:
        sat_data = src.read(1)

    min_h = min(sat_data.shape[0], soil_data.shape[0])
    min_w = min(sat_data.shape[1], soil_data.shape[1])
    sat_crop = sat_data[:min_h, :min_w]
    soil_crop = soil_data[:min_h, :min_w]

    results = []
    label_to_mukey = labels.get('label_to_mukey', {})
    soil_defs = labels.get('soil_definitions', {})

    for label_id, mukey_str in label_to_mukey.items():
        label_int = int(label_id)
        soil_def = soil_defs.get(label_id, {})
        property_value = soil_def.get(property_column)

        if property_value is None:
            continue

        polygon_mask = (soil_crop == label_int)
        if np.sum(polygon_mask) == 0:
            continue

        sat_mean = np.nanmean(sat_crop[polygon_mask])
        sat_std = np.nanstd(sat_crop[polygon_mask])

        results.append({
            'polygon': label_id,
            'soil_type': soil_def.get('muname', 'Unknown'),
            'property_value': float(property_value),
            'sat_mean': sat_mean,
            'sat_std': sat_std,
            'n_pixels': np.sum(polygon_mask)
        })

    return results
```

### Function 4: Load TIFF with Valid Mask

```python
def load_tiff(tiff_path):
    """Load TIFF file and return data array and valid pixel mask."""
    with rasterio.open(tiff_path) as src:
        data = src.read(1)
        valid_mask = ~np.isnan(data)
        if src.nodata is not None:
            valid_mask = valid_mask & (data != src.nodata)
    return data, valid_mask
```

### Function 5: Get or Resample Terrain

```python
def get_or_resample_terrain(field_id, terrain_prop, satellite_metric='ndvi'):
    """Get terrain data, resampling to match satellite resolution if needed."""
    terr_path = f'{TERRAIN_DIR}/{field_id}_{terrain_prop}.tif'
    sat_path = f'{SATELLITE_DIR}/{field_id}_{satellite_metric}.tif'
    resampled_path = f'{TERRAIN_RESAMPLED_DIR}/{field_id}_{terrain_prop}_{satellite_metric}.tif'

    if os.path.exists(resampled_path):
        return load_tiff(resampled_path)

    if os.path.exists(terr_path) and os.path.exists(sat_path):
        resample_to_match(terr_path, sat_path, resampled_path)
        return load_tiff(resampled_path)

    return None, None
```

### Function 6: Plot Raster with Colorbar and Scale Bar

```python
def plot_raster_with_scale(data, title, cmap='viridis', vmin=None, vmax=None,
                           units='', figsize=(8, 6), nodata=-9999,
                           transform=None, extent=None, add_bounds=None):
    """Plot a raster with colorbar, scale bar, and proper scaling."""
    fig, ax = plt.subplots(figsize=figsize)

    # Handle NoData
    plot_data = data.copy().astype(float)
    plot_data = np.where(data == nodata, np.nan, data)

    # Auto vmin/vmax if not specified
    if vmin is None:
        vmin = np.nanpercentile(plot_data, 2)
    if vmax is None:
        vmax = np.nanpercentile(plot_data, 98)

    # Plot with extent if provided
    if extent:
        im = ax.imshow(plot_data, cmap=cmap, vmin=vmin, vmax=vmax,
                      extent=extent, origin='upper')
    else:
        im = ax.imshow(plot_data, cmap=cmap, vmin=vmin, vmax=vmax)

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, label=units, shrink=0.8)

    # Scale bar
    height, width = data.shape
    scale_length = width // 5
    scale_meters = int(scale_length * 10)  # Approximate
    ax.plot([10, 10 + scale_length], [height - 15, height - 15], 'k-', lw=3)
    ax.text(width // 2, height - 8, f'~{scale_meters}m', ha='center',
           fontsize=9, color='white', fontweight='bold')

    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.axis('off')

    # Add field boundary if provided
    if add_bounds:
        for poly_coords in add_bounds:
            xs, ys = zip(*(list(poly_coords) + [list(poly_coords[0])]))
            ax.plot(xs, ys, 'r-', lw=2)
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)

    return fig, ax
```

### Function 7: Add Field Boundary to Plot

```python
def get_field_boundary_coords(field_id):
    """Get field boundary coordinates from geojson."""
    field_geom = gdf[gdf['field_id'] == field_id].geometry.iloc[0]

    if field_geom.geom_type == 'Polygon':
        return [list(field_geom.exterior.coords)]
    elif field_geom.geom_type == 'MultiPolygon':
        return [list(p.exterior.coords) for p in field_geom.geoms]
    return None
```

### Function 8: Interactive Scatter Plot

```python
def plot_correlation_scatter(x_data, y_data, x_label, y_label, field_id,
                            correlation_r, correlation_p, figsize=(6, 5)):
    """Create scatter plot with regression line and correlation stats."""
    fig, ax = plt.subplots(figsize=figsize)

    valid_mask = ~np.isnan(x_data) & ~np.isnan(y_data)
    x_valid = x_data[valid_mask]
    y_valid = y_data[valid_mask]

    ax.scatter(x_valid, y_valid, alpha=0.4, s=15, c='steelblue', edgecolors='none')

    if not np.isnan(correlation_r) and np.std(x_valid) > 0 and np.std(y_valid) > 0:
        z = np.polyfit(x_valid, y_valid, 1)
        p = np.poly1d(z)
        x_line = np.linspace(x_valid.min(), x_valid.max(), 100)
        ax.plot(x_line, p(x_line), 'r-', lw=2, label=f'r = {correlation_r:.3f}')

        sig_star = '***' if correlation_p < 0.001 else ('**' if correlation_p < 0.01 else ('*' if correlation_p < 0.05 else ''))
        ax.text(0.05, 0.95, f'p = {correlation_p:.2e} {sig_star}',
               transform=ax.transAxes, fontsize=10, va='top')

    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)
    ax.set_title(f'{field_id}: {x_label} vs {y_label}', fontsize=11, fontweight='bold')

    if not np.isnan(correlation_r):
        ax.legend(loc='lower right')

    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig
```

---

## Colormap Specifications

| Data Type | Property  | Colormap   | Rationale                              |
| --------- | --------- | ---------- | -------------------------------------- |
| Satellite | NDVI      | `RdYlGn`   | Red=low, Yellow=medium, Green=high     |
| Satellite | MSAVI     | `viridis`  | Sequential green to yellow             |
| Satellite | EVI       | `viridis`  | Sequential                             |
| Satellite | NDMI      | `RdBu`     | Blue=wet, Red=dry                      |
| Terrain   | Elevation | `terrain`  | Green-low, brown-high, white-peaks     |
| Terrain   | Slope     | `Greys`    | Linear (darker=steeper)                |
| Terrain   | Aspect    | `hsv`      | Circular (north=red)                   |
| Soil      | pH        | `coolwarm` | Diverging: acidic-neutral-alkaline     |
| Soil      | OM        | `YlGn`     | Sequential: light=low, dark=high       |
| Soil      | Clay      | `YlOrBr`   | Sequential: light=low, dark=high       |
| Soil      | Sand      | `YlGnBu`   | Sequential: light=sand, dark=less sand |
| Soil      | CEC       | `Purples`  | Sequential: light=low, dark=high       |

---

## Notebook Structure

### Section 1: Setup & Imports

- Import: pandas, numpy, matplotlib, seaborn, rasterio, rasterio.warp, geopandas, scipy.stats, json, os, random, ipywidgets
- Seed: 42
- Configurable Parameters at top of notebook

### Section 2: Helper Functions

All 8 functions defined above

### Section 3: Data Loading

- Load `fields_complete.geojson` → gdf
- Load `field_slope_aspect.csv` → slope_df

### Section 4: Field Selection

- Randomly select 4 fields (seed=42)
- Display table: field_id, area_acres, cdl_crop, lat, lon

### Section 5: Per-Field Image Maps (REVISED)

For each field:

**5.1 Satellite Maps**

- 2x2 grid: ndvi, msavi, evi, ndmi
- Colormap specifications above
- Colorbar, scale bar, field boundary overlay

**5.2 Terrain Maps**

- 1x3 grid: elevation, slope, aspect
- Handle NoData (-9999)
- Field boundary overlay

**5.3 Soil Property Maps**

- 2x3 grid: ph, om, clay, sand, cec
- Field boundary overlay

### Section 6: Per-Field Histograms (UNCHANGED)

- Existing histogram code preserved

### Section 7: Spatial Correlation Analysis

**7.0 Interactive Correlation Explorer (NEW)**

- Widgets: Field dropdown, Satellite dropdown, Terrain/Soil radio, Property dropdown
- Output: Scatter plot + Correlation heatmap for selected field/data type

**7.1 Satellite vs Soil Correlations (POLYGON-BASED)**

- For each soil polygon: calculate mean satellite value within polygon
- Correlate polygon-level means with soil property values from labels JSON
- Report number of polygons instead of number of pixels
- Note: This is required because SSURGO soil data represents soil map units, not continuous pixel values

**7.2 Satellite vs Terrain Correlations** (UPDATED)

- NoData values (-9999) now masked in correlation calculations
- Uses updated `calculate_pixel_correlation` function with nodata parameter

**7.3 Key Findings** (EXISTING)

---

## Interactive Explorer Widget Layout

```
┌─────────────────────────────────────────────────┐
│  Field: [WV_AG_041 ▼]                           │
│  Satellite: [ndvi ▼]                            │
│  Compare to: ○ Terrain  ● Soil                  │
│  Property: [ph ▼]                               │
├─────────────────────────────────────────────────┤
│                                                 │
│           Scatter Plot                          │
│                                                 │
├─────────────────────────────────────────────────┤
│    Correlation Heatmap                          │
│    (ALL satellite vs ALL terrain/soil)         │
└─────────────────────────────────────────────────┘
```

---

## Output Files

```
/data/assignment-04/
├── terrain/                              (existing)
├── terrain_resampled/                    (existing)
├── soil/                                 (existing)

/notebooks/
├── field_mapping_04_plan.md              (this document)
└── field_mapping_04.ipynb                 (main notebook)
```

---

## Execution Order

1. **Run terrain/soil generation scripts** - DONE
2. **Build notebook** with helper functions - DONE
3. **Add new helper functions** (6, 7, 8)
4. **Update Section 5** with image map code
5. **Add Section 7.0** interactive explorer
6. **Test and verify** all sections work

---

## Implementation Status

- [x] Terrain generation (all 50 fields)
- [x] Soil generation (all 50 fields)
- [x] Basic notebook with correlations
- [x] Planning document updated
- [x] Image maps with scaling (Section 5)
- [x] Interactive explorer (Section 7.0)
- [x] Fix image display (Section 5 - use fig.savefig instead of plt.show)
- [x] Fix soil correlation (Section 7.1 - polygon-based analysis)
- [x] Fix terrain NoData (Section 7.2 - mask -9999 in correlations)
- [x] Fix terrain aspect ratio (Section 5 - use resampled terrain to match satellite)
- [x] Fix field boundaries (Section 5 - overlay red boundary on all images)

---

## Fixes Applied (March 2025)

### Fix 1: Image Display

- Changed from `plt.show()` to `fig.savefig()` with explicit close
- Ensures images are properly captured in nbconvert output

### Fix 2: Polygon-Based Soil Correlation

- Replaced per-pixel correlation with polygon-level analysis
- Now calculates mean satellite value per soil polygon
- Correlates polygon means with soil property values
- Reports number of polygons instead of pixels

### Fix 3: Terrain NoData Masking

- Updated `calculate_pixel_correlation` to accept nodata parameter
- Terrain NoData values (-9999) now masked in correlation calculations
- Also masked in visualization (via `load_tiff_with_nodata`)

### Fix 4: Terrain Aspect Ratio (March 9, 2025)

- Section 5 now uses `get_or_resample_terrain()` to load terrain resampled to match satellite resolution
- All terrain images now have same dimensions as satellite images
- Uses `ndvi` as the reference satellite metric for resampling

### Fix 5: Field Boundaries (March 9, 2025)

- Added `get_field_boundary_coords()` calls to Section 5
- Red boundary lines now overlaid on satellite, terrain, and soil images
- Uses consistent boundary for all data types within each field
