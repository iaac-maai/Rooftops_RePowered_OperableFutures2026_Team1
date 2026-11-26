import numpy as np
import pandas as pd

from pipeline.common import InputError, require_columns
from pipeline.temporal import as_utc


def apply_schedule(predictions, building_inventory, schedule, scenario_id, timezone='Europe/Madrid'):
    require_columns(predictions, ['timestamp_utc', 'building_id', 'predicted_electricity_kwh', 'data_origin'], 'Predictions')
    require_columns(building_inventory, ['building_id', 'building_use'], 'Building inventory')
    require_columns(schedule, ['building_use', 'day_type', 'hour_local', 'multiplier', 'source_or_assumption'], 'Schedule')
    keys = ['building_use', 'day_type', 'hour_local']
    if building_inventory.building_id.duplicated().any() or schedule.duplicated(keys).any():
        raise InputError('Duplicate inventory IDs or schedule keys.')
    if schedule.source_or_assumption.isna().any():
        raise InputError('Every synthetic schedule needs an explicit assumption/source.')
    if not np.isfinite(schedule.multiplier).all() or schedule.multiplier.lt(0).any():
        raise InputError('Schedule multipliers must be finite and nonnegative.')
    data = predictions.merge(building_inventory[['building_id', 'building_use']], on='building_id',
                             how='left', validate='many_to_one')
    civil = as_utc(data.timestamp_utc).dt.tz_convert(timezone)
    data['day_type'] = np.where(civil.dt.day_of_week < 5, 'weekday', 'weekend')
    data['hour_local'] = civil.dt.hour
    data = data.merge(schedule, on=keys, how='left', validate='many_to_one')
    if data.multiplier.isna().any():
        raise InputError('Schedule must cover every requested building use, day type and local hour.')
    data['predicted_electricity_kwh'] *= data.multiplier
    data['scenario_id'] = scenario_id
    data['scenario_origin'] = 'SYNTHETIC_SCHEDULE'
    return data.drop(columns=['multiplier'])
