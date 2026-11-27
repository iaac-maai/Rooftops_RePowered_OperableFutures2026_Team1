"""East-West layout, per-panel azimuths, one-deep rows and per-direction cut-off (offline, made-up roofs)."""
import math
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import box

from step02_pv_capacity import layout as lo
from step03_simulate_generation import options as op
from step03_simulate_generation.energy import plane_of_array

MOD = lo.get_module(540)                                       # 2.279 x 1.134 m
DEPTH = MOD.short_m * math.cos(math.radians(lo.EW_TILT_DEG))   # 1.117 m on the roof


def test_pairs_touch_at_the_ridge_and_a_gap_follows_every_pair():
    off = lo.ew_row_offsets(DEPTH, 10.0)
    assert off[1] - off[0] == pytest.approx(DEPTH + lo.EW_RIDGE_GAP_M)            # halves of a pair: no gap
    assert lo.EW_RIDGE_GAP_M == 0.0
    assert off[2] - off[1] == pytest.approx(DEPTH + lo.EW_VALLEY_GAP_M)           # maintenance gap after the pair
    assert off[3] - off[2] == pytest.approx(DEPTH)                                # next pair: no gap again
    gaps = np.diff(off) - DEPTH
    assert np.allclose(gaps[1::2], lo.EW_VALLEY_GAP_M) and np.allclose(gaps[0::2], 0.0)


def test_panel_count_on_a_made_up_rectangle_matches_a_hand_count():
    # 4 panels along a row: 4 x 2.279 + 3 x 0.05 = 9.266 m; 2 pairs across: 2 x 2.234 + 0.40 = 4.868 m
    along = 4 * MOD.long_m + 3 * lo.GAP_M
    across = 4 * DEPTH + lo.EW_VALLEY_GAP_M
    roof = box(0, 0, along + 0.3, across + 0.3)                # 0.3 m spare: the search moves in 0.25 m steps
    lay = lo.lay_out_ew(roof, roof, module=MOD)
    assert lay.kind == "ew" and lay.count == 16                # hand count: 4 per row x 4 half-rows
    az = np.array(lay.azimuths)
    assert lay.azimuth_deg == pytest.approx(180.0)             # long edge east-west: halves face south and north
    assert sorted(set(np.round(az, 1))) == [0.0, 180.0] and (az == 180.0).sum() == 8
    # south rows with shade gaps fit fewer on the same roof
    assert lo.lay_out(roof, roof, module=MOD).count < lay.count


def test_both_halves_use_their_own_azimuth_in_the_yield():
    weather = SimpleNamespace(dni=np.array([700.0, 700.0]), dhi=np.array([100.0, 100.0]), ghi=np.array([500.0, 500.0]))
    elev, sun_az = np.array([30.0, 30.0]), np.array([100.0, 260.0])                  # morning sun east, afternoon west
    poa = plane_of_array(weather, elev, sun_az, np.ones((2, 2)), np.ones(2), 10.0, [90.0, 270.0])
    assert poa.shape == (2, 2)
    assert poa[0, 0] > poa[1, 0] and poa[1, 1] > poa[0, 1]     # the east half wins in the morning, the west half after
    one = plane_of_array(weather, elev, sun_az, np.ones((2, 2)), np.ones(2), 10.0, 90.0)
    assert np.allclose(one[0], poa[0])                         # a single azimuth still works as before


def test_one_deep_rows_count_as_blocks_only_when_asked():
    cells = [(0, i) for i in range(5)]                          # a single row of 5 good panels
    kwh = np.full(5, 700.0)
    neat = next(o for o in op.OPTIONS if o["id"] == "neat")
    assert op.classify(cells, kwh, neat, MOD.area_m2)[0].sum() == 0
    assert op.classify(cells, kwh, neat, MOD.area_m2, one_deep_min=4)[0].sum() == 5
    assert op.classify(cells[:3], kwh[:3], neat, MOD.area_m2, one_deep_min=4)[0].sum() == 0   # 3 < 4


def test_each_ew_half_is_judged_against_its_own_direction():
    cells = [(j, i) for j in range(2) for i in range(4)]      # one pair, 4 long
    kwh = np.array([760.0] * 4 + [690.0] * 4)                 # the half facing away makes 9% less
    az = [218.5] * 4 + [38.5] * 4
    best = next(o for o in op.OPTIONS if o["id"] == "best")  # 93% cut-off
    assert op.classify(cells, kwh, best, MOD.area_m2)[0].sum() == 0               # one roof-wide p90: weak half
    assert op.classify(cells, kwh, best, MOD.area_m2, azimuths=az)[0].sum() == 8  # per direction: a 2 x 4 block


def test_the_case_file_sets_the_layout_default():
    from step03_simulate_generation.shade_yield import case_layout_defaults
    assert case_layout_defaults("cep9") == {"orient": "eastwest", "one_deep_rows": 4}
    assert case_layout_defaults("a160") == {}
