import importlib.metadata
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from pipeline.common import InputError, directory, now, require_file, sha256, write_json
from pipeline.step_05_demand_baseline_hour_of_week.model import GroupMeanBaseline
from pipeline.step_05_demand_baseline_seasonal.model import SeasonalBaseline
from pipeline.step_04_demand_preparation.features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, make_features


def build_model(params):
    transform = ColumnTransformer([
        ('use', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL_FEATURES),
        ('numeric', SimpleImputer(strategy='median', add_indicator=True), NUMERIC_FEATURES),
    ])
    estimator = XGBRegressor(n_estimators=params['n_estimators'], max_depth=params['max_depth'],
                            learning_rate=params['learning_rate'], n_jobs=params['n_jobs'],
                            random_state=params['seed'], tree_method='hist',
                            objective=params.get('objective', 'reg:squarederror'), subsample=0.9, colsample_bytree=0.9)
    return Pipeline([('features', transform), ('regressor', estimator)])


def metrics(frame, predictions, model_name, split):
    error = predictions - frame.electricity_kwh.to_numpy()
    mean_load = float(frame.electricity_kwh.mean())
    mae = float(np.abs(error).mean())
    return {'model': model_name, 'split': split, 'rows': len(frame),
            'buildings': int(frame.building_id.nunique()), 'mae_kwh': mae,
            'rmse_kwh': float(np.sqrt(np.square(error).mean())),
            'nmae_mean_load': mae / mean_load if mean_load > 0 else None,
            'mae_wh_per_m2': float((np.abs(error) * 1000 / frame.floor_area_m2.to_numpy()).mean())}


def assert_disjoint(frame):
    groups = {s: set(frame.loc[frame.split.eq(s), 'building_id']) for s in ('train', 'validation', 'test')}
    if any(not ids for ids in groups.values()):
        raise InputError('Train, validation and test building groups must all be nonempty.')
    if groups['train'] & groups['validation'] or groups['train'] & groups['test'] or groups['validation'] & groups['test']:
        raise InputError('Building leakage across training, validation and test splits.')


def run(cfg):
    root, models = directory(cfg, 'datasets'), directory(cfg, 'models')
    out = directory(cfg, 'reports') / 'demand_model'
    out.mkdir(parents=True, exist_ok=True)
    params = cfg['training']
    path = require_file(root / 'processed/train_meter_hourly.csv.gz')
    frame = pd.read_csv(path, parse_dates=['timestamp_local_standard'])
    assert_disjoint(frame)
    training = frame.loc[frame.split.eq('train')]
    if len(training) > params['max_training_rows']:
        training = training.sample(params['max_training_rows'], random_state=params['seed']).sort_index()
    baselines = {
        'demand_baseline_hour_of_week': GroupMeanBaseline().fit(training),
        'demand_baseline_seasonal': SeasonalBaseline().fit(training),
    }
    model = build_model(params)
    print(f'Training XGBoost on {len(training):,} measured rows; no held-out labels used in fit.', flush=True)
    fit_params = {}
    if params.get('area_weighted_loss', False):
        fit_params['regressor__sample_weight'] = training.floor_area_m2.to_numpy() / training.floor_area_m2.median()
    model.fit(make_features(training), training.electricity_wh_m2, **fit_params)
    uses = sorted(training.building_use.unique().tolist())
    bundle = {'model': model, 'supported_uses': uses, 'target': 'electricity_wh_per_m2_per_hour',
              'prediction_origin': 'ML_PREDICTION', 'created_utc': now()}
    joblib.dump(bundle, models / 'demand_xgboost.joblib')
    for name, baseline in baselines.items():
        joblib.dump(baseline, models / f'{name}.joblib')
    all_metrics, detailed, per_building, prediction_frames = [], [], [], []
    for split in ('validation', 'test'):
        holdout = frame.loc[frame.split.eq(split)].copy()
        for name in [*baselines, 'demand_xgboost']:
            intensity = (baselines[name].predict_intensity(holdout) if name in baselines
                         else np.maximum(0, model.predict(make_features(holdout))))
            predictions = intensity * holdout.floor_area_m2.to_numpy() / 1000
            all_metrics.append(metrics(holdout, predictions, name, split))
            scored = holdout.assign(predicted_electricity_kwh=predictions)
            for use, sub in scored.groupby('building_use'):
                detailed.append({**metrics(sub, sub.predicted_electricity_kwh.to_numpy(), name, split), 'building_use': use})
            for year, sub in scored.groupby(scored.timestamp_local_standard.dt.year):
                detailed.append({**metrics(sub, sub.predicted_electricity_kwh.to_numpy(), name, split), 'year': int(year)})
            for building, sub in scored.groupby('building_id'):
                per_building.append({**metrics(sub, sub.predicted_electricity_kwh.to_numpy(), name, split),
                                     'building_id': building, 'building_use': sub.building_use.iloc[0],
                                     'floor_area_m2': float(sub.floor_area_m2.iloc[0])})
            scored['model'] = name
            prediction_frames.append(scored[['timestamp_local_standard', 'building_id', 'building_use',
                                            'split', 'electricity_kwh', 'predicted_electricity_kwh', 'model']])
    metric_table = pd.DataFrame(all_metrics)
    metric_table.to_csv(root / 'results/model_metrics.csv', index=False)
    pd.DataFrame(detailed).to_csv(out / 'metrics_by_use_and_year.csv', index=False)
    pd.DataFrame(per_building).to_csv(out / 'metrics_by_building.csv', index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(root / 'results/reference_holdout_predictions.csv.gz', index=False, compression='gzip')
    validation = metric_table.loc[metric_table.split.eq('validation')].set_index('model')
    best_baseline = validation.loc[list(baselines), 'mae_kwh'].idxmin()
    passes = bool(validation.loc['demand_xgboost', 'mae_kwh'] < validation.loc[best_baseline, 'mae_kwh'])
    selected = 'demand_xgboost' if passes else best_baseline
    schema = {'required_inputs': ['timestamp_utc', 'building_id', 'building_use', 'floor_area_m2', 'latitude', 'timezone', 'air_temperature_c'],
              'model_features': FEATURES, 'supported_uses': uses,
              'target_unit': 'Wh/m2 per hourly interval internally; kWh per hourly interval in exported predictions',
              'time_basis': 'Calendar features use source-compatible local standard time, not civil DST hours.',
              'unavailable_features_excluded': ['building_id', 'site_id', 'meter lags', 'observed occupancy', 'annual electricity labels']}
    write_json(models / 'feature_schema.json', schema)
    write_json(models / 'train_manifest.json', {
        'created_utc': now(), 'config': params, 'prepared_input_sha256': sha256(path),
        'training_rows_used': len(training), 'supported_uses': uses,
        'split_buildings': {s: sorted(frame.loc[frame.split.eq(s), 'building_id'].unique().tolist()) for s in ('train', 'validation', 'test')},
        'selected_model_by_validation_mae': selected, 'xgboost_beats_best_validation_baseline': passes,
        'model_selection': 'Predeclared settings, no test tuning. Validation selects recommendation; test is reported separately.',
        'packages': {p: importlib.metadata.version(p) for p in ('numpy', 'pandas', 'scikit-learn', 'xgboost', 'joblib')},
        'transfer_limitations': 'International non-residential reference data. Held-out buildings may share sites with training. No Barcelona meter accuracy or residential household validation.'})
    write_json(out / 'readiness.json', {'selected_model': selected, 'xgboost_validation_gate_passed': passes,
                                        'case_study_predictions': 'pending local weather and building inventory',
                                        'barcelona_accuracy_validated': False})
    lines = ['# Demand-model benchmark', '',
             f'Validation-selected model: **{selected}**. XGBoost improves the best validation baseline: **{passes}**.', '',
             'MAE and RMSE are hourly kWh; NMAE is MAE divided by mean measured load.', '',
             metric_table.to_csv(index=False),
             '## Limits', '',
             '- This is a reproducible initial experiment, not a tuned or locally validated final model.',
             '- Entire buildings are held out; sites can appear in multiple splits.',
             '- Reference timestamps remain in their source time basis; these are not Barcelona demand series.',
             '- Small retail cohort and uneven building/site coverage limit confidence.',
             '- Manual schedules are not learned occupancy responses. No household residential demand model is trained.',
             '- Missing meter targets are excluded, not imputed. Temperature imputation and encoding fit training rows only.',
             '- The same sampled training rows fit all three models. Validation/test use all retained holdout hours.',
             '- If XGBoost fails to beat the baseline, prefer the baseline for current estimates and revisit the modeling route.']
    (out / 'MODEL_CARD.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(metric_table.to_string(index=False), flush=True)
    return metric_table
