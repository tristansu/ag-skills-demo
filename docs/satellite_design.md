# Satellite Raster Generation for Assignment-03 Fields

_Design document for generating per-field satellite vegetation index rasters using Sentinel-2 data_

---

## Overview

Generate raw Float32 GeoTIFF raster images for vegetation indices (NDVI, MSAVI, EVI, NDMI) for each field in `fields_complete.geojson` using Sentinel-2 imagery from Copernicus Data Space. These rasters are displayed as colored overlays in the field_map_8.html web application.

## Input

| Item              | Path                                         |
| ----------------- | -------------------------------------------- |
| Source GeoJSON    | `data/assignment-03/fields_complete.geojson` |
| Field Count       | 50 fields                                    |
| Coordinate System | EPSG:4326 (WGS84)                            |

## Output

| Item             | Path                              |
| ---------------- | --------------------------------- |
| Output Directory | `data/assignment-03/satellite/`   |
| File Pattern     | `{field_id}_{index}.tif`          |
| Total Files      | 200 (50 fields × 4 indices)       |
| Format           | Float32 GeoTIFF                   |
| Resolution       | 10m native (square ground pixels) |

---

## Satellite Indices

| Index | Full Name                               | Formula                                       | Bands Used             | Range   |
| ----- | --------------------------------------- | --------------------------------------------- | ---------------------- | ------- |
| NDVI  | Normalized Difference Vegetation Index  | (B08 - B04) / (B08 + B04)                     | B04 (Red), B08 (NIR)   | -1 to 1 |
| MSAVI | Modified Soil-Adjusted Vegetation Index | (2×B08 + 1 - √((2×B08+1)² - 8×(B08-B04))) / 2 | B04, B08               | -1 to 1 |
| EVI   | Enhanced Vegetation Index               | 2.5 × (B08 - B04) / (B08 + 2.4×B04 + 1)       | B04, B08               | -1 to 1 |
| NDMI  | Normalized Difference Moisture Index    | (B08 - B11) / (B08 + B11)                     | B08 (NIR), B11 (SWIR1) | -1 to 1 |

---

## Data Source

- **Platform**: Copernicus Data Space (dataspace.copernicus.eu)
- **Product**: Sentinel-2 Level-2A (S2MSI2A)
- **Resolution**: 10m (native)
- **API**: Copernicus Process API
- **Date Range**: 2024-04-01 to 2024-09-30 (growing season)

---

## Implementation

### Script: `scripts/generate_satellite_rasters.py`

1. Load `fields_complete.geojson`
2. For each field:
   - Get bounding box in WGS84
   - Apply 10% padding to bounds
   - Calculate output dimensions: `width = field_width_m / 10`, `height = field_height_m / 10` (minimum 5×5)
   - Request Float32 GeoTIFF from Process API with evalscript for each index
   - Save as raw Float32 GeoTIFF

### Degree-to-Meter Conversion

Uses haversine formula at field centroid latitude:

```python
meters_per_degree_lat = 111320
meters_per_degree_lon = 111320 * cos(radians(lat_center))
```

### Dependencies

```bash
pip install geopandas numpy requests rasterio
```

### Credentials

Hardcoded in script (for demo purposes):

- `CLIENT_ID`: sh-b7c9d9d1-9963-4f33-a0aa-0c8cffa4a246
- `CLIENT_SECRET`: cMwfrjg1uUVTUrXepNpR8pgiOiHKjDcL

---

## Web Visualization: field_map_8.html

### Location

`docs/assignment-03/field_map_8.html`

### Features

- Displays fields from `fields_complete.geojson`
- Dropdown to select satellite metric (NDVI, MSAVI, EVI, NDMI)
- Checkbox to toggle satellite overlay display
- Opacity slider for overlay adjustment
- Colorbar showing scale for selected metric

### Colormaps

| Index | Range    | Color Scheme                            | Description                      |
| ----- | -------- | --------------------------------------- | -------------------------------- |
| NDVI  | -0.2-1.0 | viridis-like (purple→blue→green→yellow) | Low vegetation → High vegetation |
| MSAVI | -0.2-1.0 | viridis-like (purple→blue→green→yellow) | Low vegetation → High vegetation |
| EVI   | -0.2-1.0 | viridis-like (purple→blue→green→yellow) | Low vegetation → High vegetation |
| NDMI  | -0.5-0.6 | Blues reversed (blue→white→brown)       | Wet → Dry                        |

### DEM Overlays

- Uses same DEM overlays as field_map_5.html
- Located in `docs/assignment-03/dem/` (copied from assignment-02)
- Colormap: inferno (brown→yellow→green, low→high elevation)

### Data Flow

```
User clicks field → Sidebar opens
  → User selects metric from dropdown (NDVI/MSAVI/EVI/NDMI)
  → Checkbox "Show Satellite Overlay" appears
  → User checks box → PNG overlay loads on map with colormap
  → Colorbar shows scale for selected metric
```

### Similarity to field_map_5.html

- Same layout and styling
- Same field data handling
- Same popup/chart structure
- Adds satellite metric dropdown + controls
- Adds satellite colorbar panel

---

## CLI Options

The script supports the following command-line options:

```bash
python scripts/generate_satellite_rasters.py --date 2024-07-15 --cloud-threshold 20
```

| Option              | Default      | Description                      |
| ------------------- | ------------ | -------------------------------- |
| `--date`            | Current date | Target date in YYYY-MM-DD format |
| `--cloud-threshold` | 30           | Max cloud cover percentage       |

### Date Selection Logic

1. User provides target date (or defaults to today)
2. Script searches ±30 days from target for Sentinel-2 scenes
3. Filters by cloud cover ≤ threshold
4. Selects scene with date closest to target
5. Falls back to ±60 day window if no scenes found
6. Saves actual acquisition date to `satellite_dates.json`

## Metadata Output

| File                                      | Description                                                       |
| ----------------------------------------- | ----------------------------------------------------------------- |
| `data/assignment-03/satellite_dates.json` | Maps each field to its satellite acquisition date and cloud cover |

Example content:

```json
{
  "WV_AG_001": { "date": "2024-07-15", "cloud_cover": 12 },
  "WV_AG_002": { "date": "2024-08-02", "cloud_cover": 8 }
}
```

This metadata can be displayed in the web UI to show when the satellite imagery was captured.

## Status

| Task                     | Status |
| ------------------------ | ------ |
| Design doc created       | ✓      |
| Script created           | ✓      |
| Run for all fields       | ✓      |
| field_map_8.html created | ✓      |
| DEM folder copied        | ✓      |
| Date selection added     | ✓      |

---

# Assignment-03b: SSURGO Soil Overlays

_Extension to field_map_8.html that adds SSURGO soil type overlays_

## Overview

Add SSURGO (Soil Survey Geographic Database) soil polygon overlays to the field map. Uses NRCS Soil Data Access API to download soil boundaries and properties, then renders them as colored PNG overlays similar to the satellite and DEM overlays.

## Input

| Item             | Path                                                   |
| ---------------- | ------------------------------------------------------ |
| Source GeoJSON   | `docs/assignment-03/fields_complete_wgs84.geojson`     |
| Field Count      | 50 fields                                              |
| Soil Data Source | NRCS Soil Data Access (sdmdataaccess.sc.egov.usda.gov) |

## Output

| Item             | Path                             |
| ---------------- | -------------------------------- |
| Output Directory | `docs/assignment-03/soil/`       |
| File Pattern     | `soil_{field_id}_{property}.png` |
| Total Files      | ~300 (50 fields × 6 properties)  |
| Format           | 8-bit PNG with alpha             |

## Soil Properties

| Property       | Column      | Units       | Range     | Type        |
| -------------- | ----------- | ----------- | --------- | ----------- |
| pH             | ph1to1h2o_r | pH          | 4.0 - 7.5 | Continuous  |
| Organic Matter | om_r        | %           | 0 - 10    | Continuous  |
| Clay %         | claytotal_r | %           | 0 - 50    | Continuous  |
| Sand %         | sandtotal_r | %           | 0 - 80    | Continuous  |
| CEC            | cec7_r      | meq/100g    | 0 - 40    | Continuous  |
| Drainage Class | drainagecl  | categorical | 6 classes | Categorical |

## Colormaps

| Property       | Colormap Name | Color Scheme                   |
| -------------- | ------------- | ------------------------------ |
| pH             | viridis       | Purple → Blue → Green → Yellow |
| Organic Matter | greens        | Light green → Dark green       |
| Clay %         | oranges       | Light orange → Dark orange     |
| Sand %         | yellows       | Light yellow → Dark yellow     |
| CEC            | purples       | Light purple → Dark purple     |
| Drainage Class | drainage      | Categorical (see below)        |

### Drainage Class Colors

| Drainage Class               | Color      | Hex     |
| ---------------------------- | ---------- | ------- |
| Well drained                 | Green      | #2ecc71 |
| Somewhat poorly drained      | Yellow     | #f1c40f |
| Poorly drained               | Orange     | #e67e22 |
| Very poorly drained          | Red        | #e74c3c |
| Somewhat excessively drained | Light Blue | #3498db |
| Excessively drained          | Blue       | #2980b9 |
| Not rated                    | Gray       | #95a5a6 |

---

## Implementation

### Script: `scripts/generate_ssurgo_polygons.py`

1. Load field boundaries from GeoJSON
2. For each field:
   - Query NRCS Soil Data Access API for soil polygons (mupolygons)
   - Join with soil property data
3. Save spatial boundaries to `ssurgo_polygons.geojson`
4. Save property data to `ssurgo_properties.csv`

### Script: `scripts/generate_soil_overlays.py`

1. Load SSURGO polygons from `ssurgo_polygons.geojson`
2. For each field + property combination:
   - Render PNG with appropriate colormap
   - Apply 10% padding (same as satellite)
3. Save bounds to `soil_bounds.json` for web display

### Web Visualization: field_map_8.html

### Location

`docs/assignment-03/field_map_8.html`

### New Features

- Soil property dropdown selector (pH, OM, Clay, Sand, CEC, Drainage)
- Checkbox to toggle soil overlay display
- Opacity slider for overlay adjustment
- Colorbar showing scale for selected soil property

### Data Flow

```
User clicks field → Sidebar opens
  → User selects soil property from dropdown (pH/OM/Clay/Sand/CEC/Drainage)
  → Checkbox "Show Soil Overlay" appears
  → User checks box → PNG overlay loads on map with colormap
  → Colorbar shows scale for selected property
```

### UI Components

- `soilMetrics` JavaScript object (similar to `satelliteMetrics`)
- `toggleSoilOverlay()` function
- `soilPropertyChanged()` function
- Load `soil/soil_bounds.json` at startup (like dem_bounds.json)

### Directory Structure

```
docs/assignment-03/
├── field_map_8.html           # Modified HTML with soil overlay features
├── fields_complete_wgs84.geojson # Copy from assignment-03
├── fields_complete.geojson       # Copy from assignment-03
├── satellite/                    # Copy from assignment-03
├── dem/                          # Copy from assignment-03
├── soil/                         # NEW - SSURGO PNG overlays
│   ├── soil_WV_AG_001_ph.png
│   ├── soil_WV_AG_001_om.png
│   ├── ...
│   └── soil_bounds.json
└── soil_data/                    # NEW - Raw SSURGO data
    ├── ssurgo_polygons.geojson
    └── ssurgo_properties.csv
```

### Scripts Created

| Script                                | Purpose                           |
| ------------------------------------- | --------------------------------- |
| `scripts/setup_assignment_03b.py`     | Set up directory and copy files   |
| `scripts/generate_ssurgo_polygons.py` | Download SSURGO soil polygons     |
| `scripts/generate_soil_overlays.py`   | Render PNG overlays from polygons |

## Status

| Task                                | Status  |
| ----------------------------------- | ------- |
| Design doc updated                  | ✓       |
| Directory created                   | ✓       |
| Files copied                        | ✓       |
| SSURGO polygons downloaded          | ✓       |
| generate_ssurgo_polygons.py created | ✓       |
| generate_soil_overlays.py created   | ✓       |
| field_map_8.html created            | ✓       |
| Soil overlay UI in HTML             | ✓       |
| Testing/verification                | Pending |

---

## References

- `.agents/skills/ssurgo-soil/SKILL.md` - SSURGO soil processing workflow
- <https://sdmdataaccess.nrcs.usda.gov/> - NRCS Soil Data Access API
- `docs/assignment-03/field_map_8.html` - Base template

---

## References

- `.agents/skills/sentinel2-imagery/SKILL.md` - Sentinel-2 processing workflow
- <https://documentation.dataspace.copernicus.eu/> - Copernicus API docs
- `docs/assignment-02/field_map_5.html` - Base template for web visualization
