"""
Phase 4: Cross-Dataset Correlations (eda-correlate + eda-visualize)

Analyze correlations across soil, weather, and crop data.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from pathlib import Path

OUTPUT_DIR = Path('notebooks/03_cross_correlations/output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PHASE 4: CROSS-DATASET CORRELATIONS")
print("=" * 60)

# Load merged data
print("\n1. Loading data...")
df = pd.read_csv('notebooks/data/merged_analysis.csv')
print(f"   Loaded {df.shape[0]} fields")

# =============================================================================
# 2. Select all numeric variables for cross-dataset analysis
# =============================================================================
print("\n2. Selecting variables for cross-dataset analysis...")

# Combine soil, weather, and encoded crop variables
analysis_vars = [
    # Soil properties
    'om_pct', 'ph', 'clay_pct', 'sand_pct', 'silt_pct', 'cec', 'awc',
    # Weather - annual
    'temp_avg', 'precip_annual', 'solar_rad', 'humidity', 'wind_speed',
    # Weather - seasonal
    'temp_spring', 'temp_summer', 'temp_fall', 'temp_winter',
    # Encoded
    'drainage_encoded', 'crop_encoded'
]

df_analysis = df[analysis_vars].dropna()
print(f"   Variables: {len(analysis_vars)}")
print(f"   Valid records: {len(df_analysis)}")

# =============================================================================
# 3. Calculate full correlation matrix
# =============================================================================
print("\n3. Calculating cross-dataset correlation matrix...")

corr_matrix = df_analysis.corr()
print("\n   Correlation matrix shape:", corr_matrix.shape)

# Save correlation matrix
corr_matrix.round(4).to_csv(OUTPUT_DIR / 'cross_correlation_matrix.csv')

# =============================================================================
# 4. Find cross-domain correlations (soil vs weather, etc.)
# =============================================================================
print("\n4. Finding cross-domain correlations...")

# Define variable groups
soil_vars = ['om_pct', 'ph', 'clay_pct', 'sand_pct', 'silt_pct', 'cec', 'awc']
weather_vars = ['temp_avg', 'precip_annual', 'solar_rad', 'humidity', 'wind_speed']
seasonal_vars = ['temp_spring', 'temp_summer', 'temp_fall', 'temp_winter']

# Soil vs Weather correlations
cross_corrs = []
for soil_var in soil_vars:
    for weather_var in weather_vars + seasonal_vars:
        valid = df[[soil_var, weather_var]].dropna()
        if len(valid) > 2:
            r, p = pearsonr(valid[soil_var], valid[weather_var])
            cross_corrs.append({
                'soil_var': soil_var,
                'weather_var': weather_var,
                'correlation': r,
                'p_value': p,
                'significant': 'Yes' if p < 0.05 else 'No'
            })

cross_df = pd.DataFrame(cross_corrs)
cross_df_sorted = cross_df.sort_values('correlation', key=abs, ascending=False)

print("\n   Top 15 cross-domain correlations:")
print(cross_df_sorted.head(15).to_string(index=False))
cross_df.to_csv(OUTPUT_DIR / 'cross_domain_correlations.csv', index=False)

# Soil vs drainage
print("\n   Soil vs Drainage class correlations:")
drainage_corrs = []
for var in soil_vars:
    valid = df[[var, 'drainage_encoded']].dropna()
    if len(valid) > 2:
        r, p = pearsonr(valid[var], valid['drainage_encoded'])
        drainage_corrs.append({'soil_var': var, 'correlation': r, 'p_value': p})

drain_df = pd.DataFrame(drainage_corrs).sort_values('correlation', key=abs, ascending=False)
print(drain_df.to_string(index=False))
drain_df.to_csv(OUTPUT_DIR / 'soil_drainage_correlations.csv', index=False)

# =============================================================================
# 5. Create cross-dataset heatmap
# =============================================================================
print("\n5. Creating cross-dataset heatmap...")

plt.figure(figsize=(14, 12))
sns.heatmap(
    corr_matrix,
    annot=False,
    cmap='coolwarm',
    center=0,
    square=True,
    linewidths=0.3,
    cbar_kws={"shrink": 0.8}
)
plt.title('Cross-Dataset Correlation Matrix\n(Soil, Weather, Crop)', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'cross_correlation_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"   Saved: cross_correlation_heatmap.png")

# =============================================================================
# 6. Focused heatmap: Soil vs Weather only
# =============================================================================
print("\n6. Creating focused soil-weather heatmap...")

focus_vars = soil_vars + weather_vars
focus_corr = df[focus_vars].corr()

plt.figure(figsize=(12, 8))
sns.heatmap(
    focus_corr,
    annot=True,
    fmt='.2f',
    cmap='coolwarm',
    center=0,
    square=True,
    linewidths=0.5,
    cbar_kws={"shrink": 0.8}
)
plt.title('Soil Properties vs Weather Patterns', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'soil_weather_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"   Saved: soil_weather_heatmap.png")

# =============================================================================
# 7. Notable scatter plots
# =============================================================================
print("\n7. Creating notable scatter plots...")

notable_pairs = [
    ('clay_pct', 'temp_avg'),
    ('om_pct', 'precip_annual'),
    ('ph', 'temp_avg'),
    ('cec', 'precip_annual'),
]

for var1, var2 in notable_pairs:
    valid = df[[var1, var2]].dropna()
    if len(valid) > 0:
        corr, p_val = pearsonr(valid[var1], valid[var2])
        
        plt.figure(figsize=(8, 6))
        sns.scatterplot(data=valid, x=var1, y=var2, alpha=0.7, s=80)
        
        # Add trend line
        z = np.polyfit(valid[var1], valid[var2], 1)
        p = np.poly1d(z)
        x_line = np.linspace(valid[var1].min(), valid[var1].max(), 100)
        plt.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend')
        
        plt.xlabel(var1.replace('_', ' ').title(), fontsize=12)
        plt.ylabel(var2.replace('_', ' ').title(), fontsize=12)
        plt.title(f'{var1.replace("_", " ").title()} vs {var2.replace("_", " ").title()}\nr = {corr:.3f}, p = {p_val:.4f}', 
                  fontsize=12, fontweight='bold')
        plt.legend()
        plt.tight_layout()
        
        filename = f'cross_{var1}_vs_{var2}.png'
        plt.savefig(OUTPUT_DIR / filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   Saved: {filename}")

print("\n" + "=" * 60)
print("PHASE 4 COMPLETE")
print("=" * 60)
