"""The panel catalogue (step02_pv_capacity/panels.csv): the one place panel sizes live."""
import pytest

from step02_pv_capacity import layout


def test_both_panels_load_from_the_csv():
    assert set(layout.CATALOGUE) == {"residential_420", "cep9_540"}
    assert layout.WATTAGES == [420, 540]
    assert layout.DEFAULT_MODULE.key == "residential_420"


def test_sizes_in_mm_become_metres():
    r = layout.CATALOGUE["residential_420"]
    assert (r.long_m, r.short_m) == (1.722, 1.134)
    c = layout.CATALOGUE["cep9_540"]
    assert (c.long_m, c.short_m) == (2.279, 1.134)
    assert c.area_m2 == pytest.approx(2.584, abs=0.001)
    assert c.status == "REAL" and r.status == "ASSUMPTION"


def test_get_module_by_watts_or_key():
    assert layout.get_module(540) is layout.get_module("cep9_540")
    assert layout.get_module("420") is layout.DEFAULT_MODULE
    assert "CEP9 real" in layout.get_module(540).label
    with pytest.raises(SystemExit):
        layout.get_module(999)
