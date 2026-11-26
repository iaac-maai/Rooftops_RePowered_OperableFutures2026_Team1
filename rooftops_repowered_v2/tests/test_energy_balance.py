import numpy as np
import pandas as pd
import pytest

from pipeline.common import InputError
from pipeline.step_07_energy_balance.evaluate import evaluate, planned_shares


def inputs(host_load=100, neighbour_load=25):
    hours = pd.date_range('2026-01-01', periods=3, freq='h', tz='UTC')
    pv = pd.DataFrame({'timestamp_utc': hours, 'pv_generation_kwh': [30, 0, 50]})
    demand = pd.DataFrame([{'timestamp_utc': t, 'building_id': b, 'demand_kwh': load}
                           for t in hours for b, load in [('host', host_load), ('neighbour', neighbour_load)]])
    shares = demand[['timestamp_utc', 'building_id']].assign(beta=0.5)
    return pv, demand, shares


def test_energy_conservation_and_no_false_gain_when_all_pv_already_used():
    pv, demand, shares = inputs()
    hourly, summary = evaluate(pv, demand, 'host', shares)
    assert (hourly[['demand_kwh', 'allocated_pv_kwh', 'used_pv_kwh', 'grid_import_kwh', 'unconsumed_allocated_pv_kwh']] >= 0).all().all()
    np.testing.assert_allclose(hourly.demand_kwh, hourly.used_pv_kwh + hourly.grid_import_kwh)
    np.testing.assert_allclose(hourly.allocated_pv_kwh, hourly.used_pv_kwh + hourly.unconsumed_allocated_pv_kwh)
    solar = summary[summary.scenario.ne('grid_only')]
    assert (solar.pv_generation_kwh == pv.pv_generation_kwh.sum()).all()
    assert (solar.import_reduction_vs_host_only_kwh == 0).all()


def test_sharing_can_perform_worse_than_host_only():
    pv, demand, shares = inputs(neighbour_load=0)
    _, summary = evaluate(pv, demand, 'host', shares)
    collective = summary.set_index('scenario').loc['fixed_equal_shares']
    assert collective.import_reduction_vs_host_only_kwh < 0


@pytest.mark.parametrize('problem', ['negative_pv', 'duplicate_pv', 'missing_load', 'bad_beta', 'wrong_year', 'negative_load'])
def test_invalid_energy_inputs_are_rejected(problem):
    pv, demand, shares = inputs()
    if problem == 'negative_pv':
        pv.loc[0, 'pv_generation_kwh'] = -1
    elif problem == 'duplicate_pv':
        pv = pd.concat([pv, pv.iloc[:1]])
    elif problem == 'missing_load':
        demand = demand.iloc[:-1]
    elif problem == 'bad_beta':
        shares['beta'] = 0.7
    elif problem == 'wrong_year':
        pv['timestamp_utc'] += pd.DateOffset(years=1)
    elif problem == 'negative_load':
        demand.loc[0, 'demand_kwh'] = -1
    with pytest.raises(InputError):
        evaluate(pv, demand, 'host', shares)


def test_plans_reject_observed_targets_and_handle_zero_forecast():
    _, demand, _ = inputs()
    forecast = demand.rename(columns={'demand_kwh': 'predicted_electricity_kwh'}).assign(data_origin='OBSERVED_METER')
    with pytest.raises(InputError, match='not observed'):
        planned_shares(forecast)
    forecast['data_origin'] = 'ML_PREDICTION'
    forecast['predicted_electricity_kwh'] = 0
    plan = planned_shares(forecast)
    assert (plan.beta == 0.5).all()
    assert np.allclose(plan.groupby('timestamp_utc').beta.sum(), 1)
