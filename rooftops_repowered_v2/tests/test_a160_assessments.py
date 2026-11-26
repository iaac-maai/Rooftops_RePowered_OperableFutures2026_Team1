"""Verify reference separation and accounting boundaries using frozen A160 outputs."""
from copy import deepcopy
import json

import pandas as pd
import pytest

from pipeline.common import InputError, ROOT, resolve
from pipeline.step_02_roof_capacity.adapter import load_geometry
from pipeline.step_02_roof_capacity.assessments import load_settings
from pipeline.step_02_roof_capacity.milestone import check_frozen_prediction, pvgis_records
from pipeline.step_03_pvgis.importer import validate_generation_role


def test_prediction_accepts_no_observed_reference_and_rejects_changed_structural_protocol():
    settings = load_settings()
    settings['observed_panel_mask'] = 'deliberately_nonexistent_reference.geojson'
    check_frozen_prediction(settings)
    changed = deepcopy(settings)
    changed['structural']['low_relief_structural_band_m'] += .1
    with pytest.raises(InputError, match='structural changed'):
        check_frozen_prediction(changed)


@pytest.mark.parametrize('scenario', ['conservative', 'base', 'optimistic'])
def test_additional_candidates_do_not_occupy_existing_arrays_access_or_other_roof_levels(scenario):
    settings = load_settings()
    root = resolve(settings['output_dir'])
    panels = load_geometry(root / f'additional/{scenario}_panels.geojson', 'EPSG:4326', True)
    eligible = load_geometry(root / f'additional/{scenario}_eligible.geojson', 'EPSG:4326', True)
    occupied = load_geometry(settings['observed_array_envelopes'], 'EPSG:4326')
    access = load_geometry(settings['current_access_exclusions'], 'EPSG:4326', True)
    boundary = load_geometry(settings['current_high_roof_boundary'], 'EPSG:4326')
    assert panels.difference(eligible.buffer(1e-6)).area < 1e-6
    assert panels.difference(boundary).area < 1e-6
    assert panels.intersection(access).area < 1e-6
    assert panels.intersection(occupied).area < 1e-6
    if not panels.is_empty:
        assert panels.distance(occupied) >= settings['scenarios'][scenario]['obstacle_clearance_m'] - 1e-6


def test_pvgis_roles_capacities_and_azimuth_are_separate():
    settings = load_settings()
    root = resolve(settings['output_dir'])
    tables = {name: pd.read_csv(root / name / 'roof_capacity_scenarios.csv') for name in ('retrospective', 'additional')}
    records = pvgis_records(settings, tables)
    assert len(records) == 7
    for record in records:
        assert record['energy_sharing_eligible'] is False
        if record['assessment'] == 'observed_existing':
            assert record['capacity_kwp'] is None and record['tilt'] is None
        else:
            assert record['azimuth'] == pytest.approx(-44.1064518686)
            assert record['weather_year'] is None and record['loss_percent'] is None
            if record['capacity_kwp'] == 0:
                assert record['positive_capacity'] is False
        with pytest.raises(InputError):
            validate_generation_role(record)
    # Older, fully specified settings remain supported.
    validate_generation_role({'capacity_kwp': 1.0})


def test_reference_is_not_an_installed_capacity_or_uncontaminated_preinstallation_validation():
    root = ROOT / 'reports/roof_capacity/A160'
    report = json.loads((root / 'reference_separation.json').read_text())
    assert report['observed_mask_used_in_retrospective_predictor'] is False
    assert report['pre_installation_source_independence'] is False
    table = pd.read_csv(root / 'retrospective_validation.csv')
    assert table.observed_panel_count.isna().all()
    assert table.observed_installed_kwp.isna().all()
    acquisition = json.loads((root / 'lidar_acquisition.json').read_text())
    assert acquisition['roof_acquisition_utc'][0].startswith('2022-06-01')
    assert acquisition['creation_date_not_survey_date'] == '2025-08-08'
    city = pd.read_csv(ROOT / 'datasets/processed/roof_capacity/A160/municipal_map_comparison.csv')
    assert not city.current_roof_validation_eligible.any()
    assert city.combined_capacity_kwp.isna().all()
