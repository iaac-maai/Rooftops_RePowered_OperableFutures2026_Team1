import numpy as np
import pandas as pd

from pipeline.common import InputError, require_columns
from pipeline.temporal import as_utc, require_hourly_index


def hourly_matrix(frame, value_column, label):
    require_columns(frame, ['timestamp_utc', 'building_id', value_column], label)
    data = frame.copy()
    data.timestamp_utc = as_utc(data.timestamp_utc)
    if data.building_id.isna().any() or data.duplicated(['timestamp_utc', 'building_id']).any():
        raise InputError(f'{label}: missing building IDs or duplicate building/hour keys.')
    values = pd.to_numeric(data[value_column], errors='raise')
    if not np.isfinite(values).all() or values.lt(0).any():
        raise InputError(f'{label}: values must be finite and nonnegative.')
    data[value_column] = values
    matrix = data.pivot(index='timestamp_utc', columns='building_id', values=value_column).sort_index().sort_index(axis=1)
    if matrix.isna().any().any():
        raise InputError(f'{label}: incomplete building/hour grid. Missing loads cannot be zero-filled.')
    require_hourly_index(matrix.index, label)
    return matrix


def planned_shares(forecasts):
    """Create a plan from predictions, never from the evaluator's demand targets.

    Export and freeze this plan before evaluating it. Legal validity and agreement
    timing require separate checks; this function makes no statutory claim.
    """
    require_columns(forecasts, ['data_origin'], 'Allocation forecasts')
    allowed = {'ML_PREDICTION', 'REFERENCE_BASELINE_ESTIMATE', 'SYNTHETIC_SCHEDULE', 'SIMULATED_PHYSICS'}
    if not set(forecasts.data_origin).issubset(allowed):
        raise InputError('Allocation planning requires explicitly predicted/simulated inputs, not observed evaluation meters.')
    loads = hourly_matrix(forecasts, 'predicted_electricity_kwh', 'Allocation forecasts')
    sums = loads.sum(axis=1)
    shares = loads.div(sums.replace(0, np.nan), axis=0).fillna(1 / len(loads.columns))
    result = shares.rename_axis(columns='building_id').stack().rename('beta').reset_index()
    result['data_origin'] = 'HYPOTHETICAL_ALLOCATION'
    return result


def evaluate(pv, demand, host_building_id, coefficients):
    loads = hourly_matrix(demand, 'demand_kwh', 'Demand')
    if host_building_id not in loads.columns:
        raise InputError('Host building must be present in the participant demand inventory.')
    require_columns(pv, ['timestamp_utc', 'pv_generation_kwh'], 'PV')
    solar = pv.copy()
    solar.timestamp_utc = as_utc(solar.timestamp_utc)
    if solar.timestamp_utc.duplicated().any():
        raise InputError('PV contains duplicate UTC hours.')
    solar = solar.set_index('timestamp_utc').sort_index()
    generation = pd.to_numeric(solar.pv_generation_kwh, errors='raise')
    if not np.isfinite(generation).all() or generation.lt(0).any():
        raise InputError('PV energy must be finite and nonnegative.')
    if not loads.index.equals(generation.index):
        raise InputError('PV and demand must have exactly the same UTC hourly index; no cross-year relabeling or dropped hours.')
    shares = hourly_matrix(coefficients, 'beta', 'Pre-agreed coefficients')
    if not shares.index.equals(loads.index) or not shares.columns.equals(loads.columns):
        raise InputError('Coefficient hours and participant IDs must exactly match demand.')
    if not np.allclose(shares.sum(axis=1), 1, atol=1e-9, rtol=0) or (shares > 1).any().any():
        raise InputError('Every hourly coefficient must be in [0,1] and hourly sums must equal 1.')
    plans = {
        'grid_only': loads * 0,
        'host_only': loads * 0,
        'fixed_equal_shares': pd.DataFrame(1 / len(loads.columns), index=loads.index, columns=loads.columns),
        'demand_informed_preagreed': shares,
    }
    plans['host_only'][host_building_id] = 1.0
    all_rows, totals = [], []
    for name, beta in plans.items():
        allocated = beta.mul(generation, axis=0)
        used = np.minimum(allocated, loads)
        imports = loads - used
        export = allocated - used
        if not np.allclose(used + imports, loads) or not np.allclose(used + export, allocated):
            raise AssertionError('Energy conservation failed.')
        columns = {'demand_kwh': loads, 'allocated_pv_kwh': allocated, 'used_pv_kwh': used,
                   'grid_import_kwh': imports, 'unconsumed_allocated_pv_kwh': export, 'beta': beta}
        long = pd.concat({k: v.stack() for k, v in columns.items()}, axis=1).reset_index()
        long['scenario'] = name
        long['allocation_origin'] = 'HYPOTHETICAL_ALLOCATION'
        all_rows.append(long)
        total_generation = float(allocated.to_numpy().sum())
        total_demand = float(loads.to_numpy().sum())
        total_used = float(used.to_numpy().sum())
        totals.append({'scenario': name, 'demand_kwh': total_demand, 'pv_generation_kwh': total_generation,
                       'used_pv_kwh': total_used, 'grid_import_kwh': float(imports.to_numpy().sum()),
                       'unconsumed_allocated_pv_kwh': float(export.to_numpy().sum()),
                       'pv_self_consumption_fraction': total_used / total_generation if total_generation else None,
                       'solar_demand_coverage': total_used / total_demand if total_demand else None})
    summary = pd.DataFrame(totals)
    for reference in ('host_only', 'fixed_equal_shares'):
        reference_import = summary.loc[summary.scenario.eq(reference), 'grid_import_kwh'].iloc[0]
        summary[f'import_reduction_vs_{reference}_kwh'] = reference_import - summary.grid_import_kwh
    return pd.concat(all_rows, ignore_index=True), summary
