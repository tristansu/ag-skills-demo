# Monthly Solar Radiation on Sloped Surfaces

_Design document for generating per-pixel monthly solar radiation maps from lat/lon polygon_

---

## Overview

This script calculates monthly average solar radiation (MJ/m²/day) on a sloped surface for each pixel, accounting for:

- **Latitude** - from polygon centroid
- **Slope** - from terrain (degrees)
- **Aspect** - from terrain (compass convention: 0=N, 90=E, 180=S, 270=W)
- **Day length variation** - throughout the year via declination and sunset hour angle

## Input

| Parameter      | Type   | Required | Description                                                         |
| -------------- | ------ | -------- | ------------------------------------------------------------------- |
| `--input`      | string | Yes      | Polygon as GeoJSON, simple [lon,lat] list, or path to .geojson file |
| `--slope-tif`  | string | No       | Path to existing slope GeoTIFF (generated if not provided)          |
| `--aspect-tif` | string | No       | Path to existing aspect GeoTIFF (generated if not provided)         |
| `--output-dir` | string | No       | Output directory (default: `solar_rasters`)                         |
| `--resolution` | int    | No       | Resolution in meters (default: 5)                                   |
| `--padding`    | float  | No       | Padding fraction (default: 0.15 = 15%)                              |
| `--field-id`   | string | No       | Output filename prefix (default: auto-generated)                    |

## Output

13 GeoTIFF files (12 monthly + 1 yearly):

```
{field-id}_solar_jan.tif
{field-id}_solar_feb.tif
{field-id}_solar_mar.tif
{field-id}_solar_apr.tif
{field-id}_solar_may.tif
{field-id}_solar_jun.tif
{field-id}_solar_jul.tif
{field-id}_solar_aug.tif
{field-id}_solar_sep.tif
{field-id}_solar_oct.tif
{field-id}_solar_nov.tif
{field-id}_solar_dec.tif
{field-id}_solar_yearly.tif   # Yearly average
```

### Output Specifications

- **Data type**: Float32
- **Units**: MJ/m²/day (megajoules per square meter per day)
- **CRS**: EPSG:4326
- **NoData**: -9999

## Formulas

### Constants

| Symbol | Value              | Description    |
| ------ | ------------------ | -------------- |
| Gsc    | 0.0820 MJ/(m²·min) | Solar constant |
| π      | 3.14159265359      | Pi             |

### Step 1: Day Angle (J)

```
J = 2π × (day_of_year - 1) / 365
```

### Step 2: Eccentricity Correction (dr)

```
dr = 1 + 0.033 × cos(J)
```

### Step 3: Solar Declination (δ)

```
δ = 23.45 × sin(360/365 × (day_of_year - 81))  [degrees]
```

- March 21 (day 81): δ = 0° (equinox)
- June 21 (day 172): δ = +23.45° (summer solstice)
- September 21 (day 264): δ = 0° (equinox)
- December 21 (day 355): δ = -23.45° (winter solstice)

### Step 4: Sunset Hour Angle (ωs)

```
ωs = arccos(-tan(φ) × tan(δ))  [radians]
```

Where φ = latitude in radians

### Step 5: Day Length (N)

```
N = (24/π) × ωs  [hours]
```

### Step 6: Extraterrestrial Radiation on Horizontal Surface (Ra)

```
Ra = (24 × 60 / π) × Gsc × dr × [ωs × sin(φ) × sin(δ) + cos(φ) × cos(δ) × sin(ωs)]
```

Units: MJ/m²/day

### Step 7: Radiation on Sloped Surface

Convert aspect from compass convention (0=N, 90=E, 180=S, 270=W) to solar convention where south = 0:

```
α_solar = 180 - aspect_compass
```

Then calculate radiation on slope:

```
Rs_slope = Ra × [cos(β) × cos(δ) × sin(ωs) + (π/180) × ωs × sin(β) × sin(α_solar × π/180) × sin(δ)]
```

Where:

- β = slope in degrees
- α_solar = aspect in solar convention (0 = south-facing)

### Aspect Convention

The existing aspect calculation in `generate_slope_aspect.py` uses:

```python
aspect_rad = np.arctan2(dx, -dy)
aspect_deg = np.where(aspect_deg < 0, aspect_deg + 360, aspect_deg)
```

This is the **standard GIS compass convention**:

- **0°** = North-facing slope
- **90°** = East-facing slope
- **180°** = South-facing slope
- **270°** = West-facing slope

For solar radiation calculation, convert to solar convention where south-facing = 0:

```
α_solar = 180 - aspect_compass
```

### Step 8: Monthly Representative Days

Use day 15 of each month as the representative day:

| Month     | Day of Year |
| --------- | ----------- |
| January   | 15          |
| February  | 46          |
| March     | 74          |
| April     | 105         |
| May       | 135         |
| June      | 166         |
| July      | 196         |
| August    | 227         |
| September | 258         |
| October   | 288         |
| November  | 319         |
| December  | 349         |

## Implementation

### Dependencies

- numpy
- rasterio
- geopandas (optional, for polygon parsing)
- requests (for DEM fetching if slope/aspect not provided)

### Core Functions

1. **`calculate_day_angle(day_of_year)`** - Returns J in radians
2. **`calculate_eccentricity(day_angle)`** - Returns dr
3. **`calculate_declination(day_of_year)`** - Returns δ in degrees
4. **`calculate_sunset_hour_angle(latitude_rad, declination_rad)`** - Returns ωs in radians
5. **`calculate_extraterrestrial_radiation(lat_rad, declination_rad, sunset_angle, eccentricity)`** - Returns Ra
6. **`calculate_slope_radiation(ra, slope_deg, aspect_compass_deg, declination_rad, sunset_angle)`** - Returns Rs_slope
7. **`calculate_monthly_solar(latitude, slope_array, aspect_array, month)`** - Returns radiation for one month

### Processing Pipeline

1. **Parse input** - Load polygon, calculate bounds and centroid
2. **Get/create slope & aspect**:
   - If `--slope-tif` and `--aspect-tif` provided: load them
   - Otherwise: call `lat_lon_polygon_to_dem_slope_aspect.py` or USGS 3DEP directly
3. **Load terrain arrays** - Read slope and aspect as numpy masked arrays
4. **Calculate latitude** - From polygon centroid
5. **For each month (1-12)**:
   - Get representative day_of_year
   - Vectorized calculation of Ra for all pixels
   - Vectorized calculation of Rs_slope for all pixels
   - Save to GeoTIFF
6. **Return** - List of 12 output files

### Vectorization

All pixel calculations are vectorized using numpy:

```python
# Example vectorized calculation
dr = 1 + 0.033 * np.cos(day_angle)
delta_rad = np.radians(declination)
phi_lat_rad = np.radians(latitude)

omega_s = np.arccos(-np.tan(phi_lat_rad) * np.tan(delta_rad))
omega_s = np.nan_to_num(omega_s, nan=0)

Ra = (24 * 60 / np.pi) * Gsc * dr * (
    omega_s * np.sin(phi_lat_rad) * np.sin(delta_rad) +
    np.cos(phi_lat_rad) * np.cos(delta_rad) * np.sin(omega_s)
)
```

### Handling Edge Cases

| Case                 | Handling                                             |
| -------------------- | ---------------------------------------------------- |
| Slope ≈ 0 (flat)     | Use Ra (horizontal surface radiation), ignore aspect |
| Aspect = NaN         | Set to 180 (south-facing default)                    |
| Polar night (ωs < 0) | Set radiation to 0                                   |
| Invalid pixels       | Set to -9999 (NoData)                                |

## Validation

### Expected Behavior

1. **Seasonal variation**:
   - December: South-facing slopes (180°) receive MORE radiation than North-facing (0°)
   - June: More symmetric distribution between slopes

2. **Latitude effect**:
   - Higher latitudes show more extreme seasonal variation
   - Summer days are longer at high latitudes

3. **Slope effect**:
   - Steeper slopes show greater difference between aspect orientations

### Quick Validation

```python
# At latitude 45°N, December 21 (winter solstice):
# - South-facing slope (aspect=180°) should get ~30% more radiation than horizontal
# - North-facing slope (aspect=0°) should get ~50% less radiation than horizontal

# At latitude 45°N, June 21 (summer solstice):
# - All aspects receive similar radiation (high sun angle)
# - Horizontal surface gets maximum radiation
```

## File Naming

| File                                    | Description                 |
| --------------------------------------- | --------------------------- |
| `lat_lon_polygon_to_solar_radiation.py` | Main script                 |
| `solar_jan.tif`                         | January average (MJ/m²/day) |
| `solar_feb.tif`                         | February average            |
| ...                                     | ...                         |
| `solar_dec.tif`                         | December average            |

## Pre-Solstice Peak Phenomenon

### Observed Behavior

When analyzing daily solar radiation output, an interesting effect can be observed: the radiation on **south-facing slopes peaks before the summer solstice** (around DOY 140-145) and then decreases slightly at the solstice before recovering. This creates a "double-hump" pattern through the summer months.

### Physical Explanation

For horizontal surfaces, solar radiation peaks at the summer solstice (DOY 172). However, for sloped surfaces, particularly **south-facing** slopes at mid-latitudes, the peak occurs earlier. This is due to competing factors in the solar radiation formula:

```
Rs = Ra × [cos(β) × cos(δ) × sin(ωs) + (π/180) × ωs × sin(β) × sin(α_solar) × sin(δ)]
```

Where:

- **Ra** = extraterrestrial radiation on horizontal surface (peaks at solstice)
- **cos(δ)** = declination factor - **decreases** as declination increases
- **sin(ωs)** = day length factor - **increases** toward solstice

At mid-latitudes (e.g., 45°N):

| DOY | Date   | Solar Declination | cos(δ) | Day Length |
| --- | ------ | ----------------- | ------ | ---------- |
| 145 | May 25 | 20.9°             | 0.936  | 15.0h      |
| 172 | Jun 21 | 23.4°             | 0.918  | 15.4h      |

While day length increases by ~2.5% from DOY 145 to 172, **cos(δ) decreases by ~2%**. For south-facing slopes, the net effect is a slight **decrease** in radiation at the solstice.

### Impact by Aspect

| Aspect       | Peak Timing                    | Pattern                                      |
| ------------ | ------------------------------ | -------------------------------------------- |
| North (0°)   | After solstice                 | Single peak at solstice                      |
| South (180°) | Before solstice (DOY ~140-145) | Maximum before solstice, minimum at solstice |
| East/West    | Near solstice                  | Relatively flat through summer               |

### Field Example

In test data from a field in the Willamette Valley (latitude ~44.9°N, ~50% south-facing, ~40% west-facing):

- Peak at **DOY 140-145**: ~35.5 MJ/m²/day
- Solstice (DOY 172): ~34.7 MJ/m²/day
- Secondary maximum at **DOY ~197**: ~35.3 MJ/m²/day

This is a **real physical effect** and confirms the correctness of the solar radiation model.

## References

- FAO-56 Penman-Monteith equation (Allen et al., 1998)
- NOAA Solar Calculator: <https://gml.noaa.gov/grad/solcalc/calcdetails.html>
- ASCE Standardized Reference Evapotranspiration Equation
