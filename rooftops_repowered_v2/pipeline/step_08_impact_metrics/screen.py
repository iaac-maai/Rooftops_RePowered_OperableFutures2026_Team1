import calendar
import numpy as np
import pandas as pd

from pipeline.common import InputError
from pipeline.temporal import as_utc, require_hourly_index

REQUIRED = ['grid_price_eur_per_kwh', 'export_price_eur_per_kwh',
            'grid_emissions_kgco2e_per_kwh', 'capex_eur', 'annual_om_eur']


def screen(hourly, summary, assumptions, timezone='Europe/Madrid'):
    for key in REQUIRED:
        value = assumptions.get(key)
        if value is None or not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
            raise InputError(f'Provide a finite nonnegative, sourced impact assumption: {key}.')
    references = assumptions.get('sources', [])
    for key in REQUIRED:
        if not any(ref.get('assumption_name') == key and ref.get('source_url') and ref.get('source_date')
                   for ref in references):
            raise InputError(f'Provide source_url and source_date for {key} in the assumptions sources list.')
    times = as_utc(hourly.timestamp_utc.drop_duplicates()).sort_values().reset_index(drop=True)
    require_hourly_index(times, 'Impact period')
    civil = times.dt.tz_convert(timezone)
    year = civil.iloc[0].year
    full_year = (len(times) == (8784 if calendar.isleap(year) else 8760)
                 and civil.iloc[0] == pd.Timestamp(year=year, month=1, day=1, tz=timezone)
                 and civil.iloc[-1] == pd.Timestamp(year=year + 1, month=1, day=1, tz=timezone) - pd.Timedelta(hours=1))
    result = summary.copy()
    price = assumptions['grid_price_eur_per_kwh']
    export = assumptions['export_price_eur_per_kwh']
    emissions = assumptions['grid_emissions_kgco2e_per_kwh']
    result['period_import_cost_eur'] = result.grid_import_kwh * price
    result['period_export_revenue_eur'] = result.unconsumed_allocated_pv_kwh * export
    result['period_net_electricity_cost_eur'] = result.period_import_cost_eur - result.period_export_revenue_eur
    baseline_cost = result.loc[result.scenario.eq('grid_only'), 'period_net_electricity_cost_eur'].iloc[0]
    result['period_bill_saving_vs_grid_only_eur'] = baseline_cost - result.period_net_electricity_cost_eur
    result['indicative_avoided_import_emissions_kgco2e'] = (result.demand_kwh - result.grid_import_kwh) * emissions
    result['additional_avoided_import_emissions_vs_host_kgco2e'] = result.import_reduction_vs_host_only_kwh * emissions
    result['full_year'] = bool(full_year)
    result['simple_payback_years'] = np.nan
    if full_year:
        savings = result.period_bill_saving_vs_grid_only_eur - assumptions['annual_om_eur']
        eligible = ~result.scenario.eq('grid_only') & savings.gt(0)
        result.loc[eligible, 'simple_payback_years'] = assumptions['capex_eur'] / savings.loc[eligible]
    participants = hourly.groupby(['scenario', 'building_id'], as_index=False)[[
        'demand_kwh', 'allocated_pv_kwh', 'used_pv_kwh', 'grid_import_kwh', 'unconsumed_allocated_pv_kwh']].sum()
    participants['solar_coverage_fraction'] = participants.used_pv_kwh / participants.demand_kwh.replace(0, np.nan)
    participants['gross_period_bill_saving_eur'] = (participants.used_pv_kwh * price + participants.unconsumed_allocated_pv_kwh * export)
    participants['allocated_pv_fraction'] = participants.allocated_pv_kwh / participants.groupby('scenario').allocated_pv_kwh.transform('sum').replace(0, np.nan)
    participants['benefit_scope'] = 'Gross bill proxy before participant capital/O&M cost sharing; no demographic claims'
    return result, participants
