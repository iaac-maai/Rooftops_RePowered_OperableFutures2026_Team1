"""Offline, rooftop-only A160 milestone; never trains or invokes demand models."""
import json

import pandas as pd
from pyproj import Transformer

from pipeline.common import InputError, ROOT, now, require_file, resolve, sha256, write_json
from .adapter import load_geometry
from .assessments import additional, load_settings, predict_retrospective, validate_retrospective


def check_frozen_prediction(settings):
    """Refuse stale geometry/parameters before comparing it against a reference."""
    root = resolve(settings['output_dir']) / 'retrospective'
    manifest = json.loads(require_file(root / 'run_manifest.json').read_text())
    for name in ('structural', 'module', 'scenarios'):
        if manifest['parameters'][name] != settings[name]:
            raise InputError(f'Retrospective {name} changed; explicitly rebuild predictions before annotation.')
    for name in ('footprint_path', 'points_path'):
        if manifest['source_hashes'][name] != sha256(require_file(resolve(settings[name]))):
            raise InputError(f'Retrospective source {name} changed; explicitly rebuild predictions.')
    if manifest['scenario_csv_sha256'] != sha256(require_file(root / 'roof_capacity_scenarios.csv')):
        raise InputError('Retrospective scenario CSV changed since prediction.')
    return manifest


def pvgis_records(settings, tables):
    """Keep counterfactual validation, incremental proposals and existing PV separate."""
    footprint = load_geometry(settings['footprint_path'], 'EPSG:4326')
    lon, lat = Transformer.from_crs(25831, 4326, always_xy=True).transform(footprint.centroid.x, footprint.centroid.y)
    records = []
    for assessment, table in tables.items():
        for row in table.to_dict('records'):
            azimuth = float(row['azimuth_degrees_from_north'])
            capacity = float(row['estimated_kwp'])
            records.append({
                'roof_id': f'A160_{assessment}_{row["scenario"]}', 'building_id': 'A160',
                'assessment': assessment, 'scenario': row['scenario'],
                'generation_role': 'counterfactual_validation_only' if assessment == 'retrospective' else 'incremental_proposed',
                'capacity_kwp': capacity, 'tilt': float(row['tilt_degrees']),
                'azimuth_degrees_from_north': azimuth, 'azimuth': ((azimuth - 180 + 180) % 360) - 180,
                'azimuth_convention': 'PVGIS: south=0, east=-90, west=90',
                'latitude': lat, 'longitude': lon,
                'weather_year': settings['pvgis']['weather_year'], 'loss_percent': settings['pvgis']['loss_percent'],
                'timestamp_basis': 'UTC', 'power_unit': 'W',
                'source_url': 'https://re.jrc.ec.europa.eu/pvg_tools/en/',
                'capacity_origin': 'ESTIMATED_ROOF', 'existing_installed_capacity_verified': False,
                'confidence': row['confidence'], 'positive_capacity': capacity > 0,
                'energy_sharing_eligible': False,
                'next_action': 'Zero geometric capacity: skip simulation' if capacity == 0 else 'Choose PVGIS weather period/losses; keep role and scenario separate; verify design before real-world use',
                'accounting_rule': 'Select one scenario within one assessment. Retrospective generation cannot represent existing PV or be added to incremental generation. Existing PV needs separately verified capacity and yield.'})
    records.append({'roof_id': 'A160_existing', 'building_id': 'A160', 'assessment': 'observed_existing',
        'generation_role': 'existing_unverified', 'capacity_kwp': settings['existing_installation']['installed_capacity_kwp'],
        'tilt': None, 'azimuth': None, 'positive_capacity': False, 'energy_sharing_eligible': False,
        'next_action': 'Obtain installed module specifications, count, orientations/tilts or a verified installation record; do not infer installed kWp from illustrative new modules.'})
    return records


def export_pvgis(settings, tables):
    out = ROOT / 'datasets/inputs/roof_capacity/pvgis'
    out.mkdir(parents=True, exist_ok=True)
    records = pvgis_records(settings, tables)
    for record in records:
        write_json(out / f'{record["roof_id"]}.json', record)
    pd.DataFrame(records).to_csv(out / 'A160_pvgis_inputs.csv', index=False)
    return records


def source_register(settings):
    paths = {name: value for name, value in settings.items()
             if isinstance(value, str) and (name.endswith('_path') or name in (
                 'observed_panel_mask', 'observed_array_envelopes', 'observed_annotation_metadata',
                 'current_access_exclusions', 'current_high_roof_boundary',
                 'lidar_acquisition_report', 'orthophoto_bounds_report'))}
    paths.update(protocol='config/a160_assessments.json',
        annotation_protocol='config/a160_pv_reference_annotation.json',
        source_laz='datasets/raw/roof_capacity/A160/lidar/lidar-territorial-full1km432583.laz',
        newest_provisional_image='datasets/raw/roof_capacity/A160/source_probes/A160_provisional_2026.png',
        municipal_polygons='datasets/raw/roof_capacity/A160/source_probes/municipal_roof_polygons.geojson',
        cadastre_property_response='datasets/raw/roof_capacity/A160/source_probes/catastro_parcel_details.json')
    files = []
    for role, name in paths.items():
        path = require_file(resolve(name))
        files.append({'role': role, 'path': str(path.relative_to(ROOT)),
                      'bytes': path.stat().st_size, 'sha256': sha256(path)})
    report = ROOT / 'reports/roof_capacity/A160'
    write_json(report / 'source_register.json', {'created_utc': now(), 'building_id': 'A160',
        'cadastral_reference': settings['cadastral_reference'], 'files': files,
        'request_manifests': ['rooftop_sources.json', 'tile_metadata_sources.json',
            'latest_imagery_check.json', 'lidar_acquisition.json', 'cadastre_candidates.json'],
        'source_roles': {'retrospective_inputs': ['footprint_path', 'points_path', 'structural/module/scenarios parameters'],
            'reference_only': ['observed_panel_mask'],
            'additional_only': ['observed_array_envelopes', 'current_access_exclusions', 'current_high_roof_boundary'],
            'latest_provisional': 'Visual context only; not registered reference/predictor labels'},
        'existing_installation': settings['existing_installation']})


def run(settings_path='config/a160_assessments.json', rebuild=False):
    settings = load_settings(settings_path)
    root = resolve(settings['output_dir'])
    manifest = root / 'retrospective/run_manifest.json'
    if rebuild or not manifest.exists():
        predict_retrospective(settings_path)
    check_frozen_prediction(settings)
    # Predict/freeze BEFORE digitizing or scoring the observed reference.
    from .reference import annotate
    from .figures import render, render_latest_context
    from .municipal_comparison import compare
    annotate(settings_path)
    incremental = additional(settings_path)
    validation = validate_retrospective(settings_path)
    retrospective = pd.read_csv(root / 'retrospective/roof_capacity_scenarios.csv')
    records = export_pvgis(settings, {'retrospective': retrospective, 'additional': incremental})
    city = compare('config/roof_capacity.json',
        'datasets/raw/roof_capacity/A160/source_probes/municipal_roof_polygons.geojson',
        '2015-03-12', 'https://coneixement-eu.bcn.cat/mapaEnergia/viewer.html',
        root / 'municipal_map_comparison.csv')
    image = render(settings_path)
    render_latest_context(settings_path)
    source_register(settings)
    report = ROOT / 'reports/roof_capacity/A160'
    write_json(report / 'readiness.json', {
        'created_utc': now(), 'status': 'completed_provisional_rooftop_screening',
        'scope': 'A160 dual rooftop assessment only', 'building_id': 'A160',
        'confidence': 'low', 'installation_design_ready': False, 'energy_sharing_ready': False,
        'retrospective_observed_mask_used': False, 'pre_installation_lidar': False,
        'existing_capacity_verified': False, 'demand_model_retrained': False,
        'quantitative_reference_capture_date': '2025-06-18',
        'newest_public_provisional_capture_date': '2026-03-16',
        'provisional_imagery_use': 'Visual context only; differing roof alignment and unverified native GSD prevent transferring pixel labels without registration',
        'additional_capacity_kwp': dict(zip(incremental.scenario, incremental.estimated_kwp)),
        'retrospective_capacity_kwp': dict(zip(retrospective.scenario, retrospective.estimated_kwp)),
        'municipal_comparison': city, 'figure': str(image.relative_to(ROOT)),
        'limitations': ['Post-installation LiDAR; shallow relief approximation is not verified bare-roof geometry',
            'Only dominant upper roof assessed; omitted terraces/service roofs are not certified unusable',
            'Manual image interpretation and assumed access reserves; no survey/as-built design verification',
            'Scenario spread is a parameter sensitivity range, not a statistical confidence interval',
            'Municipal records predate modern host; no parcel-level current installation specification',
            'No structural, safety, electrical or existing installation capacity verification'],
        'required_for_next_stage': ['Verify installed PV count/specifications and remaining roof access/plant clearances',
            'Choose PVGIS weather period/system losses before yield simulation',
            'Use a building demand simulation domain appropriate to A160 before cluster accounting']})
    print(validation[['scenario', 'panel_coverage_iou']].to_string(index=False))
    print(f'Rooftop milestone complete: {image.relative_to(ROOT)}; {len(records)} separate PVGIS records.')
    return 0
