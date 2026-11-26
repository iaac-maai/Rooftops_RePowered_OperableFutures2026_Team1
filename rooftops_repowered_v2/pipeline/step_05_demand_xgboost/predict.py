import json
import joblib
import numpy as np
import pandas as pd

from pipeline.common import InputError, directory, require_columns, require_file, resolve
from pipeline.step_04_demand_preparation.features import make_features
from pipeline.temporal import as_utc, standard_wall_time


def predict_frame(frame, bundle):
    require_columns(frame, ['timestamp_utc', 'building_id', 'building_use', 'floor_area_m2',
                            'latitude', 'timezone', 'air_temperature_c'], 'Case-study demand input')
    data = frame.copy()
    data['timestamp_utc'] = as_utc(data.timestamp_utc)
    if data.duplicated(['timestamp_utc', 'building_id']).any():
        raise InputError('Duplicate building/hour in demand input.')
    unsupported = set(data.building_use) - set(bundle['supported_uses'])
    if unsupported:
        raise InputError(f'Unsupported building uses {sorted(unsupported)}. Available reference uses: {bundle["supported_uses"]}. Residential needs a separate defensible data/model route.')
    data['timestamp_local_standard'] = pd.NaT
    for zone, group in data.groupby('timezone', dropna=False):
        if pd.isna(zone):
            raise InputError('Every building must have an explicit IANA timezone, e.g. Europe/Madrid.')
        data.loc[group.index, 'timestamp_local_standard'] = standard_wall_time(group.timestamp_utc, zone).to_numpy()
    features = make_features(data)
    if bundle.get('model_name', 'demand_xgboost') == 'demand_xgboost':
        intensity = np.maximum(0, bundle['model'].predict(features))
    else:
        intensity = bundle['model'].predict_intensity(data)
    data['predicted_electricity_kwh'] = intensity * data.floor_area_m2.to_numpy() / 1000
    data['data_origin'] = 'ML_PREDICTION' if bundle.get('model_name', 'demand_xgboost') == 'demand_xgboost' else 'REFERENCE_BASELINE_ESTIMATE'
    data['model_version'] = bundle.get('model_name', 'demand_xgboost')
    data['scenario_id'] = 'reference_model'
    return data[['timestamp_utc', 'building_id', 'predicted_electricity_kwh', 'scenario_id', 'model_version', 'data_origin']]


def run(cfg, input_path, output_path=None, model_name='recommended'):
    models = directory(cfg, 'models')
    bundle = joblib.load(require_file(models / 'demand_xgboost.joblib'))
    manifest = json.loads(require_file(models / 'train_manifest.json').read_text(encoding='utf-8'))
    if model_name == 'recommended':
        model_name = manifest['selected_model_by_validation_mae']
    allowed = ('demand_xgboost', 'demand_baseline_hour_of_week', 'demand_baseline_seasonal')
    if model_name not in allowed:
        raise InputError(f'Unknown demand model {model_name}; choose one of {allowed}.')
    if model_name != 'demand_xgboost':
        bundle['model'] = joblib.load(require_file(models / f'{model_name}.joblib'))
    bundle['model_name'] = model_name
    source = pd.read_csv(require_file(resolve(input_path)))
    prediction = predict_frame(source, bundle)
    target = resolve(output_path) if output_path else directory(cfg, 'datasets') / 'processed/demand_hourly.csv'
    target.parent.mkdir(parents=True, exist_ok=True)
    prediction.to_csv(target, index=False)
    print(f'Wrote {len(prediction):,} modeled demand rows to {target}', flush=True)
    return prediction
