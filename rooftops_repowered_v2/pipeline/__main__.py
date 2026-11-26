"""Run from the project root: python -m pipeline --help."""
import argparse
import json
from pathlib import Path
import sys

from pipeline.common import InputError, directory, load_config, require_file, resolve, write_json


def case_ready(cfg):
    case = cfg['case_study']
    if not case.get('host_building_id'):
        raise InputError('Host selection is deferred. Set case_study.host_building_id in config/project.json and fill datasets/inputs/building_cluster.csv before running case-study matching. No host has been invented.')
    return case


def status(cfg):
    root = directory(cfg, 'datasets')
    models = directory(cfg, 'models')
    readiness = directory(cfg, 'reports') / 'demand_model/readiness.json'
    state = {'case_study': cfg['case_study']['status'], 'host_building_id': cfg['case_study']['host_building_id'],
             'roof_capacity_readiness': json.loads((directory(cfg, 'reports') / 'roof_capacity/A160/readiness.json').read_text(encoding='utf-8')) if (directory(cfg, 'reports') / 'roof_capacity/A160/readiness.json').exists() else 'not_run',
             'active_demand_route': cfg.get('demand_model', {}).get('route', 'measured_bdg2'),
             'audit_exists': (root / 'processed/data_quality_report.csv').exists(),
             'prepared_demand_exists': (root / 'processed/train_meter_hourly.csv.gz').exists(),
             'trained_model_exists': (models / 'demand_xgboost.joblib').exists(),
             'bdg2_model_readiness': json.loads(readiness.read_text(encoding='utf-8')) if readiness.exists() else None,
             'office_surrogate_readiness': json.loads((directory(cfg, 'reports') / 'simulation_surrogate/readiness.json').read_text(encoding='utf-8')) if (directory(cfg, 'reports') / 'simulation_surrogate/readiness.json').exists() else None,
             'model_output_directory': str(models),
             'case_study_inputs_present': {key: resolve(cfg['case_study'][key]).exists() for key in ('buildings_csv', 'pv_csv', 'demand_csv')}}
    print(json.dumps(state, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Roofscapes (Re)Powered: offline research pipeline')
    parser.add_argument('--config', type=Path, help='Project JSON configuration; paths resolve against the project root')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, help_text in [('status', 'Show real progress and missing host inputs'),
                            ('audit', 'Scan all eight original CSV datasets'),
                            ('prepare', 'Prepare measured demand and building-level splits'),
                            ('train', 'Fit and benchmark XGBoost and baselines'),
                            ('train-office-surrogate', 'Fit/evaluate the office EnergyPlus surrogate after simulations'),
                            ('match', 'Evaluate four energy scenarios once host inputs are supplied'),
                            ('impacts', 'Screen saved balances using sourced assumptions')]:
        commands.add_parser(name, help=help_text)
    predict = commands.add_parser('predict', aliases=['predict-bdg2'], help='Estimate demand using the configured route; predict-bdg2 explicitly uses the measured benchmark')
    predict.add_argument('--input', required=True)
    predict.add_argument('--output')
    predict.add_argument('--model', default='recommended')
    office = commands.add_parser('predict-office', help='Predict within the validated office-reference simulation domain')
    office.add_argument('--input', required=True)
    office.add_argument('--output', default='datasets/processed/office_reference_demand.csv')
    plan = commands.add_parser('plan-shares', help='Export a hypothetical hourly plan from demand forecasts')
    plan.add_argument('--input', required=True)
    plan.add_argument('--output', default='datasets/inputs/sharing_coefficients.csv')
    pv = commands.add_parser('import-pvgis', help='Normalize a PVGIS hourly CSV with documented settings')
    pv.add_argument('--input', required=True)
    pv.add_argument('--settings', required=True, help='JSON with roof_id, capacity_kwp, timestamp_basis, power_unit, tilt, azimuth, loss_percent, weather_year and source_url')
    pv.add_argument('--output', default='datasets/processed/pv_hourly.csv')
    acquire = commands.add_parser('pvgis-acquire', help='Acquire official hourly PVGIS responses for separate hypothetical roof-capacity sensitivity')
    acquire.add_argument('--settings', default='config/pvgis_hypothetical.json')
    manual = commands.add_parser('pvgis-import-hypothetical', help='Manual CSV fallback for a separate hypothetical PVGIS scenario; never enables sharing')
    manual.add_argument('--settings', default='config/pvgis_hypothetical.json')
    manual.add_argument('--input', required=True)
    manual.add_argument('--scenario', required=True)
    roof = commands.add_parser('roof-capacity', help='Dated/reviewed roof geometry -> estimated panel-capacity scenarios')
    roof.add_argument('--settings', default='config/roof_capacity.json')
    milestone = commands.add_parser('roof-feasibility', help='A160 rooftop-only retrospective/reference/additional assessments and PVGIS handoff')
    milestone.add_argument('--settings', default='config/a160_assessments.json')
    milestone.add_argument('--rebuild-prediction', action='store_true', help='Explicitly regenerate the retrospective geometry before reference annotation')
    fetch = commands.add_parser('roof-fetch-building', help='Cache public geocoder/cadastral candidate; does not verify as-built geometry')
    fetch.add_argument('--settings', default='config/roof_capacity.json')
    export = commands.add_parser('roof-pvgis-settings', help='Export PVGIS settings from a reviewed positive-capacity scenario')
    export.add_argument('--settings', default='config/roof_capacity.json')
    export.add_argument('--scenario', default='base')
    export.add_argument('--output', default='datasets/inputs/A160_pvgis_settings.json')
    city = commands.add_parser('roof-compare-map', help='Independent comparison against a dated municipal GeoJSON export')
    city.add_argument('--settings', default='config/roof_capacity.json')
    city.add_argument('--input', required=True)
    city.add_argument('--source-date', required=True)
    city.add_argument('--source-url', required=True)
    city.add_argument('--output', default='datasets/processed/roof_capacity/A160/municipal_map_comparison.csv')
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        if args.command == 'status':
            status(cfg)
        elif args.command in ('pvgis-acquire','pvgis-import-hypothetical'):
            from pipeline.step_03_pvgis.acquire import run
            result=run(args.settings, getattr(args,'input',None), getattr(args,'scenario',None))
            print(json.dumps({'available_scenarios':result['available_scenarios'],'failed_scenarios':result['failed_scenarios'],
                'actual_installed_capacity_kwp':None,'energy_sharing_eligible':False},indent=2))
            if args.command=='pvgis-acquire' and result['failed_scenarios']:
                return 2
            if args.command=='pvgis-import-hypothetical':
                selected=next(row for row in result['scenarios'] if row['scenario_id']==args.scenario)
                if selected['status'] not in ('available','not_applicable_zero_capacity'):
                    return 2
        elif args.command == 'roof-feasibility':
            from pipeline.step_02_roof_capacity.milestone import run
            run(args.settings, args.rebuild_prediction)
        elif args.command == 'roof-capacity':
            from pipeline.step_02_roof_capacity.adapter import run
            print(run(args.settings).to_string(index=False))
        elif args.command == 'roof-fetch-building':
            from pipeline.step_02_roof_capacity.acquisition import fetch_building
            print(json.dumps(fetch_building(args.settings), indent=2))
        elif args.command == 'roof-pvgis-settings':
            from pipeline.step_02_roof_capacity.adapter import export_pvgis_settings
            print(json.dumps(export_pvgis_settings(args.settings, args.scenario, args.output), indent=2))
        elif args.command == 'roof-compare-map':
            from pipeline.step_02_roof_capacity.municipal_comparison import compare
            print(json.dumps(compare(args.settings, args.input, args.source_date, args.source_url, args.output), indent=2))
        elif args.command == 'audit':
            from pipeline.step_01_data_audit.audit import run
            run(cfg)
        elif args.command == 'prepare':
            from pipeline.step_04_demand_preparation.prepare import run
            run(cfg)
        elif args.command == 'train':
            from pipeline.step_05_demand_xgboost.train import run
            run(cfg)
        elif args.command == 'train-office-surrogate':
            from pipeline.step_05_simulation_surrogate.train import run
            run()
        elif args.command == 'predict-office':
            from pipeline.step_05_simulation_surrogate.predict import run
            run(args.input, args.output)
        elif args.command in ('predict', 'predict-bdg2'):
            route = cfg.get('demand_model', {}).get('route', 'measured_bdg2')
            if args.command == 'predict-bdg2' or route == 'measured_bdg2':
                from pipeline.step_05_demand_xgboost.predict import run
                run(cfg, args.input, args.output, args.model)
            elif route == 'office_energyplus_surrogate':
                from pipeline.step_05_simulation_surrogate.predict import run
                if args.model != 'recommended':
                    raise InputError('--model overrides apply to predict-bdg2. Configure demand_model.route/artifact for the primary route.')
                output = args.output or cfg['case_study']['demand_csv']
                run(args.input, output, cfg['demand_model']['artifact'])
            else:
                raise InputError(f'Unsupported demand_model.route: {route}')
        elif args.command == 'plan-shares':
            import pandas as pd
            from pipeline.step_07_energy_balance.evaluate import planned_shares
            shares = planned_shares(pd.read_csv(require_file(resolve(args.input))))
            target = resolve(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            shares.to_csv(target, index=False)
        elif args.command == 'import-pvgis':
            from pipeline.step_03_pvgis.importer import import_hourly, validate_generation_role
            settings = json.loads(require_file(resolve(args.settings)).read_text(encoding='utf-8'))
            validate_generation_role(settings)
            required = ('roof_id', 'capacity_kwp', 'timestamp_basis', 'power_unit', 'tilt', 'azimuth', 'loss_percent', 'weather_year', 'source_url')
            missing = [key for key in required if settings.get(key) is None]
            if missing:
                raise InputError(f'PVGIS settings need values for {missing}. Do not invent the roof configuration.')
            if settings['capacity_kwp'] <= 0:
                raise InputError('PVGIS installed capacity must be positive.')
            result = import_hourly(require_file(resolve(args.input)), settings['timestamp_basis'], settings['power_unit'])
            result['roof_id'] = settings['roof_id']
            target = resolve(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(target, index=False)
            write_json(target.with_suffix('.settings.json'), settings)
        elif args.command == 'match':
            import pandas as pd
            from pipeline.case_study import validate_inventory
            from pipeline.step_07_energy_balance.evaluate import evaluate
            case = case_ready(cfg)
            pv = pd.read_csv(require_file(resolve(case['pv_csv'])))
            from pipeline.step_03_pvgis.importer import validate_case_study_supply
            validate_case_study_supply(pv)
            demand = pd.read_csv(require_file(resolve(case['demand_csv'])))
            if 'data_origin' not in demand or demand.data_origin.isna().any():
                raise InputError('Demand needs a data_origin label for every row (observed, simulated or predicted).')
            if 'demand_kwh' not in demand:
                demand = demand.rename(columns={'predicted_electricity_kwh': 'demand_kwh'})
            shares = pd.read_csv(require_file(resolve(case['shares_csv'])))
            inventory = pd.read_csv(require_file(resolve(case['buildings_csv'])))
            validate_inventory(inventory, case['host_building_id'], demand.building_id)
            hourly, summary = evaluate(pv, demand, case['host_building_id'], shares)
            root = directory(cfg, 'datasets')
            hourly.to_csv(root / 'results/hourly_balance.csv', index=False)
            summary.to_csv(root / 'results/scenario_comparison.csv', index=False)
            origins = sorted(demand.data_origin.unique().tolist())
            write_json(directory(cfg, 'reports') / 'scenario_evaluation.json', {
                'demand_origins': origins,
                'evaluation_mode': 'planning_estimate' if any('PREDICTION' in origin or 'BASELINE' in origin for origin in origins) else 'reference_scenario_evaluation',
                'limitations': 'Comparing a plan against the same demand predictions used to design it is an internal planning comparison, not independent evidence of AI value. Use held-out observed or independent physics-simulation demands for that claim. Legal eligibility and settlement rules remain unverified.'})
            print(summary.to_string(index=False))
        elif args.command == 'impacts':
            import pandas as pd
            from pipeline.step_08_impact_metrics.screen import screen
            case = case_ready(cfg)
            root = directory(cfg, 'datasets')
            hourly = pd.read_csv(require_file(root / 'results/hourly_balance.csv'))
            summary = pd.read_csv(require_file(root / 'results/scenario_comparison.csv'))
            assumptions = json.loads(require_file(resolve(case['impact_assumptions_json'])).read_text(encoding='utf-8'))
            totals, participants = screen(hourly, summary, assumptions, case['timezone'])
            totals.to_csv(root / 'results/impact_screening.csv', index=False)
            participants.to_csv(root / 'results/participant_benefits.csv', index=False)
    except (InputError, FileNotFoundError, ValueError, KeyError) as exc:
        print(f'Input required: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
