# Agricultural Data Correlation Analysis Plan

## Overview

Comprehensive correlation and comparison analysis of agricultural datasets combining soil properties, weather data, and crop information using multiple EDA skills.

## Skills Used

| Skill             | Purpose                                                          |
| ----------------- | ---------------------------------------------------------------- |
| **eda-explore**   | Initial data profiling, quality checks, missing values, outliers |
| **eda-correlate** | Correlation matrix, significance testing, heatmaps               |
| **eda-visualize** | Distribution plots, scatter plots, heatmap visualizations        |
| **eda-compare**   | Group comparisons (by crop type, region), statistical tests      |

## Data Sources

| Dataset             | Location                                                        | Key Variables                                 |
| ------------------- | --------------------------------------------------------------- | --------------------------------------------- |
| **Soil Properties** | `docs/assignment-03/soil_data/ssurgo_properties.csv`            | pH, OM, clay, sand, silt, CEC, drainage       |
| **Weather**         | `data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv` | T2M, precipitation, radiation, humidity, wind |
| **Crops**           | `data/assignment-02/cdl_oregon_willamette_ag_2025.csv`          | Crop code, type, dominance %                  |
| **Fields (merged)** | `data/assignment-02/fields_complete.geojson`                    | All above + area, lat/lon, elevation          |

---

## Phase 1: Data Exploration (eda-explore)

**Goal**: Understand data structure, quality, and distributions

1. **Load all datasets** and inspect structure
2. **Data type validation** - verify numeric vs categorical
3. **Missing value analysis** - quantify gaps per column
4. **Outlier detection** - IQR method on key soil/weather variables
5. **Categorical profiling** - crop types, soil names, drainage classes

**Output**: `notebooks/01_explore/` - summary stats, missing reports, data profiles

---

## Phase 2: Data Preparation & Joining

**Goal**: Create unified analysis dataset

1. **Aggregate weather by field** - compute monthly/seasonal averages per field
2. **Aggregate soil by field** - average soil properties per field (weighted by comppct)
3. **Join all datasets** by `field_id`
4. **Encode categorical variables** - drainage class, crop type as numeric
5. **Handle missing values** - impute or exclude based on analysis

**Output**: `notebooks/data/merged_analysis.csv` - unified dataset

---

## Phase 3: Soil Properties Correlations (eda-correlate + eda-visualize)

**Goal**: Find relationships among soil variables

1. **Correlation matrix** for soil numeric columns (pH, OM, clay, sand, silt, CEC)
2. **Identify strongest correlations** - rank pairs by absolute value
3. **Statistical significance testing** - Pearson + Spearman for top pairs
4. **Visualize** - correlation heatmap with annotations
5. **Scatter plots** for top correlations with trend lines

**Output**: `notebooks/02_soil_correlations/` - matrices, heatmaps, scatter plots

---

## Phase 4: Cross-Dataset Correlations (eda-correlate + eda-visualize)

**Goal**: Find relationships across soil, weather, and crop data

1. **Field-level aggregations**:
   - Seasonal weather (spring, summer, fall, winter averages)
   - Annual precipitation totals
   - Growing degree days

2. **Correlations to analyze**:
   - Soil properties vs weather patterns
   - Soil properties vs crop type distribution
   - Weather vs crop yield patterns

3. **Full correlation matrix** - all numeric field-level variables
4. **Significance testing** - focus on actionable relationships

**Output**: `notebooks/03_cross_correlations/` - cross-dataset matrices, findings

---

## Phase 5: Group Comparisons (eda-compare + eda-visualize)

**Goal**: Compare variables across categorical groups

1. **By Crop Type**:
   - Soil property distributions (box plots, violin plots)
   - Weather pattern differences
   - ANOVA/t-test for significant differences

2. **By Soil Drainage Class**:
   - Compare pH, OM, texture across drainage categories
   - Weather tolerance patterns

3. **Statistical testing**:
   - T-tests for 2-group comparisons
   - ANOVA for 3+ group comparisons
   - Post-hoc pairwise comparisons

**Output**: `notebooks/04_group_comparisons/` - comparison stats, test results, visualizations

---

## Phase 6: Synthesis & Reporting

**Goal**: Document findings and create outputs

1. **Summary report** (`notebooks/eda_correlation_summary.md`):
   - Top correlations with interpretation
   - Statistically significant relationships
   - Group comparison findings
   - Data quality notes

2. **Visualization archive** - all plots with captions

3. **Recommendations** - actionable insights for agricultural analysis

---

## File Structure

```
notebooks/
├── README.md
├── eda-data-correlation-plan.md          # This plan
├── 01_explore/
│   ├── data_profile.py
│   ├── data_quality_report.py
│   └── output/
├── 02_soil_correlations/
│   ├── soil_correlation_analysis.py
│   └── output/
├── 03_cross_correlations/
│   ├── cross_dataset_analysis.py
│   └── output/
├── 04_group_comparisons/
│   ├── group_comparison_analysis.py
│   └── output/
├── data/
│   └── merged_analysis.csv                # Joined dataset
└── eda_correlation_summary.md            # Final report
```

---

## Technical Notes

- **Python dependencies**: pandas, numpy, matplotlib, seaborn, scipy
- **Significance threshold**: α = 0.05
- **Correlation methods**: Pearson (linear), Spearman (rank) for robustness
- **Multiple comparison correction**: Bonferroni if needed
