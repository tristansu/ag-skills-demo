# Agricultural Data Correlation Analysis Report

**Report Date:** March 2025  
**Analyst:** AI-assisted analysis using eda-explore, eda-correlate, eda-visualize, and eda-compare skills  
**Dataset:** Oregon Willamette Valley Agricultural Fields (50 fields)

---

## Executive Summary

This report presents a comprehensive correlation analysis of agricultural data spanning soil properties, weather patterns, and crop distributions across 50 fields in Oregon's Willamette Valley. The analysis identified several statistically significant relationships:

- **Soil texture drives key properties**: Clay content strongly predicts cation exchange capacity (CEC, r=0.73), while sand content inversely correlates with available water capacity (AWC, r=-0.74)
- **Climate influences soil chemistry**: Soil pH shows significant correlation with precipitation (r=-0.49) and winter temperature (r=0.49)
- **Drainage class matters**: ANOVA reveals significant differences in CEC (p<0.001), clay (p=0.014), and organic matter (p=0.026) across drainage classes

---

## 1. Introduction

The purpose of this analysis was to explore relationships among multiple agricultural variables to identify patterns that could inform land management decisions. The analysis employed four complementary EDA skills:

- **eda-explore**: Initial data profiling and quality assessment
- **eda-correlate**: Correlation matrix calculation and significance testing
- **eda-visualize**: Heatmap and scatter plot generation
- **eda-compare**: Group-wise statistical comparisons using ANOVA and t-tests

---

## 2. Methodology

### 2.1 Data Processing Pipeline

The analysis followed a multi-phase workflow:

1. **Data Loading**: Three source datasets were loaded and inspected
2. **Aggregation**: Weather data was aggregated from daily to field-level annual and seasonal averages; soil data was aggregated by field with simple means
3. **Join**: All datasets were merged on `field_id` to create a unified analysis dataset
4. **Encoding**: Categorical variables (drainage class, crop type) were numerically encoded for statistical analysis

### 2.2 Statistical Methods

| Method                     | Application                                              |
| -------------------------- | -------------------------------------------------------- |
| **Pearson Correlation**    | Primary correlation coefficient for linear relationships |
| **Spearman Correlation**   | Robustness check using rank-based method                 |
| **ANOVA**                  | Group comparison for 3+ categories (drainage classes)    |
| **T-test**                 | Pairwise comparison (Winter Wheat vs Other Hay)          |
| **Significance Threshold** | α = 0.05 for all tests                                   |

### 2.3 Software Environment

- Python 3.x with pandas, numpy, matplotlib, seaborn, scipy
- Analysis notebooks stored in `notebooks/` directory

---

## 3. Data Sources

| Dataset             | Source File                                                     | Records                    | Key Variables                                                                   |
| ------------------- | --------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------- |
| **Soil Properties** | `docs/assignment-03/soil_data/ssurgo_properties.csv`            | 990 horizons (50 fields)   | pH, organic matter %, clay/sand/silt %, CEC, drainage class                     |
| **Weather**         | `data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv` | 109,600 daily observations | Temperature (avg/max/min), precipitation, solar radiation, humidity, wind speed |
| **Crops**           | `data/assignment-02/cdl_oregon_willamette_ag_2025.csv`          | 50 fields                  | Crop type (Winter Wheat, Other Hay, Alfalfa), dominance %                       |
| **Fields**          | `data/assignment-02/fields_complete.geojson`                    | 50 fields                  | Field boundaries, area, coordinates                                             |

**Temporal Coverage:**

- Weather: January 1, 2020 – December 31, 2025 (6 years)
- Crops: 2025 growing season
- Soil: SSURGO database (static)

---

## 4. Data Processing

### 4.1 Weather Aggregation

Daily weather observations were aggregated to field-level statistics:

- **Annual**: Mean temperature, total precipitation, mean solar radiation, mean humidity, mean wind speed
- **Seasonal**: Mean temperature for spring (Mar-May), summer (Jun-Aug), fall (Sep-Nov), winter (Dec-Feb)

### 4.2 Soil Aggregation

Multiple soil horizons per field were collapsed using simple means:

```python
soil_by_field = soil.groupby('field_id').agg({
    'om_r': 'mean',
    'ph1to1h2o_r': 'mean',
    'claytotal_r': 'mean',
    'sandtotal_r': 'mean',
    'silttotal_r': 'mean',
    'cec7_r': 'mean',
    'awc_r': 'mean',
})
```

### 4.3 Categorical Encoding

| Variable           | Encoding Scheme                                                                                               |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| **Drainage Class** | Very poorly drained=1, Poorly drained=2, Somewhat poorly drained=3, Moderately well drained=4, Well drained=5 |
| **Crop Type**      | Winter Wheat=0, Other Hay=1, Alfalfa=2                                                                        |

### 4.4 Missing Values

The final merged dataset (`merged_analysis.csv`) contains **zero missing values** after aggregation. Some source data columns contained missing values (e.g., 22 missing pH values in soil horizons), but these were handled via dropna during correlation calculations.

---

## 5. Visualizations and Findings

### 5.1 Soil Property Correlations

**Figure 1: Soil Properties Correlation Matrix**
![Soil Correlation Heatmap](../02_soil_correlations/output/soil_correlation_heatmap.png)

_Figure 1: Pearson correlation coefficients for 7 soil properties across 50 fields. Blue indicates positive correlation, red indicates negative correlation. All correlations shown are statistically significant (p < 0.05)._

The correlation matrix reveals several strong relationships among soil variables:

| Variable Pair   | Correlation (r) | p-value | Interpretation                                               |
| --------------- | --------------- | ------- | ------------------------------------------------------------ |
| Silt % ↔ AWC    | 0.75            | <0.001  | Higher silt content strongly predicts water-holding capacity |
| Sand % ↔ Silt % | -0.75           | <0.001  | Expected textural inverse relationship                       |
| Sand % ↔ AWC    | -0.74           | <0.001  | Sandy soils drain freely, low water retention                |
| Clay % ↔ CEC    | 0.73            | <0.001  | Clay minerals provide nutrient exchange sites                |
| Clay % ↔ Sand % | -0.71           | <0.001  | Textural class separation                                    |

**Figure 2: Clay vs CEC (Strongest Soil Correlation)**
![Clay vs CEC Scatter](../02_soil_correlations/output/scatter_clay_pct_vs_cec.png)

_Figure 2: Scatter plot showing the relationship between clay percentage and cation exchange capacity (CEC). The positive trend (r=0.73) indicates that fields with higher clay content have greater nutrient-holding capacity._

**Figure 3: Sand vs AWC**
![Sand vs AWC Scatter](../02_soil_correlations/output/scatter_sand_pct_vs_awc.png)

_Figure 3: Inverse relationship between sand percentage and available water capacity. Higher sand content predicts lower water retention, with implications for irrigation management._

**Figure 4: pH vs Organic Matter**
![pH vs OM Scatter](../02_soil_correlations/output/scatter_clay_pct_vs_om_pct.png)

_Figure 4: Moderate negative correlation (r=-0.43) between soil pH and organic matter percentage._

---

### 5.2 Cross-Dataset Correlations

**Figure 5: Full Cross-Dataset Correlation Matrix**
![Cross Correlation Heatmap](../03_cross_correlations/output/cross_correlation_heatmap.png)

_Figure 5: 18-variable correlation matrix spanning soil properties, weather patterns, and encoded categorical variables. Shows complex interdependencies across domains._

**Figure 6: Soil vs Weather Correlation (Focused)**
![Soil-Weather Heatmap](../03_cross_correlations/output/soil_weather_heatmap.png)

_Figure 6: Focused view of soil properties versus weather variables. Key findings: pH correlates with precipitation and temperature; AWC correlates with precipitation; silt/sand correlate with wind speed._

**Notable Cross-Domain Correlations:**

| Soil Variable | Weather Variable   | Correlation | p-value | Significance                     |
| ------------- | ------------------ | ----------- | ------- | -------------------------------- |
| Silt %        | Wind Speed         | 0.61        | <0.001  | Higher silt in windier locations |
| Sand %        | Wind Speed         | -0.61       | <0.001  | Inverse pattern                  |
| pH            | Precipitation      | -0.49       | <0.001  | Wetter areas have lower pH       |
| pH            | Winter Temperature | 0.49        | <0.001  | Warher winters = higher pH       |
| AWC           | Precipitation      | 0.46        | <0.001  | More rain = higher AWC           |
| pH            | Summer Temperature | -0.47       | <0.001  | Hotter summers = lower pH        |

**Soil vs Drainage Class:**

| Soil Variable | Correlation with Drainage | p-value |
| ------------- | ------------------------- | ------- |
| CEC           | -0.68                     | <0.001  |
| Clay %        | -0.41                     | 0.003   |
| Sand %        | 0.36                      | 0.010   |
| OM %          | 0.36                      | 0.011   |

_Interpretation: Well-drained soils tend to have lower CEC and clay content; poorly drained soils have higher organic matter and clay._

**Figure 7: pH vs Temperature**
![pH vs Temperature](../03_cross_correlations/output/cross_ph_vs_temp_avg.png)

_Figure 7: Positive relationship between soil pH and average temperature. Fields in warmer areas tend to have higher pH values._

**Figure 8: OM vs Precipitation**
![OM vs Precipitation](../03_cross_correlations/output/cross_om_pct_vs_precip_annual.png)

_Figure 8: Organic matter shows moderate positive correlation with annual precipitation (r=0.46). Higher rainfall areas accumulate more organic material._

---

### 5.3 Group Comparisons

**Figure 9: Box Plots by Crop Type**
![Box Plot by Crop](../04_group_comparisons/output/boxplot_by_crop.png)

_Figure 9: Distribution of 6 variables (OM, pH, clay, CEC, temperature, precipitation) across 3 crop types. Note: Winter Wheat dominates (n=46) compared to Other Hay (n=2) and Alfalfa (n=2), limiting statistical power for crop comparisons._

**Crop Distribution:**

- Winter Wheat: 46 fields (92%)
- Other Hay: 2 fields (4%)
- Alfalfa: 2 fields (4%)

**Figure 10: Box Plots by Drainage Class**
![Box Plot by Drainage](../04_group_comparisons/output/boxplot_by_drainage.png)

_Figure 10: Soil property distributions across 3 drainage classes. Clear differences visible in CEC and clay content._

**Drainage Distribution:**

- Poorly drained: 28 fields (56%)
- Well drained: 18 fields (36%)
- Moderately well drained: 4 fields (8%)

**ANOVA Results (Drainage Class):**

| Variable | F-statistic | p-value | Significant? |
| -------- | ----------- | ------- | ------------ |
| CEC      | 20.43       | <0.001  | **Yes**      |
| Clay %   | 4.69        | 0.014   | **Yes**      |
| OM %     | 3.97        | 0.026   | **Yes**      |
| pH       | 1.22        | 0.305   | No           |

_Three of four soil properties show statistically significant differences across drainage classes, confirming that drainage classification captures meaningful soil variation._

**Figure 11: Violin Plots**
![Violin Plots](../04_group_comparisons/output/violin_plots.png)

_Figure 11: Violin plots showing full distribution shapes. Left: pH by crop type (similar distributions despite different sample sizes). Right: CEC by drainage class (distinct distributions confirm ANOVA findings)._

**Pairwise T-Test (Winter Wheat vs Other Hay):**

| Variable | Wheat Mean | Hay Mean | Difference | p-value | Significant? |
| -------- | ---------- | -------- | ---------- | ------- | ------------ |
| OM %     | 2.66       | 1.83     | +0.83      | 0.500   | No           |
| pH       | 6.07       | 6.17     | -0.10      | 0.650   | No           |
| Clay %   | 30.03      | 34.40    | -4.36      | 0.508   | No           |
| CEC      | 21.49      | 25.07    | -3.58      | 0.310   | No           |

_Note: No significant differences found between Winter Wheat and Other Hay fields, likely due to small sample sizes for Other Hay (n=2)._

---

## 6. Output Files

### 6.1 Data Files (CSV)

| File                                | Location                        | Description                                 |
| ----------------------------------- | ------------------------------- | ------------------------------------------- |
| `merged_analysis.csv`               | `notebooks/data/`               | Unified 50-field dataset with all variables |
| `soil_correlation_matrix.csv`       | `02_soil_correlations/output/`  | 7×7 soil property correlations              |
| `soil_correlations_ranked.csv`      | `02_soil_correlations/output/`  | Correlation pairs sorted by absolute value  |
| `soil_correlation_significance.csv` | `02_soil_correlations/output/`  | P-values for top correlations               |
| `cross_correlation_matrix.csv`      | `03_cross_correlations/output/` | 18×18 full correlation matrix               |
| `cross_domain_correlations.csv`     | `03_cross_correlations/output/` | Soil-weather correlation pairs              |
| `soil_drainage_correlations.csv`    | `03_cross_correlations/output/` | Soil vs drainage encoding correlations      |
| `crop_comparison_stats.csv`         | `04_group_comparisons/output/`  | Mean/std by crop type                       |
| `drainage_comparison_stats.csv`     | `04_group_comparisons/output/`  | Mean/std by drainage class                  |
| `drainage_anova_results.csv`        | `04_group_comparisons/output/`  | ANOVA F-tests by drainage                   |
| `crop_pairwise_comparison.csv`      | `04_group_comparisons/output/`  | T-test results                              |
| `soil_profile.csv`                  | `01_explore/output/`            | Soil dataset metadata                       |
| `weather_profile.csv`               | `01_explore/output/`            | Weather dataset metadata                    |
| `crop_profile.csv`                  | `01_explore/output/`            | Crop dataset metadata                       |
| `soil_descriptive_stats.csv`        | `01_explore/output/`            | Soil numeric summaries                      |
| `weather_descriptive_stats.csv`     | `01_explore/output/`            | Weather numeric summaries                   |

### 6.2 Visualizations (PNG)

| File                                | Phase | Description                                |
| ----------------------------------- | ----- | ------------------------------------------ |
| `soil_correlation_heatmap.png`      | 3     | 7×7 soil property correlation matrix       |
| `scatter_clay_pct_vs_cec.png`       | 3     | Clay vs CEC scatter with trend line        |
| `scatter_clay_pct_vs_om_pct.png`    | 3     | Clay vs organic matter scatter             |
| `scatter_sand_pct_vs_clay_pct.png`  | 3     | Sand vs clay (textural inverse)            |
| `scatter_silt_pct_vs_clay_pct.png`  | 3     | Silt vs clay relationship                  |
| `scatter_ph_vs_cec.png`             | 3     | pH vs CEC scatter                          |
| `cross_correlation_heatmap.png`     | 4     | Full 18×18 cross-domain heatmap            |
| `soil_weather_heatmap.png`          | 4     | Soil vs weather focused heatmap            |
| `cross_clay_pct_vs_temp_avg.png`    | 4     | Clay vs average temperature                |
| `cross_om_pct_vs_precip_annual.png` | 4     | OM vs annual precipitation                 |
| `cross_ph_vs_temp_avg.png`          | 4     | pH vs average temperature                  |
| `cross_cec_vs_precip_annual.png`    | 4     | CEC vs annual precipitation                |
| `boxplot_by_crop.png`               | 5     | 6 variables across 3 crop types            |
| `boxplot_by_drainage.png`           | 5     | 4 soil variables across 3 drainage classes |
| `violin_plots.png`                  | 5     | Distribution comparison plots              |

---

## 7. Notable Findings

### 7.1 Soil Physics Drives Chemistry

The strongest correlations in the dataset are all texture-related:

- **Clay-CEC (r=0.73)**: Fields with higher clay content have substantially higher nutrient-holding capacity
- **Sand-AWC (r=-0.74)**: Sandy fields will require more frequent irrigation

**Implication**: Soil texture testing should be a priority for management zone delineation.

### 7.2 Climate-Soil Interactions

Significant correlations between weather and soil properties suggest long-term climate effects on soil development:

- **pH-Precipitation (r=-0.49)**: Higher rainfall leaches basic cations, lowering pH
- **pH-Winter Temp (r=0.49)**: Warmer winters may accelerate decomposition and nutrient cycling

**Implication**: Climate projections should inform soil amendment strategies.

### 7.3 Drainage as a Management Factor

ANOVA confirms that drainage class is a useful proxy for multiple soil properties:

- Well-drained soils: Lower CEC, lower clay, higher pH
- Poorly drained soils: Higher CEC, higher clay, higher OM

**Implication**: Drainage class can be used as a stratification variable for variable-rate applications.

### 7.4 Crop Distribution Limitation

The heavily skewed crop distribution (92% Winter Wheat) prevents meaningful crop-based comparisons. Future analysis should seek more diverse crop data.

---

## 8. Caveats and Limitations

### 8.1 Data Quality Issues

1. **Organic Matter Outliers**: Some horizons show extremely high OM values (up to 75%), likely representing surface organic deposits rather than typical soil horizons. These were retained but may skew correlations.

2. **Sample Size Imbalance**: With only 2 fields each for Other Hay and Alfalfa, crop-based statistical comparisons are underpowered.

3. **Temporal Mismatch**: Weather data spans 2020-2025, while crop data is from 2025 only. Weather patterns may not align perfectly with current crop conditions.

### 8.2 Methodological Notes

1. **Simple Averaging**: Soil properties were averaged across horizons using simple means rather than weighted averages by horizon thickness. This treats all horizons equally regardless of actual contribution to root zone.

2. **Spearman vs Pearson Divergence**: For the Clay-Sand correlation, Pearson shows r=-0.71 while Spearman shows r=-0.29. This suggests the relationship, while linear, may have outliers affecting the Pearson calculation.

3. **Encoding Arbitrariness**: The drainage class encoding (1-7 scale) assumes equal intervals between classes, which may not reflect actual hydrologic differences.

### 8.3 Generalizability

These findings are specific to:

- Geographic region: Oregon Willamette Valley
- Crop types: Primarily Winter Wheat
- Time period: 2020-2025 weather, 2025 crops

Results may not transfer to other regions or cropping systems without validation.

---

## 9. Conclusions

This correlation analysis successfully identified several actionable relationships among soil, weather, and crop variables:

1. **Soil texture is the primary driver** of both water-holding capacity and nutrient-holding capacity
2. **Climate leaves measurable signatures** on soil properties over time
3. **Drainage class serves as a useful proxy** for multiple soil characteristics
4. **Data limitations** (crop imbalance, sample size) constrain certain analyses

### Recommendations for Future Work

1. **Acquire diverse crop data** to enable meaningful crop comparisons
2. **Add yield data** to identify soil/weather predictors of productivity
3. **Consider spatial analysis** to detect geographic clusters
4. **Validate texture-CEC relationship** with laboratory measurements
5. **Develop predictive models** for irrigation and fertilization based on soil characteristics

---

## 10. Reproducibility

To reproduce this analysis:

```bash
# Run phases in order
python notebooks/01_explore/data_profile.py
python notebooks/data_prep.py
python notebooks/02_soil_correlations/soil_correlation_analysis.py
python notebooks/03_cross_correlations/cross_dataset_analysis.py
python notebooks/04_group_comparisons/group_comparison_analysis.py
```

All source data is located in:

- `docs/assignment-03/soil_data/ssurgo_properties.csv`
- `data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv`
- `data/assignment-02/cdl_oregon_willamette_ag_2025.csv`

---

_Report generated: March 2025_  
_Analysis conducted using eda-explore, eda-correlate, eda-visualize, and eda-compare skills_
