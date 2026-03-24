# PR: Soil Map Generation Script

## Summary

Create a production-ready script to generate soil property maps from field boundary GeoJSONs, outputting float GeoTIFFs for soil properties and JSON metadata.

## Scope

### Inputs

- GeoJSON file with field boundaries (Polygon or MultiPolygon)
- Must be in WGS84 (EPSG:4326)

### Outputs

Per field, in a single output folder:

| File                            | Description              | Format            |
| ------------------------------- | ------------------------ | ----------------- |
| `{field_id}_om_pct.tif`         | Organic Matter           | Float32           |
| `{field_id}_clay_pct.tif`       | Clay content             | Float32           |
| `{field_id}_silt_pct.tif`       | Silt content             | Float32           |
| `{field_id}_sand_pct.tif`       | Sand content             | Float32           |
| `{field_id}_cec.tif`            | Cation Exchange Capacity | Float32           |
| `{field_id}_awc.tif`            | Available Water Capacity | Float32           |
| `{field_id}_ph.tif`             | pH                       | Float32           |
| `{field_id}_drainage.tif`       | Drainage class           | Float32 (encoded) |
| `{field_id}_soil_metadata.json` | Metadata & bounds        | JSON              |

### Metadata JSON Structure

```json
{
  "field_id": "WV_AG_001",
  "properties": {
    "om_pct": {"min": 4.0, "max": 5.5, "unit": "percent"},
    "clay_pct": {"min": 31, "max": 35, "unit": "percent"},
    "silt_pct": {"min": 48, "max": 51, "unit": "percent"},
    "sand_pct": {"min": 17, "max": 19, "unit": "percent"},
    "cec": {"min": 17.5, "max": 22.5, "unit": "meq/100g"},
    "awc": {"min": 0.19, "max": 0.20, "unit": "cm/cm"},
    "ph": {"min": 5.5, "max": 6.1, "unit": "pH"},
    "drainage": {"min": 1, "max": 1, "encoding": {"1": "Well drained"}}
  },
  "spatial": {
    "bounds": [minx, miny, maxx, maxy],
    "crs": "EPSG:4326",
    "resolution_m": 5,
    "padding_pct": 10
  },
  "data_source": "USDA NRCS SSURGO"
}
```

### Parameters

- Padding: 10% boundary around input polygon
- Resolution: 5 meters
- Coordinate system: EPSG:4326 (lat/lon)

### Drainage Class Encoding

| Code | Class                        |
| ---- | ---------------------------- |
| 1    | Well drained                 |
| 2    | Moderately well drained      |
| 3    | Somewhat poorly drained      |
| 4    | Poorly drained               |
| 5    | Very poorly drained          |
| 6    | Excessively drained          |
| 7    | Somewhat excessively drained |

## Implementation

### Files

- New: `scripts/generate_soil_maps.py`

### Dependencies

- geopandas
- rasterio
- numpy
- requests
- pandas
- shapely

### Data Source

- USDA NRCS Soil Data Access API: https://sdmdataaccess.sc.egov.usda.gov

## Status

- [x] Create planning doc
- [x] Implement script
- [x] Test with sample data

## Verification

Tested with WV_AG_001:

- 8 property GeoTIFFs generated (Float32, EPSG:4326)
- Metadata JSON with min/max bounds per property
- Data source: USDA NRCS SSURGO
- Padding: 10%
- Resolution: 5m
