# PR: Solar Radiation Map Generation Script

## Summary

Create a production-ready script to generate solar radiation maps from field boundary GeoJSON with configurable time resolution (monthly, weekly, daily, yearly).

## Scope

### Inputs

- GeoJSON file with field boundaries (Polygon or MultiPolygon)
- Must be in WGS84 (EPSG:4326)

### Time Resolution Options

| Option              | Output Count | Filename Pattern                                         |
| ------------------- | ------------ | -------------------------------------------------------- |
| `monthly` (default) | 12           | `{field_id}_solar_{jan,...,dec}.tif`                     |
| `weekly`            | 52           | `{field_id}_solar_W01.tif` to `{field_id}_solar_W52.tif` |
| `daily`             | 365          | `{field_id}_solar_001.tif` to `{field_id}_solar_365.tif` |
| `yearly`            | 1            | `{field_id}_solar_yearly.tif`                            |

### Outputs

Per field, in a single output folder:

| File                             | Description       | Format  | Unit      |
| -------------------------------- | ----------------- | ------- | --------- |
| `{field_id}_solar_{period}.tif`  | Solar radiation   | Float32 | MJ/m²/day |
| `{field_id}_solar_metadata.json` | Metadata & bounds | JSON    | -         |

### Metadata JSON Structure

```json
{
  "field_id": "WV_AG_001",
  "time_resolution": "monthly",
  "properties": {
    "jan": {"min": 8.2, "max": 12.5, "unit": "MJ/m²/day"},
    "feb": {"min": 10.1, "max": 14.2, "unit": "MJ/m²/day"},
    ...
  },
  "spatial": {
    "bounds": [minx, miny, maxx, maxy],
    "crs": "EPSG:4326",
    "resolution_m": 5,
    "padding_pct": 10
  },
  "data_source": "Calculated from USGS 3DEP slope/aspect",
  "latitude": 44.877
}
```

### Parameters

- Padding: 10% boundary around input polygon
- Resolution: 5 meters
- Coordinate system: EPSG:4326 (lat/lon)

## Implementation

### Files

- New: `scripts/generate_solar_maps.py`

### Dependencies

- geopandas
- rasterio
- numpy
- requests
- shapely

### Calculation Method

- Fetches slope and aspect from USGS 3DEP internally
- Calculates extraterrestrial radiation using solar position algorithms
- Accounts for slope and aspect effects on radiation
- Uses daily averaging for monthly/weekly resolution

## Status

- [x] Create planning doc
- [x] Implement script
- [x] Test with sample data

## Verification

Tested with WV_AG_001 (monthly):

- 12 monthly TIFs generated (Float32, EPSG:4326)
- June: 34.58 - 34.76 MJ/m²/day (peak)
- December: 8.91 - 8.94 MJ/m²/day (minimum)
- Metadata JSON with min/max bounds per month
- Data source: Calculated from USGS 3DEP slope/aspect
- Padding: 10%
- Resolution: 5m
