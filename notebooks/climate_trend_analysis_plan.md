# Climate Trend Analysis Plan

## Overview

This plan outlines the implementation of three components:

1. **Weather Data Retrieval** - Update script to collect 2000-2025 data with GDD
2. **Data Processing** - Create aggregated monthly summaries for analysis
3. **Trend Analysis Notebook** - Explore temperature and precipitation trends

---

## Current State

| Item          | Current Value                                                           |
| ------------- | ----------------------------------------------------------------------- |
| Fields        | 50 (WV_AG_001 to WV_AG_050)                                             |
| Date Range    | 2020-2025 (6 years)                                                     |
| Total Records | ~109,600                                                                |
| Variables     | T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, ALLSKY_SFC_SW_DWN, RH2M, WS10M, ET0 |
| GDD           | **NOT INCLUDED**                                                        |

---

## Step 1: Create Planning Document

**File:** `/notebooks/climate_trend_analysis_plan.md` (this document)

---

## Step 2: Update get_weather.py

**File:** `scripts/get_weather.py`

### 2.1 Configuration Updates

| Line | Current                                                                         | Change To                                                         |
| ---- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| 35   | `FIELDS_PATH = "data/assignment-02/fields_oregon_willamette_ag_2025.geojson"`   | `FIELDS_PATH = "data/fields_oregon_willamette_ag_2025.geojson"`   |
| 36   | `OUTPUT_PATH = "data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv"` | `OUTPUT_PATH = "data/weather_oregon_willamette_ag_2000_2025.csv"` |
| 42   | `START_DATE = "20200101"`                                                       | `START_DATE = "20000101"`                                         |

### 2.2 Add GDD Calculation Function

**Insert after line 95** (after `calculate_et0` function):

```python
def calculate_gdd(tmax: float, tmin: float, base_temp: float = 10.0, cap_temp: float = 30.0) -> float:
    """
    Calculate Growing Degree Days (GDD).

    Formula: GDD = max(0, min((T_max + T_min)/2, cap) - base)

    Parameters:
        tmax: Maximum daily temperature (°C)
        tmin: Minimum daily temperature (°C)
        base_temp: Base temperature (default 10°C for corn/soybeans)
        cap_temp: Cap temperature (default 30°C)

    Returns:
        GDD in degree-days
    """
    if tmax is None or tmin is None:
        return None

    t_avg = (tmax + tmin) / 2
    gdd = min(t_avg, cap_temp) - base_temp

    return max(0, gdd)
```

### 2.3 Add GDD to API Response Processing

**Around line 138**, inside the loop, after `et0 = calculate_et0(tmean, month)`:

```python
# Calculate GDD
gdd = calculate_gdd(tmax, tmin)

records.append(
    {
        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
        "T2M": tmean,
        "T2M_MAX": tmax,
        "T2M_MIN": tmin,
        "PRECTOTCORR": param_data["PRECTOTCORR"][date_str],
        "ALLSKY_SFC_SW_DWN": param_data["ALLSKY_SFC_SW_DWN"][date_str],
        "RH2M": param_data["RH2M"][date_str],
        "WS10M": param_data["WS10M"][date_str],
        "ET0": et0,
        "GDD": gdd,  # NEW LINE
    }
)
```

### 2.4 Update Column List

**Line 223** (column list definition):

```python
cols = [
    "field_id",
    "lat",
    "lon",
    "date",
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN",
    "RH2M",
    "WS10M",
    "ET0",
    "GDD",  # NEW LINE
]
```

### 2.5 Update Documentation

**Lines 14-16** (output description):

```python
Output:
    data/weather_oregon_willamette_ag_2000_2025.csv
```

**Lines 25-26** (ET0 Reference):

```python
ET0 Reference:
    FAO-56 Penman-Monteith equation (Allen et al., 1998)

GDD Reference:
    GDD = max(0, min((T_max + T_min)/2, 30) - 10)
    Base temp: 10°C (corn/soybeans), Cap: 30°C
```

---

## Step 3: Run Weather Retrieval

**Command:** `python scripts/get_weather.py`

**Expected Output:**

- File: `data/weather_oregon_willamette_ag_2000_2025.csv`
- Records: ~50 fields × 26 years × 365 days ≈ **474,500 rows**
- Runtime: ~25 minutes (with 0.5s rate limiting per field)

---

## Step 4: Create Processing Script

**File:** `scripts/process_weather_for_notebook.py`

### 4.1 Script Purpose

Convert large daily weather CSV (~475K rows) into monthly aggregated summaries (~15.6K rows) for efficient notebook analysis.

### 4.2 Input → Output

- **Input:** `data/weather_oregon_willamette_ag_2000_2025.csv` (~475K rows)
- **Output:** `data/weather_monthly_summary.csv` (~15,600 rows)

### 4.3 Aggregation

- Groups by: field_id, year, month
- Calculates: mean temperatures, total precipitation, total GDD, etc.

### 4.4 Output Columns

| Column             | Description               | Units       |
| ------------------ | ------------------------- | ----------- |
| field_id           | Field identifier          | string      |
| year               | Year                      | integer     |
| month              | Month (1-12)              | integer     |
| season             | Season name               | string      |
| temp_mean_c        | Mean temperature          | °C          |
| temp_max_mean_c    | Mean of daily max temps   | °C          |
| temp_min_mean_c    | Mean of daily min temps   | °C          |
| precip_total_mm    | Total precipitation       | mm          |
| solar_rad_mean_mj  | Mean solar radiation      | MJ/m²/day   |
| humidity_mean_pct  | Mean relative humidity    | %           |
| wind_speed_mean_ms | Mean wind speed           | m/s         |
| et0_total_mm       | Total evapotranspiration  | mm          |
| gdd_total          | Total growing degree days | degree-days |

---

## Step 5: Create Weather Trends Notebook

**File:** `notebooks/05_weather_trends.ipynb`

### 5.1 Notebook Structure

```
notebooks/05_weather_trends.ipynb
├── 1. Setup and Data Loading
│   ├── Import libraries
│   ├── Load monthly summary data
│   └── Display basic info
├── 2. Annual Temperature Trends
│   ├── Plot: Average annual temperature by year
│   ├── Linear regression for trend detection
│   └── Statistical significance test
├── 3. Seasonal Temperature Analysis
│   ├── Compare summer (Jun-Aug) temps across years
│   ├── Compare winter (Dec-Feb) temps across years
│   └── Box plots: seasonal temperature distributions
├── 4. Precipitation Trends
│   ├── Annual precipitation totals by year
│   ├── Seasonal precipitation patterns
│   └── Identify winter rain decline
├── 5. Growing Degree Days (GDD)
│   ├── Annual GDD accumulation trends
│   ├── GDD by season
│   └── Correlation with temperature
├── 6. Summary Statistics
│   ├── Year-over-year changes table
│   ├── Trend significance summary
│   └── Key findings
```

### 5.2 Key Visualizations

| Chart                    | Type              | Purpose                         |
| ------------------------ | ----------------- | ------------------------------- |
| Annual Temperature Trend | Line + regression | Show if temperatures increasing |
| Summer vs Winter Temps   | Grouped bar/box   | Compare seasonal changes        |
| Precipitation Heatmap    | Seasonal × Year   | Visual pattern detection        |
| GDD Annual Trend         | Line chart        | Heat accumulation changes       |

### 5.3 Key Questions to Answer

- Are summers getting hotter?
- Is winter rain decreasing?
- What is the overall temperature trend?
- How is GDD changing over time?

---

## Execution Order Summary

| Step | Action                   | File(s)                                          |
| ---- | ------------------------ | ------------------------------------------------ |
| 1    | Create planning document | `/notebooks/climate_trend_analysis_plan.md`      |
| 2    | Update weather script    | `scripts/get_weather.py`                         |
| 3    | Run weather retrieval    | `python scripts/get_weather.py`                  |
| 4    | Create processing script | `scripts/process_weather_for_notebook.py`        |
| 5    | Run processing script    | `python scripts/process_weather_for_notebook.py` |
| 6    | Create notebook          | `notebooks/05_weather_trends.ipynb`              |

---

## Dependencies

- Python packages: pandas, matplotlib, seaborn, scipy
- API: NASA POWER (no authentication required)
- Input data: Field boundaries GeoJSON

---

## Notes

1. NASA POWER API rate limit: 0.5s delay between requests (already in script)
2. Data volume reduction: 475K → 15.6K rows (96.7% reduction)
3. GDD formula uses base 10°C / cap 30°C (standard for corn/soybeans)
4. Seasons defined as: winter (DJF), spring (MAM), summer (JJA), fall (SON)
