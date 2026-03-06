"""
Phase 5: Group Comparisons (eda-compare + eda-visualize)

Compare variables across crop types and drainage classes using 
statistical tests and visualizations.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path

OUTPUT_DIR = Path('notebooks/04_group_comparisons/output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PHASE 5: GROUP COMPARISONS")
print("=" * 60)

# Load merged data
print("\n1. Loading data...")
df = pd.read_csv('notebooks/data/merged_analysis.csv')
print(f"   Loaded {df.shape[0]} fields")

# =============================================================================
# 2. Compare by Crop Type
# =============================================================================
print("\n2. Comparing by Crop Type...")
print("-" * 40)

crop_counts = df['cdl_crop'].value_counts()
print(f"   Crop distribution: {crop_counts.to_dict()}")

# Since we have 3 crop types (Winter Wheat: 46, Other Hay: 2, Alfalfa: 2)
# We can do ANOVA for groups with enough data
# Focus on Winter Wheat vs others for meaningful comparison

# Group statistics by crop
crop_stats = df.groupby('cdl_crop').agg({
    'om_pct': ['mean', 'std', 'count'],
    'ph': ['mean', 'std'],
    'clay_pct': ['mean', 'std'],
    'cec': ['mean', 'std'],
    'temp_avg': ['mean', 'std'],
    'precip_annual': ['mean', 'std'],
}).round(2)

print("\n   Crop comparison statistics:")
print(crop_stats.to_string())
crop_stats.to_csv(OUTPUT_DIR / 'crop_comparison_stats.csv')

# =============================================================================
# 3. Compare by Drainage Class
# =============================================================================
print("\n3. Comparing by Drainage Class...")
print("-" * 40)

drainage_counts = df['drainage_class'].value_counts()
print(f"   Drainage distribution: {drainage_counts.to_dict()}")

# Group statistics by drainage
drainage_stats = df.groupby('drainage_class').agg({
    'om_pct': ['mean', 'std', 'count'],
    'ph': ['mean', 'std'],
    'clay_pct': ['mean', 'std'],
    'cec': ['mean', 'std'],
}).round(2)

print("\n   Drainage comparison statistics:")
print(drainage_stats.to_string())
drainage_stats.to_csv(OUTPUT_DIR / 'drainage_comparison_stats.csv')

# =============================================================================
# 4. Statistical Tests - ANOVA for drainage (3+ groups)
# =============================================================================
print("\n4. Statistical Tests (ANOVA for drainage)...")

# Variables to test
test_vars = ['om_pct', 'ph', 'clay_pct', 'cec']

anova_results = []
for var in test_vars:
    # Get non-null drainage groups
    groups = []
    group_names = []
    for drainage in df['drainage_class'].dropna().unique():
        group_data = df[df['drainage_class'] == drainage][var].dropna()
        if len(group_data) > 1:
            groups.append(group_data.values)
            group_names.append(drainage)
    
    if len(groups) >= 2:
        f_stat, p_value = stats.f_oneway(*groups)
        anova_results.append({
            'variable': var,
            'n_groups': len(groups),
            'f_statistic': f_stat,
            'p_value': p_value,
            'significant': 'Yes' if p_value < 0.05 else 'No'
        })

anova_df = pd.DataFrame(anova_results)
print(anova_df.to_string(index=False))
anova_df.to_csv(OUTPUT_DIR / 'drainage_anova_results.csv', index=False)

# =============================================================================
# 5. Create visualizations
# =============================================================================
print("\n5. Creating visualizations...")

# Box plots by crop type
fig, axes = plt.subplots(2, 3, figsize=(15, 10))
vars_to_plot = ['om_pct', 'ph', 'clay_pct', 'cec', 'temp_avg', 'precip_annual']

for idx, var in enumerate(vars_to_plot):
    ax = axes[idx // 3, idx % 3]
    sns.boxplot(data=df, x='cdl_crop', y=var, ax=ax, palette='Set2')
    ax.set_title(f'{var.replace("_", " ").title()} by Crop', fontsize=11, fontweight='bold')
    ax.set_xlabel('')
    ax.set_ylabel(var.replace('_', ' ').title())
    ax.tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'boxplot_by_crop.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"   Saved: boxplot_by_crop.png")

# Box plots by drainage class
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
vars_for_drainage = ['om_pct', 'ph', 'clay_pct', 'cec']

for idx, var in enumerate(vars_for_drainage):
    ax = axes[idx // 2, idx % 2]
    # Only show drainage classes with enough data
    drainage_data = df[df['drainage_class'].notna()]
    sns.boxplot(data=drainage_data, x='drainage_class', y=var, ax=ax, palette='Set3')
    ax.set_title(f'{var.replace("_", " ").title()} by Drainage', fontsize=11, fontweight='bold')
    ax.set_xlabel('')
    ax.set_ylabel(var.replace('_', ' ').title())
    ax.tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'boxplot_by_drainage.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"   Saved: boxplot_by_drainage.png")

# Violin plots
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

sns.violinplot(data=df, x='cdl_crop', y='ph', ax=axes[0], palette='Set2')
axes[0].set_title('pH Distribution by Crop Type', fontsize=12, fontweight='bold')
axes[0].set_xlabel('')
axes[0].tick_params(axis='x', rotation=45)

sns.violinplot(data=df[df['drainage_class'].notna()], x='drainage_class', y='cec', ax=axes[1], palette='Set3')
axes[1].set_title('CEC Distribution by Drainage Class', fontsize=12, fontweight='bold')
axes[1].set_xlabel('')
axes[1].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'violin_plots.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"   Saved: violin_plots.png")

# =============================================================================
# 6. Pairwise comparisons (Winter Wheat vs Other Hay - the main comparison)
# =============================================================================
print("\n6. Pairwise comparisons...")

# Compare Winter Wheat vs Other Hay (only 2 groups with enough data)
wheat = df[df['cdl_crop'] == 'Winter Wheat']
hay = df[df['cdl_crop'] == 'Other Hay']

if len(hay) >= 2:
    pairwise_results = []
    for var in test_vars:
        w_data = wheat[var].dropna()
        h_data = hay[var].dropna()
        if len(w_data) > 0 and len(h_data) > 0:
            t_stat, p_value = stats.ttest_ind(w_data, h_data)
            pairwise_results.append({
                'variable': var,
                'winter_wheat_mean': w_data.mean(),
                'other_hay_mean': h_data.mean(),
                'difference': w_data.mean() - h_data.mean(),
                't_statistic': t_stat,
                'p_value': p_value,
                'significant': 'Yes' if p_value < 0.05 else 'No'
            })
    
    pairwise_df = pd.DataFrame(pairwise_results)
    print(pairwise_df.to_string(index=False))
    pairwise_df.to_csv(OUTPUT_DIR / 'crop_pairwise_comparison.csv', index=False)

print("\n" + "=" * 60)
print("PHASE 5 COMPLETE")
print("=" * 60)
