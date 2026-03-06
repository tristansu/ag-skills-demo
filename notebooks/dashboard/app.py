"""
Agricultural Data Correlation Analysis Dashboard
Panel app version of eda_correlation_analysis.ipynb
"""

import panel as pn
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

pn.extension('matplotlib')

DATA_DIR = '../../data/assignment-02'
SOIL_DIR = '../../docs/assignment-03/soil_data'

def load_data():
    """Load and process all datasets"""
    soil = pd.read_csv(f'{SOIL_DIR}/ssurgo_properties.csv')
    weather = pd.read_csv(f'{DATA_DIR}/weather_oregon_willamette_ag_2020_2025.csv')
    crops = pd.read_csv(f'{DATA_DIR}/cdl_oregon_willamette_ag_2025.csv')
    
    # Aggregate soil by field
    soil_by_field = soil.groupby('field_id').agg({
        'mukey': 'nunique',
        'drainagecl': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else np.nan,
        'om_r': 'mean',
        'ph1to1h2o_r': 'mean',
        'claytotal_r': 'mean',
        'sandtotal_r': 'mean',
        'silttotal_r': 'mean',
        'cec7_r': 'mean',
        'awc_r': 'mean',
    }).reset_index()
    
    soil_by_field.columns = ['field_id', 'n_soils', 'drainage_class', 
                              'om_pct', 'ph', 'clay_pct', 'sand_pct', 
                              'silt_pct', 'cec', 'awc']
    
    # Aggregate weather by field
    weather['date'] = pd.to_datetime(weather['date'])
    weather['month'] = weather['date'].dt.month
    
    def get_season(month):
        if month in [3, 4, 5]: return 'spring'
        elif month in [6, 7, 8]: return 'summer'
        elif month in [9, 10, 11]: return 'fall'
        else: return 'winter'
    
    weather['season'] = weather['month'].apply(get_season)
    
    weather_annual = weather.groupby('field_id').agg({
        'T2M': 'mean', 'PRECTOTCORR': 'sum', 'ALLSKY_SFC_SW_DWN': 'mean',
        'RH2M': 'mean', 'WS10M': 'mean'
    }).reset_index()
    weather_annual.columns = ['field_id', 'temp_avg', 'precip_annual', 
                              'solar_rad', 'humidity', 'wind_speed']
    
    seasonal = weather.groupby(['field_id', 'season'])['T2M'].mean().unstack()
    seasonal.columns = [f'temp_{s}' for s in seasonal.columns]
    seasonal = seasonal.reset_index()
    
    weather_by_field = weather_annual.merge(seasonal, on='field_id')
    
    # Merge all datasets
    df = crops.merge(weather_by_field, on='field_id', how='left')
    df = df.merge(soil_by_field, on='field_id', how='left')
    
    # Encode categorical variables
    drainage_map = {'Very poorly drained': 1, 'Poorly drained': 2, 
                    'Somewhat poorly drained': 3, 'Moderately well drained': 4,
                    'Well drained': 5, 'Somewhat excessively drained': 6, 
                    'Excessively drained': 7}
    df['drainage_encoded'] = df['drainage_class'].map(drainage_map)
    
    crop_map = {crop: i for i, crop in enumerate(df['cdl_crop'].unique())}
    df['crop_encoded'] = df['cdl_crop'].map(crop_map)
    
    return df

# Load data
df = load_data()

# Define variable groups
soil_vars = ['om_pct', 'ph', 'clay_pct', 'sand_pct', 'silt_pct', 'cec', 'awc']
weather_vars = ['temp_avg', 'precip_annual', 'solar_rad', 'humidity', 'wind_speed']

# Styling
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("coolwarm")

# Title
title = pn.Column(
    pn.pane.Markdown("# Agricultural Data Correlation Analysis"),
    pn.pane.Markdown("**Dataset:** Oregon Willamette Valley Agricultural Fields (50 fields)"),
    sizing_mode='stretch_width'
)

# Section 1: Soil Correlation Matrix
def plot_soil_heatmap():
    corr_matrix = df[soil_vars].corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm', 
                center=0, square=True, linewidths=0.5, ax=ax)
    ax.set_title('Soil Properties Correlation Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    return fig

soil_heatmap = pn.pane.Matplotlib(plot_soil_heatmap(), sizing_mode='scale_width', height=500)

# Section 2: Interactive Scatter Plot - Soil vs Soil
var1_selector = pn.widgets.Select(name='Variable 1', options=soil_vars, value='clay_pct')
var2_selector = pn.widgets.Select(name='Variable 2', options=soil_vars, value='cec')

@pn.cache
def plot_scatter_soil(var1, var2):
    if var1 == var2:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(df[var1], df[var2], alpha=0.7, s=80)
        ax.set_xlabel(var1.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(var2.replace('_', ' ').title(), fontsize=12)
        ax.set_title(f'{var1} vs {var2}\nr = 1.000 (self-correlation)', fontsize=12, fontweight='bold')
        plt.tight_layout()
        return fig
    
    valid = df[[var1, var2]].dropna()
    r, p = stats.pearsonr(valid[var1], valid[var2])
    
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.scatterplot(data=valid, x=var1, y=var2, alpha=0.7, s=80, ax=ax)
    
    z = np.polyfit(valid[var1], valid[var2], 1)
    p_line = np.poly1d(z)
    x_line = np.linspace(valid[var1].min(), valid[var1].max(), 100)
    ax.plot(x_line, p_line(x_line), "r--", alpha=0.8, label='Trend')
    
    ax.set_xlabel(var1.replace('_', ' ').title(), fontsize=12)
    ax.set_ylabel(var2.replace('_', ' ').title(), fontsize=12)
    ax.set_title(f'{var1} vs {var2}\nr = {r:.3f}, p = {p:.4f}', fontsize=12, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    return fig

scatter_soil = pn.bind(plot_scatter_soil, var1=var1_selector, var2=var2_selector)
scatter_soil_pane = pn.pane.Matplotlib(scatter_soil, sizing_mode='scale_width', height=450)

scatter_soil_section = pn.Column(
    pn.pane.Markdown("### Interactive: Soil Property Correlations"),
    pn.Row(var1_selector, var2_selector),
    scatter_soil_pane,
    pn.pane.Markdown("*Select two soil properties to explore their correlation*"),
    sizing_mode='stretch_width'
)

# Section 3: Cross-Dataset Correlation (Soil vs Weather)
def plot_cross_heatmap():
    focus_vars = soil_vars + weather_vars
    focus_corr = df[focus_vars].corr()
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(focus_corr, annot=False, cmap='coolwarm', center=0, 
                square=True, linewidths=0.3, ax=ax)
    ax.set_title('Soil vs Weather Correlation Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    return fig

cross_heatmap = pn.pane.Matplotlib(plot_cross_heatmap(), sizing_mode='scale_width', height=550)

cross_section = pn.Column(
    pn.pane.Markdown("### Cross-Dataset Correlations (Soil vs Weather)"),
    cross_heatmap,
    pn.pane.Markdown("*Key finding: pH-Precipitation (r=-0.49), Silt-Wind (r=0.61) show significant cross-domain correlations*"),
    sizing_mode='stretch_width'
)

# Section 4: Interactive Scatter - Soil vs Weather
var_soil_selector = pn.widgets.Select(name='Soil Variable', options=soil_vars, value='ph')
var_weather_selector = pn.widgets.Select(name='Weather Variable', options=weather_vars, value='precip_annual')

@pn.cache
def plot_scatter_cross(soil_var, weather_var):
    valid = df[[soil_var, weather_var]].dropna()
    r, p = stats.pearsonr(valid[soil_var], valid[weather_var])
    
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.scatterplot(data=valid, x=soil_var, y=weather_var, alpha=0.7, s=80, ax=ax)
    
    z = np.polyfit(valid[soil_var], valid[weather_var], 1)
    p_line = np.poly1d(z)
    x_line = np.linspace(valid[soil_var].min(), valid[soil_var].max(), 100)
    ax.plot(x_line, p_line(x_line), "r--", alpha=0.8, label='Trend')
    
    ax.set_xlabel(soil_var.replace('_', ' ').title(), fontsize=12)
    ax.set_ylabel(weather_var.replace('_', ' ').title(), fontsize=12)
    ax.set_title(f'{soil_var} vs {weather_var}\nr = {r:.3f}, p = {p:.4f}', fontsize=12, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    return fig

scatter_cross = pn.bind(plot_scatter_cross, soil_var=var_soil_selector, weather_var=var_weather_selector)
scatter_cross_pane = pn.pane.Matplotlib(scatter_cross, sizing_mode='scale_width', height=450)

scatter_cross_section = pn.Column(
    pn.pane.Markdown("### Interactive: Soil vs Weather Correlations"),
    pn.Row(var_soil_selector, var_weather_selector),
    scatter_cross_pane,
    pn.pane.Markdown("*Select a soil and weather variable to explore cross-domain relationships*"),
    sizing_mode='stretch_width'
)

# Section 5: Group Comparisons by Drainage
drainage_var_selector = pn.widgets.Select(name='Variable', options=soil_vars, value='cec')

def plot_drainage_box():
    drainage_data = df[df['drainage_class'].notna()]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    vars_for_drainage = ['om_pct', 'ph', 'clay_pct', 'cec']
    
    for idx, var in enumerate(vars_for_drainage):
        ax = axes[idx // 2, idx % 2]
        sns.boxplot(data=drainage_data, x='drainage_class', y=var, ax=ax, palette='Set3')
        ax.set_title(f'{var.replace("_", " ").title()} by Drainage', fontsize=11, fontweight='bold')
        ax.set_xlabel('')
        ax.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    return fig

drainage_box = pn.pane.Matplotlib(plot_drainage_box(), sizing_mode='scale_width', height=500)

@pn.cache
def plot_drainage_violin(var):
    drainage_data = df[df['drainage_class'].notna()]
    
    # Run ANOVA
    groups = []
    for drainage in drainage_data['drainage_class'].dropna().unique():
        group_data = drainage_data[drainage_data['drainage_class'] == drainage][var].dropna()
        if len(group_data) > 1:
            groups.append(group_data.values)
    
    if len(groups) >= 2:
        f_stat, p_value = stats.f_oneway(*groups)
        sig_text = f"ANOVA: F={f_stat:.3f}, p={p_value:.4f} {'✓ Significant' if p_value < 0.05 else '✗ Not significant'}"
    else:
        sig_text = "Insufficient groups for ANOVA"
    
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.violinplot(data=drainage_data, x='drainage_class', y=var, palette='Set3', ax=ax)
    ax.set_title(f'Distribution of {var} by Drainage Class\n{sig_text}', fontsize=12, fontweight='bold')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45)
    plt.tight_layout()
    return fig

drainage_violin = pn.bind(plot_drainage_violin, var=drainage_var_selector)
drainage_violin_pane = pn.pane.Matplotlib(drainage_violin, sizing_mode='scale_width', height=400)

drainage_section = pn.Column(
    pn.pane.Markdown("### Group Comparisons by Drainage Class"),
    drainage_box,
    pn.Row(drainage_var_selector, width=300),
    drainage_violin_pane,
    pn.pane.Markdown("*ANOVA shows significant differences in CEC, Clay, and OM by drainage class (p<0.05)*"),
    sizing_mode='stretch_width'
)

# Section 6: Summary Statistics
def get_summary():
    soil_corr = df[soil_vars].corr()
    top_corrs = []
    for i in range(len(soil_vars)):
        for j in range(i+1, len(soil_vars)):
            r = soil_corr.iloc[i, j]
            top_corrs.append((soil_vars[i], soil_vars[j], r, abs(r)))
    top_corrs.sort(key=lambda x: x[3], reverse=True)
    
    summary = "### Key Findings\n\n"
    summary += "**Soil Physics Drives Chemistry:**\n"
    for v1, v2, r, _ in top_corrs[:3]:
        summary += f"- {v1} ↔ {v2}: r={r:.2f}\n"
    
    summary += "\n**Significant Cross-Domain Correlations:**\n"
    cross_corr = df[soil_vars + weather_vars].corr()
    cross_pairs = []
    for sv in soil_vars:
        for wv in weather_vars:
            r = cross_corr.loc[sv, wv]
            if abs(r) > 0.4:
                cross_pairs.append((sv, wv, r, abs(r)))
    cross_pairs.sort(key=lambda x: x[3], reverse=True)
    for sv, wv, r, _ in cross_pairs[:3]:
        summary += f"- {sv} ↔ {wv}: r={r:.2f}\n"
    
    return summary

summary_section = pn.pane.Markdown(get_summary())

# Assemble dashboard
dashboard = pn.Column(
    title,
    pn.layout.Divider(),
    pn.pane.Markdown("## 1. Soil Property Correlations"),
    soil_heatmap,
    scatter_soil_section,
    pn.layout.Divider(),
    pn.pane.Markdown("## 2. Cross-Dataset Correlations"),
    cross_section,
    scatter_cross_section,
    pn.layout.Divider(),
    pn.pane.Markdown("## 3. Group Comparisons"),
    drainage_section,
    pn.layout.Divider(),
    summary_section,
    sizing_mode='stretch_width',
    max_width=1200
)

dashboard.servable()
