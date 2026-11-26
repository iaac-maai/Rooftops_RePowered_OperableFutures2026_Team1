"""Run established EnergyPlus physics for a small, explicit office scenario grid."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import itertools
import json
from pathlib import Path
import re
import subprocess

import numpy as np
import pandas as pd

from pipeline.common import InputError, ROOT, load_config, now, require_file, resolve, sha256, write_json


def call_engine(engine, args, log):
    # ReadVarsESO uses fixed scratch filenames even with --output-directory.
    # Isolate the process CWD as well as its output path for concurrent runs.
    result = subprocess.run([str(engine), *map(str, args)], cwd=log.parent,
                            capture_output=True, text=True, errors='replace')
    log.write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    if result.returncode:
        raise InputError(f'EnergyPlus exited {result.returncode}; inspect {log}')


def compact_schedule(start, duration, weekend, standby=0, on=1):
    fields = ['Through: 12/31', 'For: SummerDesignDay WinterDesignDay', 'Until: 24:00', on,
              'For: Weekdays', f'Until: {start:02d}:00', standby,
              f'Until: {start + duration:02d}:00', on, 'Until: 24:00', standby,
              'For: AllOtherDays', f'Until: {start:02d}:00', standby,
              f'Until: {start + duration:02d}:00', standby + (on - standby) * weekend,
              'Until: 24:00', standby]
    return [{'field': value} for value in fields]


def floor_area(model):
    area = 0
    for surface in model['BuildingSurface:Detailed'].values():
        if surface['surface_type'].lower() != 'floor':
            continue
        zone = model['Zone'][surface['zone_name']]
        if zone.get('part_of_total_floor_area', 'Yes') == 'No':
            continue
        points = np.array([[v['vertex_x_coordinate'], v['vertex_y_coordinate']] for v in surface['vertices']])
        area += abs(np.dot(points[:, 0], np.roll(points[:, 1], 1)) - np.dot(points[:, 1], np.roll(points[:, 0], 1))) / 2 * zone.get('multiplier', 1)
    if area <= 0:
        raise InputError('Reference model has no positive conditioned floor area.')
    return float(area)


def prepare_base(setup, params, root):
    engine = require_file(resolve(setup['executable']))
    base = require_file(engine.parent / 'ExampleFiles' / f"{params['archetype']}.idf")
    out = root / 'base_model'
    out.mkdir(parents=True, exist_ok=True)
    call_engine(engine, ['--convert-only', '-d', out, base], out / 'convert.log')
    model = json.loads((out / f"{params['archetype']}.epJSON").read_text(encoding='utf-8'))
    # Replace Chicago design days with the Barcelona IWEC companion design days.
    epw = require_file(resolve(setup['weather_epw']))
    ddy = require_file(epw.with_suffix('.ddy'))
    ddy_idf = out / 'barcelona_design_days.idf'
    # This IWEC companion file contains a Windows-1252 degree symbol in comments.
    ddy_idf.write_text('Version,26.2;\nBuilding,Barcelona design days,0,City;\n'
                       'GlobalGeometryRules,UpperLeftCorner,CounterClockWise,Relative;\n'
                       + ddy.read_text(encoding='cp1252'), encoding='utf-8')
    call_engine(engine, ['--convert-only', '-d', out, ddy_idf], out / 'convert_design_days.log')
    design = json.loads((out / 'barcelona_design_days.epJSON').read_text(encoding='utf-8'))
    days = design['SizingPeriod:DesignDay']
    winter = [(name, value) for name, value in days.items() if value['day_type'] == 'WinterDesignDay']
    summer = [(name, value) for name, value in days.items() if value['day_type'] == 'SummerDesignDay']
    heating = min(winter, key=lambda pair: pair[1]['maximum_dry_bulb_temperature'])
    cooling = max(summer, key=lambda pair: pair[1]['maximum_dry_bulb_temperature'])
    model['SizingPeriod:DesignDay'] = dict([heating, cooling])
    write_json(out / 'selected_design_days.json', model['SizingPeriod:DesignDay'])
    model['Site:Location'] = {'Barcelona IWEC reference station': {
        'latitude': float(setup['weather_header'][6]), 'longitude': float(setup['weather_header'][7]),
        'time_zone': float(setup['weather_header'][8]), 'elevation': float(setup['weather_header'][9])}}
    control = next(iter(model['SimulationControl'].values()))
    control['run_simulation_for_sizing_periods'] = 'No'
    control['run_simulation_for_weather_file_run_periods'] = 'Yes'
    period = next(iter(model['RunPeriod'].values()))
    period['begin_year'] = params['simulation_year']
    period['end_year'] = params['simulation_year']
    period['use_weather_file_daylight_saving_period'] = 'No'
    period['day_of_week_for_start_day'] = pd.Timestamp(year=params['simulation_year'], month=1, day=1).day_name()
    model['Timestep'] = {'Timestep 1': {'number_of_timesteps_per_hour': 4}}
    model['Output:Variable'] = {'Outdoor temperature': {'key_value': '*', 'variable_name': 'Site Outdoor Air Drybulb Temperature', 'reporting_frequency': 'Hourly'}}
    model['Output:Meter'] = {'Facility electricity': {'key_name': 'Electricity:Facility', 'reporting_frequency': 'Hourly'}}
    model.pop('Output:Table:SummaryReports', None)
    return engine, epw, model


def configurations(params):
    grid = params['grid']
    result = []
    for i, values in enumerate(itertools.product(*(grid[key] for key in grid))):
        record = dict(zip(grid, values))
        record['simulation_id'] = f'office_{i:03d}'
        result.append(record)
    return result


def run_one(record, base, engine, epw, params, root):
    folder = root / record['simulation_id']
    folder.mkdir(parents=True, exist_ok=True)
    model = deepcopy(base)
    start, duration, weekend = record['weekday_start_hour'], record['weekday_duration_hours'], record['weekend_activity_fraction']
    for name, standby in [('BLDG_OCC_SCH', 0), ('BLDG_LIGHT_SCH', 0.05), ('BLDG_EQUIP_SCH', 0.15)]:
        model['Schedule:Compact'][name]['data'] = compact_schedule(start, duration, weekend, standby)
    model['Schedule:Compact']['HVACOperationSchd']['data'] = compact_schedule(start, duration, 1 if weekend > 0 else 0)
    for equipment in model['ElectricEquipment'].values():
        if equipment['design_level_calculation_method'] != 'Watts/Area':
            raise InputError('Reference electric-equipment schema needs review before modifying load density.')
        equipment['watts_per_floor_area'] = record['equipment_w_per_m2']
    path = folder / 'model.epJSON'
    write_json(path, model)
    call_engine(engine, ['--weather', epw, '--readvars', '--output-directory', folder, path], folder / 'run.log')
    err = (folder / 'eplusout.err').read_text(encoding='utf-8', errors='replace')
    if re.search(r'\*\*\s*(Severe|Fatal)\s*\*\*', err):
        raise InputError(f'Severe EnergyPlus errors: {folder / "eplusout.err"}')
    write_json(folder / 'scenario.json', {**record, 'floor_area_m2': floor_area(model),
                                        'data_origin': 'SIMULATED_PHYSICS', 'scenario_origin': 'SYNTHETIC_SCHEDULE',
                                        'input_sha256': sha256(path)})
    print(f'SIMULATED {record["simulation_id"]}', flush=True)
    return {**record, 'floor_area_m2': floor_area(model), 'status': 'completed'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Smoke-test only the first N configurations')
    args = parser.parse_args(argv)
    setup = json.loads(require_file(ROOT / 'reports/simulation_surrogate/setup_manifest.json').read_text(encoding='utf-8'))
    params = json.loads(require_file(ROOT / 'config/simulation.json').read_text(encoding='utf-8'))
    root = ROOT / 'datasets/synthetic/energyplus'
    root.mkdir(parents=True, exist_ok=True)
    engine, epw, base = prepare_base(setup, params, root)
    records = configurations(params)
    if args.limit:
        records = records[:args.limit]
    results = []
    with ThreadPoolExecutor(max_workers=params['workers']) as pool:
        futures = [pool.submit(run_one, r, base, engine, epw, params, root) for r in records]
        for record, future in zip(records, futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({**record, 'status': 'failed', 'error': str(exc)})
                print(f'FAILED {record["simulation_id"]}: {exc}', flush=True)
    pd.DataFrame(results).to_csv(root / 'scenario_manifest.csv', index=False)
    write_json(ROOT / 'reports/simulation_surrogate/simulation_manifest.json', {
        'created_utc': now(), 'parameters': params, 'weather_sha256': sha256(epw),
        'reference_model': params['archetype'], 'results': results,
        'provenance': 'SIMULATED_PHYSICS',
        'limitations': 'One US office reference envelope/geometry/HVAC, Barcelona IWEC and design days, synthetic schedules. No local meter calibration or geometry generalization. Calendar year 2017 is an explicit simulation convention, not observed 2017 Barcelona weather.'})
    if any(r['status'] != 'completed' for r in results):
        raise InputError('Some simulations failed. Inspect reports/simulation_surrogate and scenario run logs.')


if __name__ == '__main__':
    main()
