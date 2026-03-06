# Agricultural Data Correlation Analysis - Summary Report

## Overview

This analysis explored correlations and comparisons across soil properties, weather patterns, and crop types for 50 agricultural fields in Oregon's Willamette Valley.

---

## Data Summary

| Dataset         | Records                    | Key Variables                                               |
| --------------- | -------------------------- | ----------------------------------------------------------- |
| Soil Properties | 990 (50 fields × ~20 rows) | pH, OM, clay, sand, silt, CEC, drainage                     |
| Weather         | 109,600 daily observations | Temperature, precipitation, humidity, wind, solar radiation |
| Crops           | 50 fields                  | Winter Wheat (46), Other Hay (2), Alfalfa (2)               |

---

## Key Findings

### 1. Soil Property Correlations (Phase 3)

**Strongest correlations identified:**

| Variable Pair   | Correlation | p-value | Interpretation                     |
| --------------- | ----------- | ------- | ---------------------------------- |
| Silt % ↔ AWC    | 0.75        | <0.001  | Higher silt = higher water storage |
| Sand % ↔ Silt % | -0.75       | <0.001  | Inverse texture relationship       |
| Sand % ↔ AWC    | -0.74       | <0.001  | Sandy soils drain faster           |
| Clay % ↔ CEC    | 0.73        | <0.001  | Clay holds more nutrients          |
| Clay % ↔ Sand % | -0.71       | <0.001  | Textural inverse                   |

**Key insight:** Soil texture (clay/sand/silt) is the primary driver of both water-holding capacity (AWC) and nutrient-holding capacity (CEC).

### 2. Cross-Dataset Correlations (Phase 4)

**Soil vs Weather significant relationships:**

| Soil Variable | Weather Variable   | Correlation | p-value |
| ------------- | ------------------ | ----------- | ------- |
| Silt %        | Wind Speed         | 0.61        | <0.001  |
| Sand %        | Wind Speed         | -0.61       | <0.001  |
| pH            | Precipitation      | -0.49       | <0.001  |
| pH            | Winter Temperature | 0.49        | <0.001  |
| AWC           | Precipitation      | 0.46        | <0.001  |

**Soil vs Drainage class:**

- CEC shows strongest relationship (r = -0.68, p < 0.001): Higher CEC = poorer drainage

### 3. Group Comparisons (Phase 5)

**ANOVA results by drainage class:**

| Variable | F-statistic | p-value | Significant? |
| -------- | ----------- | ------- | ------------ |
| CEC      | 20.43       | <0.001  | Yes          |
| Clay %   | 4.69        | 0.014   | Yes          |
| OM %     | 3.97        | 0.026   | Yes          |
| pH       | 1.22        | 0.305   | No           |

**Interpretation:** Drainage class is significantly related to soil fertility (CEC), texture (clay), and organic matter - but not pH.

---

## Visualizations Created

| File                            | Description                                  |
| ------------------------------- | -------------------------------------------- |
| `soil_correlation_heatmap.png`  | Soil properties correlation matrix           |
| `scatter_*.png` (5 files)       | Soil variable scatter plots with trend lines |
| `cross_correlation_heatmap.png` | Full cross-dataset heatmap                   |
| `soil_weather_heatmap.png`      | Soil vs weather correlation                  |
| `boxplot_by_crop.png`           | Soil/weather by crop type                    |
| `boxplot_by_drainage.png`       | Soil by drainage class                       |
| `violin_plots.png`              | Distribution comparisons                     |

---

## Data Quality Notes

- **Missing values:** Minimal in merged dataset (0 missing after aggregation)
- **Outliers:** Some extreme values in OM (up to 75% in one horizon) - likely surface organic deposits
- **Crop distribution:** Highly skewed (92% Winter Wheat) - limits crop comparison power

---

## Recommendations for Further Analysis

1. **Temporal analysis:** Investigate how weather correlations vary seasonally
2. **Spatial analysis:** Map fields to identify geographic soil/climate patterns
3. **Yield correlation:** If yield data available, identify soil/weather predictors
4. **Expanded crop data:** Acquire more diverse crop types for meaningful crop comparisons

---

## Technical Details

- **Analysis date:** 2025
- **Python packages:** pandas, numpy, matplotlib, seaborn, scipy
- **Correlation methods:** Pearson (linear), Spearman (rank)
- **Significance threshold:** α = 0.05
- **Data sources:** USDA SSURGO, NASA POWER, USDA NASS CDL

---

_Generated from: notebooks/eda-data-correlation-plan.md_
