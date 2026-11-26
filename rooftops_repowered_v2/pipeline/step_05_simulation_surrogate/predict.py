"""Inference confined to the validated office-reference simulation domain."""
import joblib
import numpy as np
import pandas as pd

from pipeline.common import InputError, ROOT, require_columns, require_file, resolve
from pipeline.step_05_simulation_surrogate.train import PARAMETERS, features
from pipeline.temporal import as_utc, standard_wall_time


def predict_frame(data, bundle):
    required = ['timestamp_utc', 'building_id', 'archetype', 'floor_area_m2', 'timezone',
                'air_temperature_c', 'temperature_6h_mean_c', 'solar_global_w_m2', *PARAMETERS]
    require_columns(data, required, 'Office simulation-surrogate input')
    frame = data.copy()
    if frame.building_id.isna().any() or frame.duplicated(['timestamp_utc', 'building_id']).any():
        raise InputError('Office input needs unique, nonmissing building/hour identifiers.')
    if not frame.archetype.eq(bundle['archetype']).all():
        raise InputError('Office surrogate supports only its documented reference archetype. Simulate the new geometry/HVAC before applying it.')
    if not np.allclose(frame.floor_area_m2, bundle['floor_area_m2'], rtol=1e-6, atol=1e-6):
        raise InputError('Arbitrary area scaling is not validated. Add the selected building geometry to the physics training domain first.')
    if not frame.timezone.eq('Europe/Madrid').all():
        raise InputError('Initial office surrogate covers the Barcelona reference-climate time convention only.')
    for key in PARAMETERS:
        bounds = bundle['input_domain'][key]
        if not frame[key].isin(bounds).all():
            raise InputError(f'{key} is outside the simulated input domain {bounds}; expand simulation coverage before extrapolating.')
    if not bundle.get('validation_gate_passed'):
        raise InputError('Office surrogate has not passed its baseline validation gate.')
    frame['timestamp_utc'] = as_utc(frame.timestamp_utc)
    frame['timestamp_local_standard'] = standard_wall_time(frame.timestamp_utc, 'Europe/Madrid')
    y = np.maximum(0, bundle['model'].predict(features(frame)))
    result = frame[['timestamp_utc', 'building_id']].copy()
    result['predicted_electricity_kwh'] = y
    result['scenario_id'] = 'office_reference_simulation_domain'
    result['model_version'] = 'demand_office_energyplus_surrogate'
    result['data_origin'] = 'ML_PREDICTION'
    result['training_origin'] = 'SIMULATED_PHYSICS'
    result['schedule_origin'] = 'SYNTHETIC_SCHEDULE'
    return result


def run(input_path, output_path, artifact_path=None):
    artifact = resolve(artifact_path) if artifact_path else ROOT / 'pipeline/models/demand_office_energyplus_surrogate.joblib'
    bundle = joblib.load(require_file(artifact))
    data = pd.read_csv(require_file(resolve(input_path)))
    result = predict_frame(data, bundle)
    target = resolve(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(target, index=False)
    print(f'Wrote {len(result):,} office surrogate estimates to {target}')
    return result
