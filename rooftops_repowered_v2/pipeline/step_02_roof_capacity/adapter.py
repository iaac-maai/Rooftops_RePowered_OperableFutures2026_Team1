"""Dated, reviewed roof masks -> V1 packing -> estimated kWp -> PVGIS settings.

All geometric operations use EPSG:25831 metres. Exported GeoJSON is WGS84.
No solar-energy yield or actual rooftop suitability is inferred here.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import base64
from html import escape
import json
from pathlib import Path

import laspy
import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union

from pipeline.common import InputError, ROOT, now, require_file, resolve, sha256, write_json
from .grid import Grid
from .layout import Layout, lay_out
from .lidar_roof import read_roof_lidar, roof_points

METRIC_CRS = CRS.from_epsg(25831)
GEO_CRS = CRS.from_epsg(4326)
REQUIRED_EXCLUSIONS = {'terraces', 'vegetation', 'pedestrian_access', 'equipment', 'fire_safety_paths', 'existing_pv'}


def completion_cutoff(settings):
    if settings.get('completion_date'):
        return date.fromisoformat(settings['completion_date'])
    # Completion month/day is unknown: a survey during the completion year is
    # ambiguous and must not be treated as evidence of the completed roof.
    return date(int(settings['completion_year']), 12, 31)


def validate_vintage(record, settings):
    try:
        start = date.fromisoformat(record['survey_start'])
        end = date.fromisoformat(record['survey_end'])
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError('Each tile needs documented survey_start/survey_end flight dates; LAS creation date is not acquisition evidence.') from exc
    if start > end or end > datetime.now(ZoneInfo('Europe/Madrid')).date():
        raise InputError('LiDAR acquisition dates are reversed or in the future.')
    if start <= completion_cutoff(settings):
        raise InputError(f'Stale or ambiguous LiDAR: {start}–{end}; must postdate documented completion. Use current plans/imagery if the modern roof is absent.')
    if not record.get('source_url') or not record.get('acquisition_evidence'):
        raise InputError('Each tile needs source_url and acquisition_evidence, not an inferred filename/header date.')
    if CRS.from_user_input(record.get('crs', '')) != METRIC_CRS or record.get('vertical_units') != 'm':
        raise InputError('LiDAR must explicitly declare EPSG:25831 and metre elevations.')
    return start, end


def load_geometry(path, declared_crs, allow_empty=False):
    data = json.loads(require_file(resolve(path)).read_text(encoding='utf-8-sig'))
    source_crs = CRS.from_user_input(declared_crs)
    if data.get('crs'):
        embedded = CRS.from_user_input(data['crs']['properties']['name'])
        if embedded != source_crs:
            raise InputError(f'Embedded and configured CRS differ for {path}.')
    features = data.get('features') if data.get('type') == 'FeatureCollection' else [data]
    polygons = []
    for feature in features:
        value = feature.get('geometry') if feature.get('type') == 'Feature' else feature
        if value is None:
            raise InputError(f'Null geometry in {path}.')
        geom = shape(value)
        if geom.is_empty:
            continue
        if geom.geom_type not in ('Polygon', 'MultiPolygon') or not geom.is_valid:
            raise InputError(f'Expected valid polygon geometry in {path}; no silent geometry repair.')
        converter = Transformer.from_crs(source_crs, METRIC_CRS, always_xy=True)
        polygons.append(shapely.transform(geom, converter.transform, interleaved=False))
    result = unary_union(polygons) if polygons else Polygon()
    if result.is_empty and not allow_empty:
        raise InputError(f'{path}: empty footprint.')
    if not result.is_empty:
        bounds = np.asarray(result.bounds)
        if not np.isfinite(bounds).all() or result.area > 100000:
            raise InputError(f'{path}: nonfinite or out-of-scope single-roof geometry/CRS.')
        # Reject accidentally labelling longitude/latitude numbers as UTM metres.
        if max(abs(bounds)) < 1000:
            raise InputError(f'{path}: coordinates look geographic but are declared projected.')
    return result


def write_geojson(path, geometries, properties):
    converter = Transformer.from_crs(METRIC_CRS, GEO_CRS, always_xy=True)
    features = [{'type': 'Feature', 'geometry': mapping(shapely.transform(geom, converter.transform, interleaved=False)),
                 'properties': props} for geom, props in zip(geometries, properties)
                if geom is not None and not geom.is_empty]
    write_json(path, {'type': 'FeatureCollection', 'features': features})


def validate_settings(settings):
    module = settings['module']
    for key in ('long_m', 'short_m', 'wp', 'grid_shift_step_m'):
        if not np.isfinite(module[key]) or module[key] <= 0:
            raise InputError(f'module.{key} must be finite and positive.')
    if not 0 <= module['tilt_degrees'] < 80 or not 0 < module['winter_design_elevation_degrees'] < 90:
        raise InputError('Tilt/elevation angles are outside the supported flat-roof layout domain.')
    if module['panel_gap_m'] < 0 or not module.get('source'):
        raise InputError('Module gap must be nonnegative; module/design assumptions need a source.')
    if module['azimuth_degrees_from_north'] is not None and not 0 <= module['azimuth_degrees_from_north'] < 360:
        raise InputError('Panel azimuth must be in [0,360), measured clockwise from north.')
    if not 0.1 <= settings['grid_resolution_m'] <= 2:
        raise InputError('Grid resolution must be between 0.1 and 2 m for this raster baseline.')
    if not 0 < settings['minimum_lidar_coverage'] <= 1:
        raise InputError('minimum_lidar_coverage must be in (0,1].')
    for name, scenario in settings['scenarios'].items():
        for key in ('edge_setback_m', 'obstacle_clearance_m'):
            if not np.isfinite(scenario[key]) or scenario[key] < 0:
                raise InputError(f'{name}.{key} must be finite and nonnegative.')


def missing_inputs(settings):
    problems = []
    for key in ('footprint_path', 'eligible_mask_path', 'exclusions_path'):
        if not settings.get(key) or not resolve(settings[key]).is_file():
            problems.append(f'Missing {key}: {settings.get(key)}')
    if not settings.get('geometry_verified_current'):
        problems.append('Current building/roof identity and post-construction geometry are not verified.')
    review = settings.get('review', {})
    if not review.get('verified') or not review.get('source_url') or not review.get('source_date'):
        problems.append('A sourced, dated review of eligible areas and exclusions is required.')
    elif date.fromisoformat(review['source_date']) <= completion_cutoff(settings):
        problems.append('Review imagery/plans predate or ambiguously coincide with completion.')
    if review.get('existing_pv_status') not in ('none_verified', 'present_excluded'):
        problems.append('Existing PV status is unknown; verify none or explicitly exclude existing panels.')
    if not REQUIRED_EXCLUSIONS.issubset(review.get('exclusions_checked', [])):
        problems.append('Review must explicitly check terraces, vegetation, access, equipment, safety paths and existing PV.')
    if settings.get('method') == 'lidar':
        if not settings.get('tile_metadata_csv') or not resolve(settings['tile_metadata_csv']).is_file():
            problems.append('No dated LiDAR tile manifest. Use lidar_tiles_TEMPLATE.csv; do not use LAS creation dates.')
    elif settings.get('method') != 'reviewed_plan':
        problems.append('method must be lidar or reviewed_plan (documented current plan/imagery fallback).')
    return problems


def capacity_scenarios(footprint, eligible, exclusions, settings, points=None):
    """Pure geometric planning calculation, callable with explicit test fixtures."""
    validate_settings(settings)
    results, layers = [], {}
    for name, scenario in settings['scenarios'].items():
        edge, clearance = scenario['edge_setback_m'], scenario['obstacle_clearance_m']
        obstacle_geom = exclusions
        reading = None
        if points is not None:
            roof = read_roof_lidar(footprint, points, res=settings['grid_resolution_m'],
                                   include_lower=settings['include_lower_roofs'],
                                   edge_setback=edge, clearance=clearance)
            if roof.summary['lidar_coverage'] < settings['minimum_lidar_coverage']:
                raise InputError(f'Insufficient classified roof-point coverage: {roof.summary["lidar_coverage"]}; do not extrapolate roof area.')
            detected = roof.grid.cells_to_polygon(roof.obstacle)
            if detected is not None:
                obstacle_geom = unary_union([exclusions, detected])
            # V1 unioned adjacent surfaces at different heights. Never pack a
            # panel across an A160 step: keep each detected plane separate and
            # apply setbacks to its own physical edge, not only the plot edge.
            regions = []
            for surface_id in np.unique(roof.surface_id[roof.surface_id >= 0]):
                usable_region = roof.grid.cells_to_polygon(roof.usable & (roof.surface_id == surface_id))
                whole_surface = roof.grid.cells_to_polygon(roof.surface_id == surface_id)
                if usable_region is not None:
                    regions.append(usable_region.intersection(whole_surface.buffer(-edge)))
            reading = roof.summary
        else:
            # Current-plan fallback can express separate roof levels as disjoint
            # eligible polygons. Keep MultiPolygon components separate in packing.
            candidate = footprint.buffer(-edge).intersection(eligible)
            regions = list(candidate.geoms) if candidate.geom_type == 'MultiPolygon' else [candidate]
        # The reviewed eligible mask can only remove areas; it never adds roof
        # area beyond current geometry or overrides detected/no-data obstacles.
        regions = [region.intersection(eligible).difference(obstacle_geom.buffer(clearance))
                   .intersection(footprint.buffer(-edge)) for region in regions]
        free = unary_union(regions) if regions else Polygon()
        module = settings['module']
        layouts = [lay_out(region, footprint, tilt_deg=module['tilt_degrees'],
                         azimuth_deg=module['azimuth_degrees_from_north'],
                         panel_long_m=module['long_m'], panel_short_m=module['short_m'],
                         module_wp=module['wp'], gap_m=module['panel_gap_m'],
                         winter_elevation_deg=module['winter_design_elevation_degrees'],
                         shift_step_m=module['grid_shift_step_m']) for region in regions if not region.is_empty]
        orientation = layouts[0] if layouts else lay_out(Polygon(), footprint,
                        tilt_deg=module['tilt_degrees'], azimuth_deg=module['azimuth_degrees_from_north'], module_wp=module['wp'])
        layout = Layout([panel for item in layouts for panel in item.panels],
                        orientation.azimuth_deg, orientation.tilt_deg, module['wp'])
        results.append({'building_id': settings['building_id'], 'scenario': name,
                        'usable_area_m2': float(free.area), 'panel_count': layout.count,
                        'module_wp': layout.module_wp, 'estimated_kwp': layout.kwp,
                        'azimuth_degrees_from_north': layout.azimuth_deg,
                        'tilt_degrees': layout.tilt_deg, 'edge_setback_m': edge,
                        'obstacle_clearance_m': clearance, 'method': settings['method'],
                        'data_origin': 'ESTIMATED_ROOF', 'model_version': 'v1_geometry_v2_dated_adapter_1',
                        'certified_installation': False})
        layers[name] = {'eligible': free, 'obstacles': obstacle_geom, 'panels': layout.panels,
                        'lidar_summary': reading}
    return pd.DataFrame(results), layers


def preview_svg(path, footprint, layers, settings):
    minx, miny, maxx, maxy = footprint.bounds
    margin = 3
    minx, miny, maxx, maxy = minx - margin, miny - margin, maxx + margin, maxy + margin
    scale = max(maxx - minx, maxy - miny) / 700
    texts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx} {-maxy} {maxx-minx} {maxy-miny}" width="900">',
             f'<title>{escape(settings["building_id"])} estimated capacity QA; not certified</title>',
             '<g transform="scale(1,-1)">']
    review = settings.get('review', {})
    if review.get('orthophoto_path'):
        bbox = review.get('orthophoto_bbox_25831')
        if not bbox or len(bbox) != 4:
            raise InputError('Orthophoto overlay needs its exact EPSG:25831 image bounds.')
        x0, y0, x1, y1 = bbox
        payload = base64.b64encode(require_file(resolve(review['orthophoto_path'])).read_bytes()).decode('ascii')
        texts.append(f'<image href="data:image/png;base64,{payload}" x="{x0}" y="{-y1}" width="{x1-x0}" height="{y1-y0}" transform="scale(1,-1)" preserveAspectRatio="none"/>')
    for geom, color in [(footprint, '#dddddd'), (layers['eligible'], '#64c27b'), (layers['obstacles'], '#ed7777')]:
        if not geom.is_empty:
            texts.append(geom.svg(scale_factor=scale, fill_color=color))
    for panel in layers['panels']:
        texts.append(panel.svg(scale_factor=scale / 4, fill_color='#347ac2'))
    texts.extend(['</g>', '</svg>'])
    path.write_text('\n'.join(texts), encoding='utf-8')


def run(settings_path='config/roof_capacity.json'):
    settings_path = require_file(resolve(settings_path))
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    out = resolve(settings['output_dir'])
    out.mkdir(parents=True, exist_ok=True)
    report = ROOT / 'reports/roof_capacity' / settings['building_id']
    report.mkdir(parents=True, exist_ok=True)
    readiness = {'checked_utc': now(), 'building_id': settings['building_id'], 'status': 'blocked',
                 'settings_sha256': sha256(settings_path), 'blockers': [],
                 'limitations': 'Geometric scenarios only. Structural, fire/safety design, waterproofing, permits, electrical interconnection and actual production remain unverified.'}
    try:
        blockers = missing_inputs(settings)
        if blockers:
            readiness['blockers'] = blockers
            raise InputError('; '.join(blockers))
        footprint = load_geometry(settings['footprint_path'], settings['footprint_crs'])
        eligible = load_geometry(settings['eligible_mask_path'], settings['mask_crs'], True)
        exclusions = load_geometry(settings['exclusions_path'], settings['mask_crs'], True)
        if eligible.difference(footprint.buffer(1e-6)).area > 0.01:
            raise InputError('Reviewed eligible polygon extends outside the selected building footprint.')
        points, survey_dates, sources, hashes = None, [], [], {}
        for key in ('footprint_path', 'eligible_mask_path', 'exclusions_path'):
            hashes[settings[key]] = sha256(resolve(settings[key]))
        if settings['method'] == 'lidar':
            meta_path = require_file(resolve(settings['tile_metadata_csv']))
            tiles = pd.read_csv(meta_path, keep_default_na=False).to_dict('records')
            if not tiles:
                raise InputError('LiDAR tile manifest is empty.')
            paths = []
            for tile in tiles:
                validate_vintage(tile, settings)
                path = require_file(resolve(tile['path']))
                with laspy.open(path) as reader:
                    crs = reader.header.parse_crs()
                    if crs is not None and CRS.from_user_input(crs) != METRIC_CRS:
                        raise InputError(f'{path.name}: header CRS differs from EPSG:25831.')
                    if reader.header.mins[0] > footprint.bounds[2] or reader.header.maxs[0] < footprint.bounds[0] or reader.header.mins[1] > footprint.bounds[3] or reader.header.maxs[1] < footprint.bounds[1]:
                        raise InputError(f'{path.name}: does not overlap the selected building.')
                paths.append(path)
                survey_dates.append(tile['survey_start'])
                sources.append(tile['source_url'])
                hashes[str(path)] = sha256(path)
            hashes[str(meta_path)] = sha256(meta_path)
            points = roof_points(footprint, paths)
        table, layers = capacity_scenarios(footprint, eligible, exclusions, settings, points)
        table['survey_date'] = min(survey_dates) if survey_dates else settings['review']['source_date']
        table['source'] = '; '.join(sorted(set(sources))) if sources else settings['review']['source_url']
        table['review_source_date'] = settings['review']['source_date']
        table['confidence'] = 'reviewed_geometric_scenario_not_certified'
        table.to_csv(out / 'roof_capacity_scenarios.csv', index=False)
        for name, layer in layers.items():
            props = {'building_id': settings['building_id'], 'scenario': name, 'data_origin': 'ESTIMATED_ROOF'}
            write_geojson(out / f'{name}_eligible_roof.geojson', [layer['eligible']], [props])
            write_geojson(out / f'{name}_obstacles.geojson', [layer['obstacles']], [props])
            write_geojson(out / f'{name}_panels.geojson', layer['panels'], [props] * len(layer['panels']))
            preview_svg(out / f'{name}_qa.svg', footprint, layer, settings)
            if layer['lidar_summary'] is not None:
                write_json(out / f'{name}_lidar_reading.json', layer['lidar_summary'])
        readiness.update(status='ready' if table.estimated_kwp.gt(0).any() else 'no_eligible_capacity',
                         input_sha256=hashes, scenario_csv=str(out / 'roof_capacity_scenarios.csv'),
                         scenario_csv_sha256=sha256(out / 'roof_capacity_scenarios.csv'),
                         internal_crs='EPSG:25831', geojson_crs='EPSG:4326',
                         survey_dates=survey_dates, cv_model_used=False)
        return table
    except (InputError, ValueError, KeyError, OSError) as exc:
        if not readiness['blockers']:
            readiness['blockers'] = [str(exc)]
        raise InputError(f'Roof capacity blocked for {settings["building_id"]}: {exc}') from exc
    finally:
        write_json(report / 'readiness.json', readiness)


def export_pvgis_settings(settings_path, scenario, output):
    settings_path = require_file(resolve(settings_path))
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    readiness = json.loads(require_file(ROOT / 'reports/roof_capacity' / settings['building_id'] / 'readiness.json').read_text(encoding='utf-8'))
    if readiness['status'] != 'ready' or readiness['settings_sha256'] != sha256(settings_path):
        raise InputError('Run a successful roof-capacity calculation with the current settings before exporting PVGIS settings.')
    csv_path = require_file(Path(readiness['scenario_csv']))
    if sha256(csv_path) != readiness['scenario_csv_sha256']:
        raise InputError('Capacity CSV changed since the reviewed run; recompute before PVGIS export.')
    table = pd.read_csv(csv_path)
    selected = table[table.scenario.eq(scenario)]
    if len(selected) != 1 or selected.estimated_kwp.iloc[0] <= 0:
        raise InputError('Select a unique positive-capacity scenario; no PV can be generated from an empty mask.')
    row = selected.iloc[0]
    centroid = load_geometry(settings['footprint_path'], settings['footprint_crs']).centroid
    lon, lat = Transformer.from_crs(METRIC_CRS, GEO_CRS, always_xy=True).transform(centroid.x, centroid.y)
    result = {'roof_id': settings['building_id'], 'capacity_kwp': float(row.estimated_kwp),
              'latitude': lat, 'longitude': lon, 'timestamp_basis': 'UTC', 'power_unit': 'W',
              'tilt': float(row.tilt_degrees),
              # V1 = north-clockwise; PVGIS = south-zero, west-positive.
              'azimuth': float(((row.azimuth_degrees_from_north - 180 + 180) % 360) - 180),
              'azimuth_convention': 'PVGIS: south=0, east=-90, west=90',
              'weather_year': settings['pvgis']['weather_year'], 'loss_percent': settings['pvgis']['loss_percent'],
              'source_url': settings['pvgis']['source_url'], 'capacity_origin': 'ESTIMATED_ROOF',
              'capacity_scenario': scenario, 'capacity_source': str(csv_path),
              'notes': 'Capacity scenario for PVGIS, not an installed/approved system. Weather year/losses must be selected explicitly.'}
    write_json(resolve(output), result)
    return result
