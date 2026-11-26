import pandas as pd
import pytest

from pipeline.common import InputError
from pipeline.step_07_energy_balance.evaluate import evaluate
from pipeline.step_08_impact_metrics.screen import REQUIRED, screen


def test_missing_sources_stop_financial_and_emissions_claims():
    with pytest.raises(InputError):
        screen(pd.DataFrame(), pd.DataFrame(), {})


def test_partial_period_has_no_annual_payback_and_redistribution_adds_no_emissions_gain():
    hours = pd.date_range('2026-01-01', periods=2, freq='h', tz='UTC')
    pv = pd.DataFrame({'timestamp_utc': hours, 'pv_generation_kwh': 10})
    demand = pd.DataFrame([{'timestamp_utc': t, 'building_id': b, 'demand_kwh': 100}
                           for t in hours for b in ('host', 'other')])
    shares = demand[['timestamp_utc', 'building_id']].assign(beta=0.5)
    hourly, summary = evaluate(pv, demand, 'host', shares)
    assumptions = dict(zip(REQUIRED, [0.2, 0.05, 0.1, 1000, 10]))
    assumptions['sources'] = [{'assumption_name': k, 'source_url': 'test-fixture-only', 'source_date': '2026-01-01'} for k in REQUIRED]
    result, participants = screen(hourly, summary, assumptions)
    assert result.simple_payback_years.isna().all()
    assert not result.full_year.any()
    solar = result[result.scenario.ne('grid_only')]
    assert (solar.additional_avoided_import_emissions_vs_host_kgco2e == 0).all()
    assert len(participants) == 8
