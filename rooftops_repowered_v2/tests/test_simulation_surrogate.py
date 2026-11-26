import numpy as np
import pandas as pd
import pytest

from pipeline.common import InputError
from pipeline.step_05_simulation_surrogate.train import hour_start_labels, features
from pipeline.step_05_simulation_surrogate.simulate import compact_schedule
from pipeline.step_05_simulation_surrogate.predict import predict_frame


def test_energyplus_hour_end_24_maps_to_last_interval_of_same_day():
    values = hour_start_labels([' 01/01  01:00:00', ' 01/01  24:00:00', ' 01/02  01:00:00'], 2017)
    assert values.tolist() == [pd.Timestamp('2017-01-01T00:00:00'), pd.Timestamp('2017-01-01T23:00:00'), pd.Timestamp('2017-01-02T00:00:00')]
    with pytest.raises(InputError):
        hour_start_labels([' 01/01  00:00:00'], 2017)


def test_schedule_load_features_are_known_inputs_not_simulated_targets():
    frame = pd.DataFrame({'timestamp_local_standard': ['2017-01-02T08:00:00', '2017-01-02T09:00:00'],
                          'weekday_start_hour': 9, 'weekday_duration_hours': 8, 'equipment_w_per_m2': 10,
                          'weekend_activity_fraction': 0, 'air_temperature_c': 20,
                          'temperature_6h_mean_c': 19, 'solar_global_w_m2': 100,
                          'simulation_id': ['exclude_a', 'exclude_a'], 'electricity_kwh': [999, 1]})
    x = features(frame)
    assert x.activity_fraction.tolist() == [0, 1]
    np.testing.assert_allclose(x.scheduled_equipment_w_per_m2, [1.5, 10])
    assert 'simulation_id' not in x and 'electricity_kwh' not in x
    schedule = compact_schedule(9, 8, 0.2)
    assert {'field': 'Until: 17:00'} in schedule


def test_surrogate_refuses_unvalidated_geometry_scaling():
    frame = pd.DataFrame({'timestamp_utc': ['2026-01-01T00:00:00Z'], 'building_id': 'future',
                          'archetype': 'reference', 'floor_area_m2': 1000, 'timezone': 'Europe/Madrid',
                          'air_temperature_c': 10, 'temperature_6h_mean_c': 10, 'solar_global_w_m2': 0,
                          'weekday_start_hour': 9, 'weekday_duration_hours': 8, 'equipment_w_per_m2': 10,
                          'weekend_activity_fraction': 0})
    with pytest.raises(InputError, match='area scaling'):
        predict_frame(frame, {'archetype': 'reference', 'floor_area_m2': 511})
