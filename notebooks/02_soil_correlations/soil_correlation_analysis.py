"""
Phase 3: Soil Properties Correlations (eda-correlate + eda-visualize)

Analyze correlations among soil variables and create visualizations.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from pathlib import Path

OUTPUT_DIR = Path('notebooks/02_soil_correlations/output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PHASE 3: SOIL PROPERTIES CORRELATIONS")
print("=" * 60)

# Load merged data
print("\n1. Loading data...")
df = pd.read_csv('notebooks/data/merged_analysis.csv')
print(f"   Loaded {df.shape[0]} fields")

# =============================================================================
# 2. Select soil variables
# =============================================================================
print("\n2. Selecting soil variables...")

soil_vars = ['om_pct', 'ph', 'clay_pct', 'sand_pct', 'silt_pct', 'cec', 'awc']
df_soil = df[soil_vars].dropna()
print(f"   Variables: {soil_vars}")
print(f"   Valid records: {len(df_soil)}")

# =============================================================================
# 3. Calculate correlation matrix
# =============================================================================
print("\n3. Calculating correlation matrix...")

corr_matrix = df_soil.corr()
print("\n   Pearson Correlation Matrix:")
print(corr_matrix.round(3).to_string())

# Save correlation matrix
corr_matrix.round(4).to_csv(OUTPUT_DIR / 'soil_correlation_matrix.csv')

# =============================================================================
# 4. Find strongest correlations
# =============================================================================
print("\n4. Finding strongest correlations...")

# Get upper triangle (avoid duplicates)
mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
correlations = corr_matrix.where(mask).stack().reset_index()
correlations.columns = ['var1', 'var2', 'correlation']
correlations = correlations.sort_values('correlation', key=abs, ascending=False)

print("\n   Top correlations (by absolute value):")
print(correlations.head(10).to_string(index=False))

# Save
correlations.to_csv(OUTPUT_DIR / 'soil_correlations_ranked.csv', index=False)

# =============================================================================
# 5. Statistical significance testing
# =============================================================================
print("\n5. Testing statistical significance...")

significance_results = []
for i, row in correlations.head(10).iterrows():
    var1, var2, corr = row['var1'], row['var2'], row['correlation']
    valid = df[[var1, var2]].dropna()
    if len(valid) > 2:
        pearson_r, pearson_p = pearsonr(valid[var1], valid[var2])
        spearman_r, spearman_p = spearmanr(valid[var1], valid[var2])
        significance_results.append({
            'var1': var1,
            'var2': var2,
            'pearson_r': pearson_r,
            'pearson_p': pearson_p,
            'spearman_r': spearman_r,
            'spearman_p': spearman_p,
            'significant': 'Yes' if pearson_p < 0.05 else 'No'
        })

sig_df = pd.DataFrame(significance_results)
print(sig_df.to_string(index=False))
sig_df.to_csv(OUTPUT_DIR / 'soil_correlation_significance.csv', index=False)

# =============================================================================
# 6. Create correlation heatmap
# =============================================================================
print("\n6. Creating correlation heatmap...")

plt.figure(figsize=(10, 8))
sns.heatmap(
    corr_matrix,
    annot=True,
    fmt='.2f',
    cmap='coolwarm',
    center=0,
    square=True,
    linewidths=0.5,
    cbar_kws={"shrink": 0.8}
)
plt.title('Soil Properties Correlation Matrix', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'soil_correlation_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"   Saved: soil_correlation_heatmap.png")

# =============================================================================
# 7. Create scatter plots for top correlations
# =============================================================================
print("\n7. Creating scatter plots...")

top_pairs = [
    ('clay_pct', 'cec'),
    ('clay_pct', 'om_pct'),
    ('sand_pct', 'clay_pct'),
    ('silt_pct', 'clay_pct'),
    ('ph', 'cec'),
]

for var1, var2 in top_pairs:
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
        
        filename = f'scatter_{var1}_vs_{var2}.png'
        plt.savefig(OUTPUT_DIR / filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   Saved: {filename}")

print("\n" + "=" * 60)
print("PHASE 3 COMPLETE")
print("=" * 60)
