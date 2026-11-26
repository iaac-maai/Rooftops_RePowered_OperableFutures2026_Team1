"""Public, allowlisted read-only views of repository evidence (stdlib only).

No model loading, inference, simulation, arbitrary paths or raw report serving.
Missing/invalid sources remain pending; unknown quantities are null, never zero.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ('conservative', 'base', 'optimistic')
ASSESSMENTS = ('retrospective', 'additional')
ROOF = 'datasets/processed/roof_capacity/A160'
REPORT = 'reports/roof_capacity/A160'
SOURCES = {
    'buildings': 'datasets/inputs/case_study_candidates.csv',
    'roof_settings': 'config/a160_assessments.json',
    'roof_readiness': f'{REPORT}/readiness.json',
    'reference': f'{REPORT}/retrospective_validation.csv',
    'reference_separation': f'{REPORT}/reference_separation.json',
    'annotation': 'datasets/inputs/roof_capacity/A160_observed_annotation.json',
    'metrics': 'reports/simulation_surrogate/model_metrics.csv',
    'model_readiness': 'reports/simulation_surrogate/readiness.json',
    'model_manifest': 'pipeline/models/office_surrogate_manifest.json',
    'split_manifest': 'reports/simulation_surrogate/split_manifest.json',
    'bdg2': 'reports/demand_model/readiness.json',
    'impact': 'config/impact_assumptions.json',
    'footprint': 'datasets/inputs/roof_capacity/A160_footprint.geojson',
    'observed': 'datasets/inputs/roof_capacity/A160_observed_panel_coverage.geojson',
    'existing_pv_record': 'config/a160_existing_pv.json',
    'pvgis_hypothetical_report': 'reports/pvgis/A160/hypothetical_acquisition.json',
    'pvgis_hypothetical_settings': 'config/pvgis_hypothetical.json',
}
for assessment in ASSESSMENTS:
    SOURCES[assessment] = f'{ROOF}/{assessment}/roof_capacity_scenarios.csv'
    for scenario in SCENARIOS:
        for layer in ('eligible', 'panels'):
            SOURCES[f'{assessment}_{scenario}_{layer}'] = f'{ROOF}/{assessment}/{scenario}_{layer}.geojson'

PUBLIC_URLS = {
    'a160': 'https://www.batlleiroig.com/en/projects/oficines-almogavers-160-a-barcelona/',
    'icgc': 'https://geoserveis.icgc.cat/servei/catalunya/orto-territorial/wms?SERVICE=WMS&REQUEST=GetCapabilities',
    'lidar': 'https://datacloud.icgc.cat/datacloud/lidar-territorial/vigent/laz_unzip/full10km4358/lidar-territorial-full1km432583.laz',
    'municipal': 'https://coneixement-eu.bcn.cat/mapaEnergia/viewer.html',
    'pvgis': 'https://re.jrc.ec.europa.eu/pvg_tools/en/',
    'energyplus': 'https://energyplus.net/',
    'bdg2': 'https://doi.org/10.1038/s41597-020-00712-x',
}


class SourceUnavailable(ValueError):
    pass


def safe_text(value):
    value = str(value or '')
    if re.search(r'[A-Za-z]:[\\/]|/(?:Users|home|tmp)/|\\\\', value):
        return 'Source detail withheld: local path'
    return value


def safe_url(value):
    try:
        parsed = urlsplit(str(value or ''))
    except ValueError:
        return None
    return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else None


def number(value, integer=False):
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid numeric source value') from None
    if not math.isfinite(result) or result < 0 or (integer and not result.is_integer()):
        raise SourceUnavailable('Invalid numeric source value')
    return int(result) if integer else result


def pending(message, missing=()):
    return {'state': 'pending', 'evidence_state': 'MISSING_SOURCE_INPUT',
            'message': message, 'missing_inputs': list(missing), 'results': None}


class RepositoryData:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()

    def path(self, key):
        if key not in SOURCES:
            raise ValueError('Unknown source key')
        path = (self.root / SOURCES[key]).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise SourceUnavailable(f'Source unavailable: {SOURCES[key]}')
        return path

    def read(self, key):
        path = self.path(key)
        try:
            if path.suffix == '.csv':
                with path.open(encoding='utf-8-sig', newline='') as file:
                    return list(csv.DictReader(file))
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise SourceUnavailable(f'Source unreadable: {SOURCES[key]}') from None

    def provenance(self, *keys):
        result = []
        for key in keys:
            path = self.path(key)
            result.append({'repository_path': SOURCES[key], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'file_updated_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
        return result

    def buildings(self):
        try:
            rows = self.read('buildings')
            if not rows or len({row['building_id'] for row in rows}) != len(rows):
                raise SourceUnavailable('Candidate inventory is empty or has duplicate IDs')
            if any(row['is_host'].lower() not in ('true','false') for row in rows) or sum(row['is_host'].lower()=='true' for row in rows)!=1:
                raise SourceUnavailable('Candidate inventory must identify exactly one host')
            settings = self.read('roof_settings')
            output = []
            for row in rows:
                host = row['is_host'].lower() == 'true'
                output.append({key: safe_text(row.get(key)) for key in ('building_id', 'building_name', 'address', 'building_use', 'geometry_status')})
                output[-1].update(is_host=host, source_url=safe_url(row.get('source_url')),
                    evidence_state='AVAILABLE_REPOSITORY_RESULT', participation_verified=False,
                    existing_pv_status='visually_confirmed_specifications_unverified' if row['building_id'] == settings['building_id'] else safe_text(row['existing_pv_status']),
                    actual_hourly_meter_available=False)
            return {'state':'available', 'buildings':output, 'inventory_role':'public_candidates_not_approved_participants',
                    'provenance':self.provenance('buildings', 'roof_settings')}
        except (SourceUnavailable, KeyError) as exc:
            return pending(safe_text(exc), ['Public candidate inventory'])

    def scenarios(self):
        groups = {}
        for assessment in ASSESSMENTS:
            try:
                rows = self.read(assessment)
                if len(rows) != 3 or {row['scenario'] for row in rows} != set(SCENARIOS):
                    raise SourceUnavailable('Scenario source must contain exactly three known scenarios')
                parsed = []
                for row in rows:
                    if row['assessment'] != assessment or row['building_id'] != 'A160':
                        raise SourceUnavailable('Unexpected roof assessment or building identity')
                    values = {key:number(row[key], integer=key in ('panel_count',)) for key in (
                        'usable_area_m2','panel_projected_area_m2','panel_count','assumed_module_wp',
                        'estimated_kwp','tilt_degrees','azimuth_degrees_from_north')}
                    if not math.isclose(values['estimated_kwp'], values['panel_count'] * values['assumed_module_wp'] / 1000, abs_tol=1e-6):
                        raise SourceUnavailable('Capacity and module-count source values disagree')
                    parsed.append({**values, 'scenario':row['scenario'], 'building_id':'A160', 'assessment':assessment,
                        'confidence':safe_text(row['confidence']), 'data_origin':safe_text(row['data_origin']),
                        'model_version':safe_text(row['model_version']), 'lidar_survey_date':safe_text(row['lidar_survey_date']),
                        'evidence_state':'PROVISIONAL_ESTIMATE', 'unit':'kWp', 'source_url':PUBLIC_URLS['lidar'],
                        'generation_role':'counterfactual_validation_only' if assessment == 'retrospective' else 'incremental_proposed'})
                groups[assessment] = {'state':'available', 'scenarios':parsed, 'provenance':self.provenance(assessment)}
            except (SourceUnavailable, KeyError) as exc:
                groups[assessment] = pending(safe_text(exc), [f'{assessment} scenario CSV'])
        try:
            settings = self.read('roof_settings')
            assumptions = {key: settings['module'].get(key) for key in ('long_m','short_m','wp','tilt_degrees','azimuth_degrees_from_north')}
            scenarios = settings['scenarios']
        except (SourceUnavailable, KeyError):
            assumptions, scenarios = None, None
        return {'state':'available' if all(group['state']=='available' for group in groups.values()) else 'partial',
            'building_id':'A160', 'assessments':groups, 'installed_capacity_kwp':None,
            'installed_capacity_verified':False, 'assumptions':assumptions, 'scenario_parameters':scenarios,
            'confidence_or_limitations':'Low-confidence geometric screening. Counterfactual, additional and existing PV are separate. No structural/access/fire certification.',
            'units':{'estimated_kwp':'kWp','usable_area_m2':'m²','tilt_degrees':'degrees','azimuth_degrees_from_north':'degrees clockwise from north'}}

    def reference(self):
        try:
            settings = self.read('roof_settings')
            readiness = self.read('roof_readiness')
            metrics = self.read('reference')
            separation = self.read('reference_separation')
            annotation = self.read('annotation')
            return {'state':'available', 'data_origin':'OBSERVED_IMAGE_INTERPRETATION',
                'observed_projected_panel_coverage_m2':number(annotation['observed_projected_panel_coverage_m2']),
                'area_sensitivity_m2':{key:number(value) for key,value in annotation['area_sensitivity_m2'].items()},
                'observed_module_count':None, 'installed_capacity_kwp':None,
                'metrics':[{key: safe_text(row[key]) if key=='scenario' else number(row[key]) for key in (
                    'scenario','panel_coverage_iou','observed_panel_area_inside_predicted_eligible_fraction')} for row in metrics],
                'source_dates':{'lidar_acquired':settings['lidar_acquisition_date'], 'final_ortho_captured':settings['orthophoto_date'],
                    'provisional_image_captured':readiness['newest_public_provisional_capture_date']},
                'native_gsd_m':number(settings['orthophoto_native_gsd_m']),
                'observed_mask_used_in_retrospective_predictor':separation['observed_mask_used_in_retrospective_predictor'],
                'pre_installation_source_independence':separation['pre_installation_source_independence'],
                'limitations':['LiDAR already includes installed PV; no clean pre-installation geometry.',
                    'Image interpretation is a spatial reference, not installed kWp or verified maximum potential.',
                    '2026 provisional image is visual context; registration for label transfer is unverified.'],
                'municipal_comparison':{key: readiness['municipal_comparison'][key] for key in (
                    'municipal_source_date','municipal_potential_kw_source','municipal_usable_area_m2',
                    'current_roof_validation_eligible','source_url')},
                'provenance':self.provenance('reference','annotation','roof_settings','reference_separation','roof_readiness')}
        except (SourceUnavailable, KeyError) as exc:
            return pending(safe_text(exc), ['Reference annotation and metrics'])

    def model(self):
        try:
            manifest = self.read('model_manifest')
            readiness = self.read('model_readiness')
            split = self.read('split_manifest')['splits']
            metrics = self.read('metrics')
            parsed = []
            for row in metrics:
                parsed.append({'model':safe_text(row['model']), 'split':safe_text(row['split']),
                    **{key:number(row[key], integer=key in ('rows','configurations')) for key in (
                        'rows','configurations','mae_kwh','rmse_kwh','nmae_mean_simulated_load')}})
            return {'state':'available', 'evidence_state':'VALIDATED_SIMULATION_DOMAIN',
                'training_origin':'SIMULATED_PHYSICS', 'real_building_accuracy_validated':False,
                'model_version':manifest['created_utc'], 'metrics':parsed,
                'configuration_count':number(readiness['configuration_count'], integer=True),
                'splits':{name:len(ids) for name,ids in split.items()},
                'floor_area_m2':number(manifest['floor_area_m2']), 'archetype':safe_text(readiness['archetype']),
                'validation_gate_passed':readiness['validation_gate_passed'],
                'test_beats_baselines':readiness['test_beats_baselines'],
                'real_world_transfer_state':'UNVERIFIED_REAL_WORLD_TRANSFER',
                'limitations':safe_text(manifest['limitations']),
                'metric_units':{'mae_kwh':'kWh per hourly interval', 'rmse_kwh':'kWh per hourly interval'},
                'provenance':self.provenance('metrics','model_manifest','model_readiness','split_manifest')}
        except (SourceUnavailable, KeyError) as exc:
            return pending(safe_text(exc), ['Office-surrogate evaluation reports'])

    def map(self, assessment, scenario):
        if assessment not in ASSESSMENTS or scenario not in SCENARIOS:
            raise ValueError('Unknown assessment or scenario')
        try:
            layers = {}
            for role,key in (('footprint','footprint'),('eligible',f'{assessment}_{scenario}_eligible'),('panels',f'{assessment}_{scenario}_panels')):
                source = self.read(key)
                if source.get('type') != 'FeatureCollection':
                    raise SourceUnavailable('Expected a GeoJSON FeatureCollection')
                # Drop raw feature properties, which can contain local paths or unreviewed metadata.
                layers[role] = {'type':'FeatureCollection', 'features':[{'type':'Feature','geometry':feature['geometry'],
                    'properties':{'layer':role,'assessment':assessment,'scenario':scenario}}
                    for feature in source['features'] if feature.get('geometry')]}
            return {'state':'available', 'assessment':assessment, 'scenario':scenario, 'crs':'EPSG:4326',
                'layers':layers, 'observed_reference_included':False,
                'display_note':'Real WGS84 geometry; local metric display projection. No imagery basemap or legal boundary certification.'}
        except (SourceUnavailable, KeyError) as exc:
            return pending(safe_text(exc), ['Allowlisted roof GeoJSON layers'])

    def stage(self, name):
        if name == 'pvgis':
            from .solar import status
            return status(self)
        if name == 'demand':
            return {**pending('The office-reference model is available; A160/mixed-use demand is not validated.',
                ['A160 geometry/HVAC and operation domain', 'Education, residential and hospitality physics archetypes',
                 'Aligned hourly weather and calendar convention']), 'actual_meter_available':False, 'hourly_demand':None}
        if name == 'sharing':
            return {**pending('No case-study allocation comparison has been evaluated.',
                ['Aligned verified-role PV and site-appropriate reference demands',
                 'Pre-agreed coefficients evaluated against independent loads']),
                'annual_solar_used_kwh':None, 'avoided_grid_imports_kwh':None, 'participant_benefits':None}
        if name == 'impact':
            return {**pending('Impact results await evaluated balances and sourced assumptions.',
                ['Evaluated energy balances', 'Dated tariffs, emissions factors, capex/O&M', 'Defined benefit-sharing proxy']),
                'emissions_avoided_kgco2e':None, 'annual_savings_eur':None, 'payback_years':None}
        raise ValueError('Unknown stage')

    def evidence(self):
        reference = self.reference()
        dates = reference.get('source_dates', {})
        municipal_date = reference.get('municipal_comparison', {}).get('municipal_source_date')
        records = [
            {'id':'roof', 'title':'A160 rooftop scenarios', 'state':'PROVISIONAL_ESTIMATE',
             'source_url':PUBLIC_URLS['lidar'], 'source_date':dates.get('lidar_acquired'), 'unit':'kWp',
             'repository_paths':[SOURCES['retrospective'],SOURCES['additional']],
             'limitations':'Post-installation LiDAR; assumed new modules. Not existing installed kWp or certified maximum.'},
            {'id':'reference', 'title':'Independent image-reference coverage', 'state':'AVAILABLE_REPOSITORY_RESULT',
             'source_url':PUBLIC_URLS['icgc'], 'source_date':dates.get('final_ortho_captured'), 'unit':'m² projected coverage',
             'repository_paths':[SOURCES['reference'],SOURCES['annotation']],
             'limitations':'Native GSD 0.25 m. Module count/specifications and installed kWp are unknown.'},
            {'id':'model', 'title':'Office EnergyPlus–XGBoost evaluation', 'state':'VALIDATED_SIMULATION_DOMAIN',
             'source_url':PUBLIC_URLS['energyplus'], 'source_date':None, 'unit':'kWh per hourly interval',
             'repository_paths':[SOURCES['metrics'],SOURCES['model_readiness']],
             'limitations':'Simulated reference loads, one office geometry. No verified real-world A160 transfer.'},
            {'id':'municipal', 'title':'Municipal solar map: legacy comparison', 'state':'AVAILABLE_REPOSITORY_RESULT',
             'source_url':PUBLIC_URLS['municipal'], 'source_date':municipal_date, 'unit':'kW modeled potential',
             'repository_paths':[f'{ROOF}/municipal_map_comparison.csv'],
             'limitations':'Record timestamp predates modern A160. Not current as-built capacity; never additive.'},
            {'id':'bdg2', 'title':'BDG2 negative benchmark results', 'state':'AVAILABLE_REPOSITORY_RESULT',
             'source_url':PUBLIC_URLS['bdg2'], 'source_date':None, 'unit':'kWh error',
             'repository_paths':['reports/demand_model/MODEL_CARD.md','reports/demand_model/experiments/initial70/'],
             'limitations':'Both measured-data XGBoost experiments failed the primary baseline improvement gate.'},
            {'id':'illustration', 'title':'Building rhythm explorer', 'state':'ILLUSTRATIVE_NOT_SIMULATED',
             'source_url':None, 'source_date':None, 'unit':'normalized activity (0–1)', 'repository_paths':['ui/profiles.js'],
             'limitations':'Educational schedule hypotheses. Not observed meters, simulator output or hourly kWh.'}]
        return {'state':'available', 'records':records, 'clock':{'timestamp_basis':'timestamp_utc', 'display_timezone':'Europe/Madrid'},
            'data_policy':'Public research evidence only. No private meters, raw caches, arbitrary paths or account credentials.'}

    def status(self):
        try:
            commit = subprocess.run(['git','rev-parse','HEAD'], cwd=self.root, capture_output=True, text=True,
                timeout=3, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            commit = None
        times = []
        for key in ('buildings','retrospective','additional','reference','metrics','existing_pv_record','pvgis_hypothetical_report'):
            try:
                times.append(self.path(key).stat().st_mtime)
            except SourceUnavailable:
                pass
        return {'schema_version':'1.1', 'commit':commit, 'version':'a160-readonly-ui-2-pvgis',
            'last_updated_utc':datetime.fromtimestamp(max(times),timezone.utc).isoformat() if times else None,
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'display_timezone':'Europe/Madrid', 'mode':'read_only_research_dashboard',
            'stages':{'roof':'provisional_screening' if self.scenarios()['state']=='available' else 'source_pending',
                'office_model':'validated_simulation_domain' if self.model()['state']=='available' else 'source_pending',
                'pvgis_hypothetical':'available' if self.stage('pvgis').get('hypothetical_state')=='available' else 'source_pending',
                **{name:'pending' for name in ('pvgis','demand','sharing','impact')}},
            'private_meter_data_served':False, 'live_control':False}

    def dashboard(self):
        from .existing_pv import assess
        return {'status':self.status(), 'buildings':self.buildings(), 'roof':self.scenarios(),'existing_pv':assess(self),
            'reference':self.reference(), 'model':self.model(), 'evidence':self.evidence(),
            **{stage:self.stage(stage) for stage in ('pvgis','demand','sharing','impact')}}
