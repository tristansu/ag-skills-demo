"""
Phase 2: Data Preparation & Joining

Create unified analysis dataset from soil, weather, and crop data.
"""

import pandas as pd
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path('notebooks/data')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PHASE 2: DATA PREPARATION & JOINING")
print("=" * 60)

# Load datasets
print("\n1. Loading datasets...")
soil = pd.read_csv('docs/assignment-03/soil_data/ssurgo_properties.csv')
weather = pd.read_csv('data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv')
crops = pd.read_csv('data/assignment-02/cdl_oregon_willamette_ag_2025.csv')

print(f"   Soil: {soil.shape}")
print(f"   Weather: {weather.shape}")
print(f"   Crops: {crops.shape}")

# =============================================================================
# 2. Aggregate soil by field
# =============================================================================
print("\n2. Aggregating soil by field...")

# Key soil numeric columns for analysis
soil_numeric = ['om_r', 'ph1to1h2o_r', 'claytotal_r', 'sandtotal_r', 
                'silttotal_r', 'cec7_r', 'awc_r', 'comppct_r']

# Weighted average by comppct_r for each field
def weighted_avg(group, col):
    weights = group['comppct_r'].fillna(1)
    values = group[col].fillna(0)
    return np.average(values, weights=weights) if weights.sum() > 0 else np.nan

soil_agg = {}
for col in soil_numeric:
    soil_agg[col] = lambda g, c=col: weighted_avg(g, c)

soil_by_field = soil.groupby('field_id').agg({
    'mukey': 'nunique',
    'muname': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else np.nan,
    'drainagecl': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else np.nan,
    'om_r': 'mean',
    'ph1to1h2o_r': 'mean',
    'claytotal_r': 'mean',
    'sandtotal_r': 'mean',
    'silttotal_r': 'mean',
    'cec7_r': 'mean',
    'awc_r': 'mean',
}).reset_index()

soil_by_field.columns = ['field_id', 'n_soils', 'dominant_soil', 'drainage_class',
                         'om_pct', 'ph', 'clay_pct', 'sand_pct', 'silt_pct', 
                         'cec', 'awc']

print(f"   Aggregated soil: {soil_by_field.shape}")
print(soil_by_field.head())

# =============================================================================
# 3. Aggregate weather by field
# =============================================================================
print("\n3. Aggregating weather by field...")

# Convert date to datetime
weather['date'] = pd.to_datetime(weather['date'])
weather['month'] = weather['date'].dt.month
weather['year'] = weather['date'].dt.year

# Define seasons
def get_season(month):
    if month in [3, 4, 5]:
        return 'spring'
    elif month in [6, 7, 8]:
        return 'summer'
    elif month in [9, 10, 11]:
        return 'fall'
    else:
        return 'winter'

weather['season'] = weather['month'].apply(get_season)

# Calculate seasonal and annual averages per field
weather_agg = weather.groupby('field_id').agg({
    'T2M': 'mean',
    'T2M_MAX': 'mean',
    'T2M_MIN': 'mean',
    'PRECTOTCORR': 'sum',  # Annual total
    'ALLSKY_SFC_SW_DWN': 'mean',
    'RH2M': 'mean',
    'WS10M': 'mean',
}).reset_index()

weather_agg.columns = ['field_id', 'temp_avg', 'temp_max_avg', 'temp_min_avg',
                       'precip_annual', 'solar_rad', 'humidity', 'wind_speed']

# Seasonal averages
seasonal = weather.groupby(['field_id', 'season'])['T2M'].mean().unstack()
seasonal.columns = [f'temp_{s}' for s in seasonal.columns]
seasonal = seasonal.reset_index()

# Merge seasonal with annual
weather_by_field = weather_agg.merge(seasonal, on='field_id')

print(f"   Aggregated weather: {weather_by_field.shape}")
print(weather_by_field.head())

# =============================================================================
# 4. Merge all datasets
# =============================================================================
print("\n4. Merging datasets...")

# Start with crops (has field info)
merged = crops.copy()
merged = merged.merge(weather_by_field, on='field_id', how='left')
merged = merged.merge(soil_by_field, on='field_id', how='left')

print(f"   Merged dataset: {merged.shape}")
print(f"   Columns: {merged.columns.tolist()}")

# =============================================================================
# 5. Encode categorical variables
# =============================================================================
print("\n5. Encoding categorical variables...")

# Drainage class encoding
drainage_map = {
    'Very poorly drained': 1,
    'Poorly drained': 2,
    'Somewhat poorly drained': 3,
    'Moderately well drained': 4,
    'Well drained': 5,
    'Somewhat excessively drained': 6,
    'Excessively drained': 7,
}
merged['drainage_encoded'] = merged['drainage_class'].map(drainage_map)

# Crop type encoding
crop_map = {crop: i for i, crop in enumerate(merged['cdl_crop'].unique())}
merged['crop_encoded'] = merged['cdl_crop'].map(crop_map)

print(f"   Drainage encoding: {drainage_map}")
print(f"   Crop encoding: {crop_map}")

# =============================================================================
# 6. Save merged dataset
# =============================================================================
print("\n6. Saving merged dataset...")

merged.to_csv(OUTPUT_DIR / 'merged_analysis.csv', index=False)

print(f"   Saved to {OUTPUT_DIR / 'merged_analysis.csv'}")
print(f"   Final shape: {merged.shape}")
print(f"\n   Missing values:")
missing = merged.isnull().sum()
print(missing[missing > 0].to_string())

print("\n" + "=" * 60)
print("PHASE 2 COMPLETE")
print("=" * 60)
