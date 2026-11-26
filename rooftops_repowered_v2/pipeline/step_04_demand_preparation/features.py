import numpy as np
import pandas as pd

from pipeline.common import InputError, require_columns

NUMERIC_FEATURES = ['log_floor_area', 'latitude', 'hour', 'day_of_week', 'month', 'is_weekend',
                    'annual_sin', 'annual_cos', 'air_temperature_c',
                    'heating_degrees', 'cooling_degrees']
CATEGORICAL_FEATURES = ['building_use']
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def make_features(frame):
    require_columns(frame, ['timestamp_local_standard', 'floor_area_m2', 'building_use',
                            'air_temperature_c', 'latitude'], 'Demand feature inputs')
    times = pd.to_datetime(frame['timestamp_local_standard'], errors='raise')
    if times.dt.tz is not None:
        raise InputError('timestamp_local_standard must be naive source-standard wall time, not UTC/civil time.')
    area = pd.to_numeric(frame['floor_area_m2'], errors='raise')
    if not np.isfinite(area).all() or (area <= 0).any():
        raise InputError('floor_area_m2 must be finite and strictly positive.')
    if frame['building_use'].isna().any():
        raise InputError('Every demand input must specify building_use.')
    temperature = pd.to_numeric(frame['air_temperature_c'], errors='raise')
    if np.isinf(temperature).any():
        raise InputError('Temperature must be finite or missing, never infinity.')
    result = pd.DataFrame(index=frame.index)
    result['building_use'] = frame['building_use'].astype(str)
    result['log_floor_area'] = np.log1p(area)
    latitude = pd.to_numeric(frame['latitude'], errors='raise')
    if latitude.isna().any() or not latitude.between(-90, 90).all():
        raise InputError('latitude must be known and in [-90,90].')
    result['latitude'] = latitude
    result['hour'] = times.dt.hour
    result['day_of_week'] = times.dt.day_of_week
    result['month'] = times.dt.month
    result['is_weekend'] = (times.dt.day_of_week >= 5).astype(int)
    phase = 2 * np.pi * (times.dt.day_of_year - 1) / 365.25
    result['annual_sin'], result['annual_cos'] = np.sin(phase), np.cos(phase)
    result['air_temperature_c'] = temperature
    # Engineering proxies, not thermal energy targets or fitted HVAC thresholds.
    result['heating_degrees'] = (18 - temperature).clip(lower=0)
    result['cooling_degrees'] = (temperature - 22).clip(lower=0)
    return result[FEATURES]
