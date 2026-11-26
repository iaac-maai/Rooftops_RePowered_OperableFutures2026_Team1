import pandas as pd
import pytest

from pipeline.__main__ import case_ready, main
from pipeline.common import load_config
from pipeline.case_study import validate_inventory
from pipeline.common import InputError


def test_matching_stops_until_host_selected(capsys):
    cfg = load_config()
    cfg['case_study']['host_building_id'] = None
    with pytest.raises(InputError, match='Host selection is deferred'):
        case_ready(cfg)


def test_inventory_requires_exactly_one_consistent_host_and_sources():
    # Deliberately hypothetical test fixture, not a project case-study inventory.
    inventory = pd.DataFrame({'building_id': ['test_host', 'test_other'], 'is_host': [True, False],
                              'building_use': 'Office', 'latitude': 41.4, 'longitude': 2.1,
                              'floor_area_m2': 100, 'source_url': 'test-fixture-only'})
    validate_inventory(inventory, 'test_host', ['test_host', 'test_other'])
    with pytest.raises(InputError):
        validate_inventory(inventory.assign(is_host=True), 'test_host', ['test_host', 'test_other'])
    with pytest.raises(InputError):
        validate_inventory(inventory.assign(source_url=None), 'test_host', ['test_host', 'test_other'])
