import numpy as np
import pandas as pd
import pytest

from pipeline.common import InputError
from pipeline.step_04_demand_preparation.prepare import split_buildings
from pipeline.step_04_demand_preparation.features import make_features
from pipeline.step_05_demand_xgboost.train import assert_disjoint
from pipeline.step_05_demand_baseline_hour_of_week.model import GroupMeanBaseline
from pipeline.step_05_demand_xgboost.predict import predict_frame


def test_disjoint_buildings_and_prior_experiment_excluded_from_new_test():
    buildings = pd.DataFrame({'building_id': [f'b{i}' for i in range(20)], 'building_use': 'Office'})
    prior = [f'b{i}' for i in range(10)]
    result = split_buildings(buildings, 42, 0.2, 0.2, prior)
    assert_disjoint(result)
    assert not set(prior) & set(result.loc[result.split.eq('test'), 'building_id'])
    assert result.equals(split_buildings(buildings, 42, 0.2, 0.2, prior))
    corrupted = pd.concat([result, result.iloc[:1].assign(split='test')])
    if result.iloc[0]['split'] == 'test':
        corrupted.iloc[-1, corrupted.columns.get_loc('split')] = 'train'
    with pytest.raises(InputError):
        assert_disjoint(corrupted)


def test_baseline_uses_training_labels_only_and_features_exclude_identifiers():
    training = pd.DataFrame({'timestamp_local_standard': ['2016-01-04T00:00:00', '2016-01-11T00:00:00'],
                             'building_use': 'Office', 'electricity_wh_m2': [10, 20],
                             'floor_area_m2': 100, 'latitude': 41.4, 'air_temperature_c': 12,
                             'building_id': ['train_a', 'train_b'], 'site_id': 'do_not_use'})
    baseline = GroupMeanBaseline().fit(training)
    holdout = training.assign(electricity_wh_m2=99999, building_id='unseen')
    np.testing.assert_allclose(baseline.predict_intensity(holdout), [15, 15])
    features = make_features(holdout)
    assert not {'building_id', 'site_id', 'electricity_wh_m2', 'electricity_kwh'} & set(features)


def test_unknown_residential_use_is_not_silently_mapped_to_office():
    frame = pd.DataFrame({'timestamp_utc': ['2026-01-01T00:00:00Z'], 'building_id': 'new',
                          'building_use': 'Residential', 'floor_area_m2': 100,
                          'latitude': 41.4, 'timezone': 'Europe/Madrid', 'air_temperature_c': 12})
    with pytest.raises(InputError, match='Unsupported'):
        predict_frame(frame, {'supported_uses': ['Office']})
