"""Validate a future user-selected cluster without supplying a default host."""
import numpy as np
import pandas as pd

from pipeline.common import InputError, require_columns


def validate_inventory(inventory, host_id, participant_ids):
    require_columns(inventory, ['building_id', 'is_host', 'building_use', 'latitude',
                                'longitude', 'floor_area_m2', 'source_url'], 'Building inventory')
    if inventory.building_id.isna().any() or inventory.building_id.duplicated().any():
        raise InputError('Inventory building IDs must be nonmissing and unique.')
    if set(inventory.building_id) != set(participant_ids):
        raise InputError('Building inventory must match demand participants exactly.')
    flag = inventory.is_host.astype(str).str.lower()
    if not flag.isin(['true', 'false', '1', '0', 'yes', 'no']).all():
        raise InputError('is_host must use explicit true/false or 1/0 flags.')
    hosts = inventory.loc[flag.isin(['true', '1', 'yes']), 'building_id'].tolist()
    if hosts != [host_id]:
        raise InputError('Exactly one inventory host must match case_study.host_building_id.')
    for col, low, high in [('latitude', -90, 90), ('longitude', -180, 180), ('floor_area_m2', 0, np.inf)]:
        values = pd.to_numeric(inventory[col], errors='raise')
        if not np.isfinite(values).all() or not values.between(low, high).all() or (col == 'floor_area_m2' and values.le(0).any()):
            raise InputError(f'Invalid inventory {col}.')
    if inventory.building_use.isna().any() or inventory.source_url.isna().any():
        raise InputError('Building uses and their source references must be supplied.')
    return inventory
