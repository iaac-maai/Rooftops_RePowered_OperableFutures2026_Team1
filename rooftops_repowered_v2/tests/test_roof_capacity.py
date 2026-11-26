"""Synthetic geometric fixtures only; never substitute these for A160 inputs."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon, box, mapping

from pipeline.common import InputError
from pipeline.step_02_roof_capacity import adapter
from pipeline.step_02_roof_capacity.adapter import capacity_scenarios, export_pvgis_settings, validate_vintage
from pipeline.step_02_roof_capacity.layout import lay_out
from pipeline.step_02_roof_capacity.lidar_roof import lower_surfaces


@pytest.fixture
def settings():
    cfg = json.loads(Path('config/roof_capacity.json').read_text(encoding='utf-8'))
    cfg.update(building_id='SYNTHETIC_TEST_ROOF', method='reviewed_plan', geometry_verified_current=True)
    cfg['review'].update(verified=True, source_date='2025-01-01', source_url='synthetic-test-fixture', existing_pv_status='none_verified')
    cfg['module']['azimuth_degrees_from_north'] = 180
    return cfg


@pytest.fixture
def footprint():
    return box(430000, 4582000, 430020, 4582015)


@pytest.mark.parametrize('start,end', [('2021-01-01','2021-12-31'), ('2021-01-01','2023-01-01'), ('2022-12-01','2022-12-01')])
def test_stale_or_ambiguous_tiles_rejected_even_with_recent_file_creation(settings, start, end):
    record = {'survey_start': start, 'survey_end': end, 'creation_date': '2026-01-01',
              'crs': 'EPSG:25831', 'vertical_units': 'm', 'source_url': 'test-only', 'acquisition_evidence': 'test-only'}
    with pytest.raises(InputError, match='Stale or ambiguous'):
        validate_vintage(record, settings)


def test_tile_crs_units_and_acquisition_evidence_are_explicit(settings):
    record = {'survey_start': '2024-01-01', 'survey_end': '2024-01-02', 'crs': 'EPSG:25831',
              'vertical_units': 'm', 'source_url': 'test-only', 'acquisition_evidence': 'test-only'}
    validate_vintage(record, settings)
    for change in ({'crs': 'EPSG:4326'}, {'vertical_units': 'ft'}, {'acquisition_evidence': ''}):
        with pytest.raises(InputError):
            validate_vintage({**record, **change}, settings)


def test_layout_uses_selected_module_wp_and_avoids_reviewed_exclusions(settings, footprint):
    obstacle = box(430006, 4582004, 430012, 4582010)  # may represent existing PV or vegetation
    settings['module']['wp'] = 500
    table, layers = capacity_scenarios(footprint, footprint, obstacle, settings)
    assert table.panel_count.gt(0).all()
    np.testing.assert_allclose(table.estimated_kwp, table.panel_count * 0.5)
    assert table.set_index('scenario').loc['conservative', 'usable_area_m2'] <= table.set_index('scenario').loc['base', 'usable_area_m2']
    for scenario, layer in layers.items():
        for panel in layer['panels']:
            assert layer['eligible'].covers(panel)
            assert not panel.intersects(obstacle)
            assert panel.distance(obstacle) >= settings['scenarios'][scenario]['obstacle_clearance_m'] - 1e-8


@pytest.mark.parametrize('kind', ['empty_eligible', 'fully_obstructed'])
def test_no_eligible_roof_means_zero_panels(settings, footprint, kind):
    eligible = Polygon() if kind == 'empty_eligible' else footprint
    excluded = footprint if kind == 'fully_obstructed' else Polygon()
    table, _ = capacity_scenarios(footprint, eligible, excluded, settings)
    assert table.panel_count.eq(0).all() and table.estimated_kwp.eq(0).all()


def test_panels_cannot_bridge_two_roof_levels_even_with_zero_setback(settings, footprint):
    cfg = deepcopy(settings)
    cfg['scenarios'] = {'test': {'edge_setback_m': 0, 'obstacle_clearance_m': 0}}
    xs, ys = np.meshgrid(np.arange(430000.1, 430020, .25), np.arange(4582000.1, 4582015, .25))
    points = np.column_stack([xs.ravel(), ys.ravel(), np.where(xs.ravel() < 430010, 25., 28.)])
    _, layers = capacity_scenarios(footprint, footprint, Polygon(), cfg, points)
    for panel in layers['test']['panels']:
        assert not (panel.bounds[0] < 430010 < panel.bounds[2])


def test_v1_fragmented_surface_edge_case_and_empty_north_layout(footprint):
    surfaces = [{'height_m': 20 + i, 'area_m2': 20} for i in range(12)]
    assert isinstance(lower_surfaces(surfaces), list)
    empty = lay_out(Polygon(), footprint, azimuth_deg=0, module_wp=500)
    assert empty.azimuth_deg == 0 and empty.kwp == 0


def write_polygon(path, geom):
    path.write_text(json.dumps({'type': 'FeatureCollection', 'features': [] if geom.is_empty else [
        {'type': 'Feature', 'geometry': mapping(geom), 'properties': {}}]}), encoding='utf-8')


def test_reviewed_plan_to_csv_geojson_qa_and_pvgis(settings, footprint, tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, 'ROOT', tmp_path)
    for key, geom in [('footprint_path', footprint), ('eligible_mask_path', footprint), ('exclusions_path', Polygon())]:
        path = tmp_path / f'{key}.geojson'
        write_polygon(path, geom)
        settings[key] = str(path)
    settings.update(footprint_crs='EPSG:25831', mask_crs='EPSG:25831', output_dir=str(tmp_path / 'out'))
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps(settings), encoding='utf-8')
    table = adapter.run(cfg)
    assert table.estimated_kwp.gt(0).any()
    assert (tmp_path / 'out/base_qa.svg').is_file()
    geometry = json.loads((tmp_path / 'out/base_eligible_roof.geojson').read_text())['features'][0]['geometry']
    assert abs(geometry['coordinates'][0][0][0]) < 180  # exported WGS84, not UTM numbers
    export = export_pvgis_settings(cfg, 'base', tmp_path / 'pvgis.json')
    assert export['azimuth'] == 0  # north-clockwise 180 -> PVGIS south-zero 0
    assert export['weather_year'] is None and export['loss_percent'] is None
    assert export['capacity_kwp'] == pytest.approx(table.set_index('scenario').loc['base','estimated_kwp'])
    # Current settings must match reviewed output; no stale automatic export.
    settings['module']['wp'] = 600
    cfg.write_text(json.dumps(settings))
    with pytest.raises(InputError, match='current settings'):
        export_pvgis_settings(cfg, 'base', tmp_path / 'stale.json')


def test_missing_review_and_existing_pv_status_block_instead_of_inventing_capacity(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, 'ROOT', tmp_path)
    settings.update(output_dir=str(tmp_path / 'out'), geometry_verified_current=False)
    settings['review']['existing_pv_status'] = 'unknown'
    cfg = tmp_path / 'blocked.json'
    cfg.write_text(json.dumps(settings))
    with pytest.raises(InputError):
        adapter.run(cfg)
    readiness = json.loads((tmp_path / 'reports/roof_capacity/SYNTHETIC_TEST_ROOF/readiness.json').read_text())
    assert readiness['status'] == 'blocked' and readiness['blockers']
    assert not (tmp_path / 'out/roof_capacity_scenarios.csv').exists()
