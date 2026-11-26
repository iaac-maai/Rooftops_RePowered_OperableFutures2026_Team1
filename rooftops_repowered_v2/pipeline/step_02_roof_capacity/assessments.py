"""Separate retrospective roof prediction, observed PV reference and new capacity.

The retrospective predictor accepts geometry/points/parameters only. It cannot
read an observed PV mask. This enforces computational label separation, not a
claim of pre-installation LiDAR: A160's 2022 survey already contains the PV.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from pipeline.common import InputError, ROOT, now, require_file, resolve, sha256, write_json
from .adapter import load_geometry, preview_svg, write_geojson
from .layout import lay_out
from .lidar_roof import read_roof_lidar, usable_mask


def load_settings(path='config/a160_assessments.json'):
    return json.loads(require_file(resolve(path)).read_text(encoding='utf-8'))


def structural_geometry(footprint, points, parameters):
    """Panel-mask-agnostic dominant structural plane and high-relief obstacles."""
    roof = read_roof_lidar(footprint, points, res=parameters['grid_resolution_m'],
                           height_tol=parameters['v1_plane_growing_height_tolerance_m'])
    if roof.summary['lidar_coverage'] < parameters['minimum_source_coverage']:
        raise InputError('Insufficient source coverage for a structural approximation.')
    ids, counts = np.unique(roof.surface_id[roof.surface_id >= 0], return_counts=True)
    if not len(ids):
        raise InputError('No dominant flat roof plane; do not invent roof capacity.')
    principal = ids[np.argmax(counts)]
    seed = roof.surface_id == principal
    rr, cc = np.indices(seed.shape)
    design = np.column_stack([cc[seed] * roof.grid.res, rr[seed] * roof.grid.res, np.ones(seed.sum())])
    coefficients, *_ = np.linalg.lstsq(design, roof.dsm[seed], rcond=None)
    plane = coefficients[0] * cc * roof.grid.res + coefficients[1] * rr * roof.grid.res + coefficients[2]
    residual = roof.dsm - plane
    has = np.isfinite(roof.dsm)
    band = parameters['low_relief_structural_band_m']
    candidate = roof.roof & has & (np.abs(residual) <= band)
    obstacles = roof.roof & has & (residual > band)
    info = {**roof.summary, 'principal_surface_id': int(principal),
            'plane_coefficients': coefficients.tolist(), 'low_relief_band_m': band,
            'candidate_structural_area_m2': float(candidate.sum() * roof.grid.cell_area),
            'observed_pv_mask_used': False,
            'method': 'V1 dominant-plane structural approximation with fixed low-relief band; not bare-roof truth'}
    return roof.grid, roof.roof, candidate, obstacles, info


def pack(eligible, footprint, module):
    return lay_out(eligible, footprint, tilt_deg=module['tilt_degrees'],
                    azimuth_deg=module['azimuth_degrees_from_north'], panel_long_m=module['long_m'],
                    panel_short_m=module['short_m'], module_wp=module['wp'], gap_m=module['panel_gap_m'],
                    winter_elevation_deg=module['winter_design_elevation_degrees'], shift_step_m=module['grid_shift_step_m'])


def save_assessment(root, assessment, footprint, eligible_by_scenario, obstacles, settings, source_hashes):
    out = root / assessment
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario, eligible in eligible_by_scenario.items():
        layout = pack(eligible, footprint, settings['module'])
        panel_union = unary_union(layout.panels) if layout.panels else Polygon()
        row = {'building_id': settings['building_id'], 'assessment': assessment, 'scenario': scenario,
               'usable_area_m2': float(eligible.area), 'panel_projected_area_m2': float(panel_union.area),
               'panel_count': layout.count, 'assumed_module_wp': layout.module_wp, 'estimated_kwp': layout.kwp,
               'tilt_degrees': layout.tilt_deg, 'azimuth_degrees_from_north': layout.azimuth_deg,
               'confidence': 'low_provisional_geometry_screening', 'data_origin': 'ESTIMATED_ROOF',
               'lidar_survey_date': settings['lidar_acquisition_date'],
               'model_version': 'v1_a160_dominant_plane_v2_dual_1',
               'installed_capacity_verified': False, 'certified_maximum_capacity': False}
        rows.append(row)
        props = {'building_id': settings['building_id'], 'assessment': assessment, 'scenario': scenario,
                 'data_origin': 'ESTIMATED_ROOF', 'not_existing_installed_capacity': True}
        write_geojson(out / f'{scenario}_eligible.geojson', [eligible], [props])
        write_geojson(out / f'{scenario}_panels.geojson', layout.panels, [props] * layout.count)
        preview = {'eligible': eligible, 'obstacles': obstacles, 'panels': layout.panels}
        preview_settings = {**settings, 'review': {'orthophoto_path': settings['orthophoto_path'],
            'orthophoto_bbox_25831': json.loads(require_file(resolve(settings['orthophoto_bounds_report'])).read_text())['ortho_bbox_25831']}}
        # Image is a visualization background only, applied AFTER the polygons
        # and panel packing have been computed; never a predictor feature.
        preview_svg(out / f'{scenario}_qa.svg', footprint, preview, preview_settings)
    table = pd.DataFrame(rows)
    table.to_csv(out / 'roof_capacity_scenarios.csv', index=False)
    write_json(out / 'run_manifest.json', {'created_utc': now(), 'assessment': assessment,
        'parameters': {'structural': settings['structural'], 'module': settings['module'], 'scenarios': settings['scenarios']},
        'source_hashes': source_hashes, 'scenario_csv_sha256': sha256(out / 'roof_capacity_scenarios.csv'),
        'lidar_contains_existing_installation': True,
        'limitations': 'Post-installation 2022 LiDAR and 2025 image annotation. Structural low-relief approximation can suppress small equipment and does not recover verified hidden bare-roof geometry. Not an independent pre-installation study or a maximum-capacity certification.'})
    return table


def predict_retrospective(settings_path='config/a160_assessments.json'):
    settings = load_settings(settings_path)
    footprint = load_geometry(settings['footprint_path'], 'EPSG:4326')
    source = np.load(require_file(resolve(settings['points_path'])))['points']
    points = source[np.isin(source[:, 3], [6, 77]), :3]
    # The structural function and packing receive no imagery or observed-mask data.
    grid, roof, candidate, obstacles, info = structural_geometry(footprint, points, settings['structural'])
    geometries = {}
    obstacle_geom = grid.cells_to_polygon(obstacles)
    obstacle_geom = Polygon() if obstacle_geom is None else obstacle_geom
    for name, parameters in settings['scenarios'].items():
        mask = usable_mask(roof, candidate, obstacles, grid.res,
                           edge_setback=parameters['edge_setback_m'], clearance=parameters['obstacle_clearance_m'])
        eligible = grid.cells_to_polygon(mask)
        geometries[name] = Polygon() if eligible is None else eligible.intersection(footprint)
    root = resolve(settings['output_dir'])
    hashes = {key: sha256(require_file(resolve(settings[key]))) for key in ('footprint_path', 'points_path')}
    hashes['structural_protocol'] = sha256(require_file(resolve(settings_path)))
    table = save_assessment(root, 'retrospective', footprint, geometries, obstacle_geom, settings, hashes)
    write_json(root / 'retrospective/structural_reading.json', info)
    write_geojson(root / 'retrospective/structural_obstacles.geojson', [obstacle_geom], [{'data_origin': 'ESTIMATED_ROOF'}])
    print(table.to_string(index=False), flush=True)
    return table


def additional(settings_path='config/a160_assessments.json'):
    settings = load_settings(settings_path)
    root = resolve(settings['output_dir'])
    footprint = load_geometry(settings['footprint_path'], 'EPSG:4326')
    # Existing array envelopes, not only dark module pixels, are occupied
    # infrastructure: include their internal aisles and service spacing.
    occupied = load_geometry(settings['observed_array_envelopes'], 'EPSG:4326')
    access = load_geometry(settings['current_access_exclusions'], 'EPSG:4326', True)
    current_boundary = load_geometry(settings['current_high_roof_boundary'], 'EPSG:4326')
    structural_obstacles = load_geometry(root / 'retrospective/structural_obstacles.geojson', 'EPSG:4326', True)
    geometries = {}
    for name, parameters in settings['scenarios'].items():
        candidate = load_geometry(root / f'retrospective/{name}_eligible.geojson', 'EPSG:4326', True)
        geometries[name] = candidate.intersection(current_boundary).difference(occupied.buffer(parameters['obstacle_clearance_m'])).difference(access)
    hashes = {'occupied_arrays': sha256(resolve(settings['observed_array_envelopes'])),
              'current_access_exclusions': sha256(resolve(settings['current_access_exclusions'])),
              'current_high_roof_boundary': sha256(resolve(settings['current_high_roof_boundary'])),
              'retrospective_manifest': sha256(root / 'retrospective/run_manifest.json')}
    table = save_assessment(root, 'additional', footprint, geometries,
                            unary_union([structural_obstacles, occupied, access]), settings, hashes)
    print(table.to_string(index=False), flush=True)
    return table


def validate_retrospective(settings_path='config/a160_assessments.json'):
    settings = load_settings(settings_path)
    root = resolve(settings['output_dir'])
    observed = load_geometry(settings['observed_panel_mask'], 'EPSG:4326')
    annotation = json.loads(require_file(resolve(settings['observed_annotation_metadata'])).read_text())
    rows = []
    for name in settings['scenarios']:
        predicted = load_geometry(root / f'retrospective/{name}_panels.geojson', 'EPSG:4326', True)
        eligible = load_geometry(root / f'retrospective/{name}_eligible.geojson', 'EPSG:4326', True)
        intersection = predicted.intersection(observed).area
        union = predicted.union(observed).area
        rows.append({'building_id': 'A160', 'scenario': name,
                     'predicted_projected_panel_area_m2': predicted.area,
                     'observed_image_panel_coverage_m2': observed.area,
                     'predicted_to_observed_projected_area_ratio': predicted.area / observed.area,
                     'projected_area_difference_percent': 100 * (predicted.area - observed.area) / observed.area,
                     'panel_coverage_iou': intersection / union if union else None,
                     'predicted_panel_area_overlapping_observed_fraction': intersection / predicted.area if predicted.area else None,
                     'observed_panel_area_inside_predicted_eligible_fraction': observed.intersection(eligible).area / observed.area,
                     'observed_panel_count': annotation.get('reliable_panel_count'),
                     'observed_installed_kwp': settings['existing_installation']['installed_capacity_kwp'],
                     'reference_origin': 'OBSERVED_IMAGE_INTERPRETATION',
                     'reference_native_gsd_m': settings['orthophoto_native_gsd_m'],
                     'validation_scope': 'existing-installation spatial agreement; not maximum capacity or pre-installation accuracy',
                     'source_contamination_risk': '2022 LiDAR already includes the existing installation'})
    out = ROOT / 'reports/roof_capacity/A160'
    table = pd.DataFrame(rows)
    table.to_csv(out / 'retrospective_validation.csv', index=False)
    write_json(out / 'reference_separation.json', {'created_utc': now(),
        'retrospective_frozen_manifest_sha256': sha256(root / 'retrospective/run_manifest.json'),
        'observed_annotation_sha256': sha256(resolve(settings['observed_panel_mask'])),
        'observed_mask_used_in_retrospective_predictor': False,
        'not_blinded_human_study': True,
        'pre_installation_source_independence': False,
        'ground_truth_limit': 'User-confirmed PV identity, image-interpreted projected coverage at 0.25m native GSD; no verified module count/Wp or installed kWp.'})
    return table


if __name__ == '__main__':
    predict_retrospective()
