# PR: Topography Map Generation Script

## Summary

Create a production-ready script to generate topography maps (elevation, slope, aspect) from field boundary GeoJSON, outputting float GeoTIFFs and JSON metadata.

## Scope

### Inputs

- GeoJSON file with field boundaries (Polygon or MultiPolygon)
- Must be in WGS84 (EPSG:4326)

### Outputs

Per field, in a single output folder:

| File                                  | Description       | Format  | Unit            |
| ------------------------------------- | ----------------- | ------- | --------------- |
| `{field_id}_elevation.tif`            | Elevation         | Float32 | meters          |
| `{field_id}_slope.tif`                | Slope             | Float32 | degrees (0-90)  |
| `{field_id}_aspect.tif`               | Aspect            | Float32 | degrees (0-360) |
| `{field_id}_topography_metadata.json` | Metadata & bounds | JSON    | -               |

### Metadata JSON Structure

```json
{
  "field_id": "WV_AG_001",
  "properties": {
    "elevation": {"min": 45.2, "max": 67.8, "unit": "meters"},
    "slope": {"min": 0.0, "max": 12.3, "unit": "degrees"},
    "aspect": {"min": 45, "max": 315, "unit": "degrees (0=N, 90=E, 180=S, 270=W)"}
  },
  "spatial": {
    "bounds": [minx, miny, maxx, maxy],
    "crs": "EPSG:4326",
    "resolution_m": 5,
    "padding_pct": 10
  },
  "data_source": "USGS 3DEP"
}
```

### Parameters

- Padding: 10% boundary around input polygon
- Resolution: 5 meters (with fallback to 10m, 30m)
- Coordinate system: EPSG:4326 (lat/lon)

## Implementation

### Files

- New: `scripts/generate_topography_maps.py`

### Dependencies

- geopandas
- rasterio
- numpy
- requests
- shapely

### Data Source

- USGS 3DEP: https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage

## Status

- [x] Create planning doc
- [x] Implement script
- [x] Test with sample data

## Verification

Tested with WV_AG_001:

- 3 property GeoTIFFs generated (Float32, EPSG:4326): elevation, slope, aspect
- Metadata JSON with min/max bounds per property
- Data source: USGS 3DEP
- Padding: 10%
- Resolution: 5m
