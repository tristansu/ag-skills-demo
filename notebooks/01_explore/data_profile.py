"""
Phase 1: Data Exploration (eda-explore skill)

Load and profile all agricultural datasets to understand structure, 
quality, and distributions.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Output directory
OUTPUT_DIR = Path('notebooks/01_explore/output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PHASE 1: DATA EXPLORATION")
print("=" * 60)

# =============================================================================
# 1. Load all datasets
# =============================================================================
print("\n1. Loading datasets...")

soil_props = pd.read_csv('docs/assignment-03/soil_data/ssurgo_properties.csv')
weather = pd.read_csv('data/assignment-02/weather_oregon_willamette_ag_2020_2025.csv')
crops = pd.read_csv('data/assignment-02/cdl_oregon_willamette_ag_2025.csv')

print(f"   Soil properties: {soil_props.shape[0]} rows × {soil_props.shape[1]} cols")
print(f"   Weather: {weather.shape[0]} rows × {weather.shape[1]} cols")
print(f"   Crops: {crops.shape[0]} rows × {crops.shape[1]} cols")

# =============================================================================
# 2. Soil Properties Analysis
# =============================================================================
print("\n2. Soil Properties Analysis")
print("-" * 40)

soil_cols = soil_props.columns.tolist()
print(f"   Columns: {soil_cols}")

soil_numeric = soil_props.select_dtypes(include=[np.number]).columns.tolist()
soil_categorical = soil_props.select_dtypes(include=['object']).columns.tolist()
print(f"   Numeric columns: {len(soil_numeric)}")
print(f"   Categorical columns: {len(soil_categorical)}")

print("\n   Numeric columns summary:")
print(soil_props[soil_numeric].describe().round(2).to_string())

print("\n   Missing values:")
soil_missing = soil_props.isnull().sum()
print(soil_missing[soil_missing > 0].to_string())

print("\n   Unique field_ids:", soil_props['field_id'].nunique())
print("   Unique mukey:", soil_props['mukey'].nunique())
print("   Unique muname:", soil_props['muname'].nunique())
print("   Unique drainage:", soil_props['drainagecl'].nunique())

# =============================================================================
# 3. Weather Analysis
# =============================================================================
print("\n3. Weather Analysis")
print("-" * 40)

weather_cols = weather.columns.tolist()
print(f"   Columns: {weather_cols}")

weather_numeric = weather.select_dtypes(include=[np.number]).columns.tolist()
print(f"   Numeric columns: {len(weather_numeric)}")

print("\n   Numeric columns summary:")
print(weather[weather_numeric].describe().round(2).to_string())

print("\n   Missing values:")
weather_missing = weather.isnull().sum()
print(weather_missing[weather_missing > 0].to_string())

print(f"\n   Date range: {weather['date'].min()} to {weather['date'].max()}")
print(f"   Unique fields: {weather['field_id'].nunique()}")

# =============================================================================
# 4. Crops Analysis
# =============================================================================
print("\n4. Crops Analysis")
print("-" * 40)

crop_cols = crops.columns.tolist()
print(f"   Columns: {crop_cols}")

print("\n   Crop distribution:")
print(crops['cdl_crop'].value_counts().to_string())

print(f"\n   Unique field_ids: {crops['field_id'].nunique()}")

# =============================================================================
# 5. Save profiles
# =============================================================================
print("\n5. Saving profiles...")

# Soil profile
soil_profile = {
    'n_rows': soil_props.shape[0],
    'n_cols': soil_props.shape[1],
    'numeric_cols': soil_numeric,
    'categorical_cols': soil_categorical,
    'n_unique_fields': soil_props['field_id'].nunique(),
    'n_unique_soils': soil_props['mukey'].nunique(),
}
pd.DataFrame([soil_profile]).to_csv(OUTPUT_DIR / 'soil_profile.csv', index=False)

# Weather profile
weather_profile = {
    'n_rows': weather.shape[0],
    'n_cols': weather.shape[1],
    'numeric_cols': weather_numeric,
    'date_range': f"{weather['date'].min()} to {weather['date'].max()}",
    'n_unique_fields': weather['field_id'].nunique(),
}
pd.DataFrame([weather_profile]).to_csv(OUTPUT_DIR / 'weather_profile.csv', index=False)

# Crop profile
crop_profile = {
    'n_rows': crops.shape[0],
    'n_cols': crops.shape[1],
    'n_unique_fields': crops['field_id'].nunique(),
    'crop_types': crops['cdl_crop'].value_counts().to_dict(),
}
pd.DataFrame([crop_profile]).to_csv(OUTPUT_DIR / 'crop_profile.csv', index=False)

# Descriptive statistics
soil_props[soil_numeric].describe().round(2).to_csv(OUTPUT_DIR / 'soil_descriptive_stats.csv')
weather[weather_numeric].describe().round(2).to_csv(OUTPUT_DIR / 'weather_descriptive_stats.csv')

print(f"   Saved to {OUTPUT_DIR}/")

print("\n" + "=" * 60)
print("PHASE 1 COMPLETE")
print("=" * 60)
