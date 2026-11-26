import json
import numpy as np
import pandas as pd

from pipeline.common import InputError, directory, now, require_columns, require_file, sha256, write_json


def split_buildings(buildings, seed, validation_fraction, test_fraction, excluded_test_ids=()):
    if min(validation_fraction, test_fraction) <= 0 or validation_fraction + test_fraction >= 1:
        raise InputError('Validation and test fractions must be positive and sum to less than 1.')
    result = buildings.copy()
    result['split'] = 'train'
    rng = np.random.default_rng(seed)
    for use, group in result.groupby('building_use', sort=True):
        ids = rng.permutation(sorted(group.index))
        if len(ids) < 5:
            raise InputError(f'{use}: need at least five eligible buildings for separate train/validation/test groups.')
        nv, nt = max(1, int(len(ids) * validation_fraction)), max(1, int(len(ids) * test_fraction))
        test_pool = [i for i in ids if result.loc[i, 'building_id'] not in set(excluded_test_ids)]
        test_ids = test_pool[:nt]
        validation_ids = [i for i in ids if i not in set(test_ids)][:nv]
        result.loc[validation_ids, 'split'] = 'validation'
        result.loc[test_ids, 'split'] = 'test'
    return result


def run(cfg):
    root = directory(cfg, 'datasets')
    out = directory(cfg, 'reports') / 'data_audit'
    params = cfg['training']
    source = root / 'raw/building_data_genome_2'
    metadata_path = require_file(source / 'metadata.csv')
    meter_path = require_file(source / 'electricity_cleaned.csv')
    weather_path = require_file(source / 'weather.csv')
    quality_path = require_file(out / 'column_quality.csv')
    summary = json.loads(require_file(out / 'audit_summary.json').read_text(encoding='utf-8'))
    for item in summary['sources']:
        if item['source_id'].startswith('bdg2_') and item['status'] != 'audited':
            raise InputError('BDG2 audit must pass before preparation.')
    meta = pd.read_csv(metadata_path)
    require_columns(meta, ['building_id', 'site_id', 'primaryspaceusage', 'sqm', 'timezone', 'electricity'], 'BDG2 metadata')
    if meta['building_id'].duplicated().any():
        raise InputError('BDG2 metadata building_id must be unique.')
    meta = meta.rename(columns={'primaryspaceusage': 'building_use', 'sqm': 'floor_area_m2', 'lat': 'latitude'})
    meter_quality = pd.read_csv(quality_path)
    meter_quality = meter_quality.loc[meter_quality.source_id.eq('bdg2_cleaned_electricity')].rename(columns={'column': 'building_id'})
    meta = meta.merge(meter_quality[['building_id', 'missing_fraction', 'negative_count', 'zero_count', 'rows']],
                      on='building_id', how='left', validate='one_to_one')
    area = pd.to_numeric(meta.floor_area_m2, errors='coerce')
    eligible = (meta.electricity.eq('Yes') & meta.building_use.isin(params['building_uses']) &
                np.isfinite(area) & area.gt(0) & meta.latitude.between(-90, 90) & meta.missing_fraction.le(1 - params['minimum_meter_coverage']) &
                meta.negative_count.eq(0) & (meta.zero_count / meta.rows).le(params['maximum_zero_fraction']))
    meta['eligible'] = eligible
    meta.to_csv(out / 'building_eligibility.csv', index=False)
    candidates = meta.loc[eligible].copy()
    selected = []
    for use in params['building_uses']:
        group = candidates.loc[candidates.building_use.eq(use)].sort_values('building_id')
        if len(group) < 5:
            raise InputError(f'{use}: only {len(group)} eligible measured buildings. Choose a supported use or revise the declared quality threshold in config/project.json.')
        group = group.sample(n=min(len(group), params['max_buildings_per_use']), random_state=params['seed'])
        selected.append(group)
    from pipeline.common import resolve
    excluded_test_ids = (json.loads(require_file(resolve(params['exclude_from_test_ids_file'])).read_text(encoding='utf-8'))
                         if params.get('exclude_from_test_ids_file') else [])
    buildings = split_buildings(pd.concat(selected, ignore_index=True), params['seed'],
                                params['validation_fraction'], params['test_fraction'], excluded_test_ids)
    meters = pd.read_csv(meter_path, usecols=['timestamp', *buildings.building_id], parse_dates=['timestamp'])
    if meters.timestamp.duplicated().any():
        raise InputError('Duplicate BDG2 wall timestamps require source review; not silently aggregated.')
    if not meters.timestamp.diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise InputError('BDG2 meter index must have regular hourly source timestamps.')
    long = meters.melt(id_vars='timestamp', var_name='building_id', value_name='electricity_kwh')
    long = long.rename(columns={'timestamp': 'timestamp_local_standard'}).dropna(subset=['electricity_kwh'])
    if not np.isfinite(long.electricity_kwh).all() or (long.electricity_kwh < 0).any():
        raise InputError('Meter targets must be finite and nonnegative; audit before proceeding.')
    long = long.merge(buildings[['building_id', 'site_id', 'building_use', 'floor_area_m2', 'latitude', 'timezone', 'split']],
                      on='building_id', how='left', validate='many_to_one')
    weather = pd.read_csv(weather_path, usecols=['timestamp', 'site_id', 'airTemperature'], parse_dates=['timestamp'])
    weather = weather.rename(columns={'timestamp': 'timestamp_local_standard', 'airTemperature': 'air_temperature_c'})
    if weather.duplicated(['site_id', 'timestamp_local_standard']).any():
        raise InputError('Duplicate site/weather timestamp keys; cannot safely join.')
    long = long.merge(weather, on=['site_id', 'timestamp_local_standard'], how='left', validate='many_to_one', indicator=True)
    unmatched = int(long['_merge'].eq('left_only').sum())
    long = long.drop(columns='_merge')
    long['data_origin'] = 'OBSERVED_METER'
    long['electricity_wh_m2'] = long.electricity_kwh * 1000 / long.floor_area_m2
    buildings.to_csv(root / 'processed/train_buildings.csv', index=False)
    long.to_csv(root / 'processed/train_meter_hourly.csv.gz', index=False, compression='gzip')
    write_json(out / 'preparation_manifest.json', {
        'created_utc': now(), 'config': params,
        'input_sha256': {p.name: sha256(p) for p in (metadata_path, meter_path, weather_path, quality_path)},
        'buildings': len(buildings), 'rows': len(long),
        'buildings_by_use_split': buildings.groupby(['building_use', 'split']).size().reset_index(name='count').to_dict('records'),
        'weather_unmatched_rows': unmatched,
        'temperature_missing_fraction': float(long.air_temperature_c.isna().mean()),
        'excluded_test_ids': excluded_test_ids,
        'time_basis': 'Publisher source-local regular wall time; weather explicitly ignores DST. Retained for training; not falsely converted into actual UTC meter instants.',
        'quality_selection': 'Declared coverage/area/nonnegative checks use all source periods to define the eligible cohort, not to tune model parameters.',
        'evaluation': 'Disjoint buildings per use; sites may be shared across splits. This is unseen-building evaluation, not unseen-site or Barcelona validation.'})
    print(f'Prepared {len(long):,} measured hourly targets from {len(buildings)} buildings.', flush=True)
    return buildings
