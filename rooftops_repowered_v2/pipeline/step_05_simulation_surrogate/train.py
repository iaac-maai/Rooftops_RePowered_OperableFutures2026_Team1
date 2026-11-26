"""Fit an office surrogate to EnergyPlus, with whole configurations held out."""
import json
import re
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from pipeline.common import InputError, ROOT, now, require_columns, require_file, sha256, write_json
from pipeline.step_05_demand_baseline_hour_of_week.model import GroupMeanBaseline

PARAMETERS = ['weekday_start_hour', 'weekday_duration_hours', 'equipment_w_per_m2', 'weekend_activity_fraction']
FEATURES = [*PARAMETERS, 'hour', 'day_of_week', 'month', 'activity_fraction', 'equipment_fraction',
            'scheduled_equipment_w_per_m2', 'scheduled_lighting_w_per_m2',
            'hvac_on', 'air_temperature_c', 'temperature_6h_mean_c', 'solar_global_w_m2',
            'active_cooling_degrees', 'active_heating_degrees']


def hour_start_labels(values, year):
    result = []
    for value in values:
        match = re.fullmatch(r'\s*(\d{2})/(\d{2})\s+(\d{2}):00:00\s*', value)
        if not match:
            raise InputError(f'Unexpected EnergyPlus hourly end label: {value!r}')
        month, day, hour = map(int, match.groups())
        if not 1 <= hour <= 24:
            raise InputError('EnergyPlus hourly labels must use end hours 01–24.')
        result.append(pd.Timestamp(year=year, month=month, day=day) + pd.Timedelta(hours=hour - 1))
    return pd.Series(result)


def features(data):
    require_columns(data, ['timestamp_local_standard', 'air_temperature_c', 'solar_global_w_m2',
                           'temperature_6h_mean_c', *PARAMETERS], 'Office surrogate input')
    times = pd.to_datetime(data.timestamp_local_standard)
    if times.dt.tz is not None:
        raise InputError('Surrogate calendar uses explicit local standard time, no civil DST shifts.')
    x = data[PARAMETERS].copy()
    x['hour'], x['day_of_week'], x['month'] = times.dt.hour, times.dt.day_of_week, times.dt.month
    is_open_hour = (x.hour >= x.weekday_start_hour) & (x.hour < x.weekday_start_hour + x.weekday_duration_hours)
    day_level = np.where(x.day_of_week < 5, 1, x.weekend_activity_fraction)
    x['activity_fraction'] = np.where(is_open_hour, day_level, 0)
    x['equipment_fraction'] = 0.15 + 0.85 * x.activity_fraction
    x['scheduled_equipment_w_per_m2'] = x.equipment_w_per_m2 * x.equipment_fraction
    x['scheduled_lighting_w_per_m2'] = 10.76 * (0.05 + 0.95 * x.activity_fraction)
    x['hvac_on'] = (x.activity_fraction > 0).astype(int)
    for col in ['air_temperature_c', 'temperature_6h_mean_c', 'solar_global_w_m2']:
        x[col] = data[col]
    x['active_cooling_degrees'] = (x.air_temperature_c - 22).clip(lower=0) * x.hvac_on
    x['active_heating_degrees'] = (18 - x.air_temperature_c).clip(lower=0) * x.hvac_on
    if not np.isfinite(x.to_numpy(dtype=float)).all():
        raise InputError('Office surrogate inputs must be complete and finite.')
    return x[FEATURES]


def prepare():
    manifest_path = require_file(ROOT / 'reports/simulation_surrogate/simulation_manifest.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    setup = json.loads(require_file(ROOT / 'reports/simulation_surrogate/setup_manifest.json').read_text(encoding='utf-8'))
    records = manifest['results']
    if len(records) < 15 or any(r['status'] != 'completed' for r in records):
        raise InputError('Need at least 15 completed independent configurations; run the full office scenario grid first.')
    # EPW hourly irradiation in Wh/m2 over one hour is numerically average W/m2.
    epw = pd.read_csv(resolve_epw(setup), skiprows=8, header=None)
    if len(epw) != 8760:
        raise InputError('This initial office experiment requires the 8760-row non-leap reference EPW.')
    solar = pd.to_numeric(epw.iloc[:, 13], errors='raise').to_numpy()
    if not np.isfinite(solar).all() or (solar < 0).any() or (solar >= 9999).any():
        raise InputError('EPW solar field has missing/sentinel/invalid values.')
    frames = []
    for record in records:
        folder = ROOT / 'datasets/synthetic/energyplus' / record['simulation_id']
        hourly = pd.read_csv(require_file(folder / 'eplusout.csv'))
        meter_col = 'Electricity:Facility [J](Hourly)'
        temp_col = next((col for col in hourly if 'Site Outdoor Air Drybulb Temperature [C](Hourly)' in col), None)
        require_columns(hourly, ['Date/Time', meter_col], record['simulation_id'])
        if not temp_col or len(hourly) != 8760:
            raise InputError(f'{record["simulation_id"]}: missing weather or complete annual meter output.')
        data = pd.DataFrame({'timestamp_local_standard': hour_start_labels(hourly['Date/Time'], manifest['parameters']['simulation_year']),
                             'electricity_kwh': pd.to_numeric(hourly[meter_col]) / 3_600_000,
                             'air_temperature_c': pd.to_numeric(hourly[temp_col]),
                             'solar_global_w_m2': solar})
        expected = pd.date_range(f"{manifest['parameters']['simulation_year']}-01-01", periods=8760, freq='h')
        if not pd.DatetimeIndex(data.timestamp_local_standard).equals(expected):
            raise InputError('EnergyPlus hour-end labels do not map to the expected complete interval-start calendar.')
        data['temperature_6h_mean_c'] = data.air_temperature_c.rolling(6, min_periods=1).mean()
        for key in PARAMETERS:
            data[key] = record[key]
        data['simulation_id'] = record['simulation_id']
        data['building_id'] = record['simulation_id']
        data['building_use'] = 'Office'
        data['floor_area_m2'] = record['floor_area_m2']
        data['electricity_wh_m2'] = data.electricity_kwh * 1000 / data.floor_area_m2
        data['data_origin'] = 'SIMULATED_PHYSICS'
        if not np.isfinite(data.electricity_kwh).all() or data.electricity_kwh.lt(0).any():
            raise InputError('EnergyPlus electricity target must be finite and nonnegative.')
        frames.append(data)
    full = pd.concat(frames, ignore_index=True)
    rng = np.random.default_rng(manifest['parameters']['seed'])
    ids = rng.permutation(sorted(full.simulation_id.unique()))
    n = max(1, int(len(ids) * 0.2))
    split = {sid: ('test' if i < n else 'validation' if i < 2 * n else 'train') for i, sid in enumerate(ids)}
    full['split'] = full.simulation_id.map(split)
    full.to_csv(ROOT / 'datasets/processed/office_simulation_training.csv.gz', index=False, compression='gzip')
    write_json(ROOT / 'reports/simulation_surrogate/split_manifest.json', {
        'created_utc': now(), 'simulation_manifest_sha256': sha256(manifest_path),
        'splits': {s: sorted(full.loc[full.split.eq(s), 'simulation_id'].unique().tolist()) for s in ('train', 'validation', 'test')},
        'definition': 'Entire parameter combinations held out. Same reference geometry and same weather sequence; this tests interpolation across operation configurations, not unseen climates or real buildings.'})
    return full


def resolve_epw(setup):
    from pipeline.common import resolve
    return require_file(resolve(setup['weather_epw']))


def run():
    data = prepare()
    simulation_manifest = json.loads((ROOT / 'reports/simulation_surrogate/simulation_manifest.json').read_text(encoding='utf-8'))
    protocol = json.loads((ROOT / 'config/simulation.json').read_text(encoding='utf-8'))
    hyperparameters = protocol['surrogate']
    train = data[data.split.eq('train')]
    # A naive pooled hourly mean and a schedule/load-aware linear reference.
    # The latter prevents an easy win from only learning obvious lighting/plug changes.
    baseline = GroupMeanBaseline().fit(train)
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    linear = make_pipeline(StandardScaler(), Ridge(alpha=1))
    linear.fit(features(train), train.electricity_kwh)
    model = XGBRegressor(**hyperparameters, tree_method='hist', objective='reg:squarederror',
                         random_state=simulation_manifest['parameters']['seed'])
    model.fit(features(train), train.electricity_kwh)
    metrics, predictions, by_config = [], [], []
    for split in ('validation', 'test'):
        held = data[data.split.eq(split)].copy()
        estimates = {
            'hour_of_week_baseline': baseline.predict_intensity(held) * held.floor_area_m2.to_numpy() / 1000,
            'schedule_linear_baseline': np.maximum(0, linear.predict(features(held))),
            'office_energyplus_xgboost': np.maximum(0, model.predict(features(held))),
        }
        for name, estimate in estimates.items():
            error = estimate - held.electricity_kwh.to_numpy()
            metrics.append({'model': name, 'split': split, 'rows': len(held), 'configurations': held.simulation_id.nunique(),
                            'mae_kwh': float(np.abs(error).mean()), 'rmse_kwh': float(np.sqrt(np.square(error).mean())),
                            'nmae_mean_simulated_load': float(np.abs(error).mean() / held.electricity_kwh.mean())})
            scored = held[['timestamp_local_standard', 'simulation_id', 'electricity_kwh', 'split']].copy()
            scored['predicted_electricity_kwh'], scored['model'] = estimate, name
            scored['reference_origin'], scored['prediction_origin'] = 'SIMULATED_PHYSICS', 'ML_PREDICTION' if name.endswith('xgboost') else 'REFERENCE_BASELINE_ESTIMATE'
            predictions.append(scored)
            for sid, sub in scored.groupby('simulation_id'):
                by_config.append({'simulation_id': sid, 'model': name, 'split': split,
                                  'mae_kwh': float(np.abs(sub.predicted_electricity_kwh - sub.electricity_kwh).mean())})
    table = pd.DataFrame(metrics)
    out = ROOT / 'reports/simulation_surrogate'
    table.to_csv(out / 'model_metrics.csv', index=False)
    pd.DataFrame(by_config).to_csv(out / 'metrics_by_configuration.csv', index=False)
    pd.concat(predictions, ignore_index=True).to_csv(ROOT / 'datasets/results/office_surrogate_holdout_predictions.csv.gz', index=False, compression='gzip')
    validation = table[table.split.eq('validation')].set_index('model')
    test = table[table.split.eq('test')].set_index('model')
    baseline_names = ['hour_of_week_baseline', 'schedule_linear_baseline']
    validation_best = float(validation.loc[baseline_names, 'mae_kwh'].min())
    test_best = float(test.loc[baseline_names, 'mae_kwh'].min())
    passed = bool(validation.loc['office_energyplus_xgboost', 'mae_kwh'] < validation_best)
    test_passed = bool(test.loc['office_energyplus_xgboost', 'mae_kwh'] < test_best)
    artifact = {'model': model, 'features': FEATURES, 'archetype': simulation_manifest['reference_model'],
                'floor_area_m2': float(data.floor_area_m2.iloc[0]), 'supported_uses': ['Office'],
                'input_domain': {key: sorted(data[key].unique().tolist()) for key in PARAMETERS},
                'prediction_origin': 'ML_PREDICTION', 'training_origin': 'SIMULATED_PHYSICS',
                'schedule_origin': 'SYNTHETIC_SCHEDULE', 'validation_gate_passed': passed}
    joblib.dump(artifact, ROOT / 'pipeline/models/demand_office_energyplus_surrogate.joblib')
    joblib.dump({'hour_of_week': baseline, 'linear': linear}, ROOT / 'pipeline/models/office_simulation_baselines.joblib')
    write_json(ROOT / 'pipeline/models/office_surrogate_manifest.json', {
        'created_utc': now(), 'feature_schema': FEATURES, 'input_domain': artifact['input_domain'],
        'floor_area_m2': artifact['floor_area_m2'], 'validation_gate_passed': passed, 'test_beats_baselines': test_passed,
        'prepared_data_sha256': sha256(ROOT / 'datasets/processed/office_simulation_training.csv.gz'),
        'model_hyperparameters': hyperparameters,
        'limitations': 'Physics surrogate within one reference office geometry, HVAC and envelope; one Barcelona typical weather sequence. Not calibrated or validated against local observed electricity. No residential/retail/education surrogate. Floor-area scaling to an arbitrary real building is not validated.'})
    write_json(out / 'readiness.json', {'validation_gate_passed': passed, 'test_beats_baselines': test_passed,
                                       'real_building_accuracy_validated': False, 'archetype': artifact['archetype'],
                                       'configuration_count': int(data.simulation_id.nunique())})
    (out / 'MODEL_CARD.md').write_text('# Office EnergyPlus surrogate\n\n'
        f'Validation beats both reference baselines: **{passed}**. Test beats both: **{test_passed}**.\n\n'
        + table.to_csv(index=False) + '\nTargets are simulated facility electricity, converted from joules to kWh. '
        'Whole operating configurations are held out, with a fixed reference geometry and weather sequence. '
        'The schedule-aware linear baseline uses the same exogenous features. '
        'This establishes simulator approximation only, not actual Barcelona building accuracy. '
        'See simulation_manifest.json and split_manifest.json for assumptions and partitions.\n', encoding='utf-8')
    print(table.to_string(index=False), flush=True)
    return table


if __name__ == '__main__':
    run()
