"""Offline checks on step 02's existing-panel finder (photo colours + LiDAR, fitted as rectangles)."""
import math

import numpy as np
import pytest

from step02_pv_capacity import existing_panels as ep
from step02_pv_capacity.grid import Grid
from step02_pv_capacity.layout import GAP_M, MODULES
from step02_pv_capacity.lidar_roof import LidarRoof

CEP9 = MODULES["cep9_540"]           # 2.279 x 1.134 m, from the catalogue
WARM = (210, 185, 155)               # gravel roof: red well above blue
GREY = (120, 125, 135)               # modules
FRAME = (200, 205, 210)              # light frames and gaps: the texture


def _flat_roof(size_m=40.0):
    """A flat size_m x size_m roof read by LiDAR (0.5 m cells) and an empty warm photo (0.1 m)."""
    n = int(size_m / 0.5)
    grid = Grid(0.0, size_m, 0.5, n, n)
    roof = np.ones((n, n), bool)
    lroof = LidarRoof(grid, roof, np.full((n, n), 10.0), np.zeros((n, n), int), np.zeros((n, n), bool),
                      roof.copy(), {"surfaces": [{"height_m": 10.0, "area_m2": size_m ** 2}]}, np.zeros((n, n), bool))
    rgb = np.zeros((n * 5, n * 5, 3), np.uint8)
    rgb[...] = WARM
    return rgb, lroof


def _paint_block(rgb, grid, cx, cy, angle_deg, per_row, rows):
    """Paint per_row x rows CEP9 panels (landscape, rows along angle_deg) centred on (cx, cy)."""
    pu, pv = ep.pitches(CEP9)
    depth = pv - ep.EXISTING_ROW_GAP_M
    length, width = per_row * pu - GAP_M, depth + (rows - 1) * pv
    X, Y = grid.centres()
    t = math.radians(angle_deg)
    u = (X - cx) * math.cos(t) + (Y - cy) * math.sin(t) + length / 2
    v = -(X - cx) * math.sin(t) + (Y - cy) * math.cos(t) + width / 2
    inside = (u >= 0) & (u <= length) & (v >= 0) & (v <= width)
    rgb[inside] = GREY
    lines = inside & ((np.mod(v, pv) < 0.12) | (np.mod(u, pu / 2) < 0.08))   # row gaps and half-cell lines
    rgb[lines] = FRAME
    return length * width


def test_two_rotated_blocks_give_two_rectangles_and_noise_goes():
    rgb, lroof = _flat_roof()
    fine = lroof.grid.finer(5)
    _paint_block(rgb, fine, 12.0, 12.0, 30.0, 4, 3)
    _paint_block(rgb, fine, 26.0, 28.0, 30.0, 5, 4)
    rng = np.random.default_rng(1)
    rgb[rng.integers(0, 400, 300), rng.integers(0, 400, 300)] = GREY       # scattered noise pixels
    found = ep.detect(rgb, lroof, 5, roof_angle_deg=30.0, module=CEP9)
    rects = sorted(found["rectangles"], key=lambda r: r["panels_estimate"])
    assert len(rects) == 2
    for r in rects:
        assert ep._angle_gap(r["angle_deg"], 30.0) <= 2
    assert abs(rects[0]["panels_estimate"] - 12) <= 4          # 4 x 3, within one row
    assert abs(rects[1]["panels_estimate"] - 20) <= 5          # 5 x 4, within one row


def test_an_l_shaped_blob_gives_two_rectangles():
    grid = Grid(0.0, 20.0, 0.1, 200, 200)
    X, Y = grid.centres()
    leg1 = (X >= 2) & (X <= 13.6) & (Y >= 2) & (Y <= 5.7)        # 5 panels x 3 rows, along x
    leg2 = (X >= 2) & (X <= 6.6) & (Y > 5.7) & (Y <= 15.0)       # 2 panels wide, going up
    rects, angle = ep.fit_rectangles(leg1 | leg2, grid, 0.0, CEP9)
    assert angle == 0.0
    assert len(rects) == 2


def test_listed_look_alike_is_not_a_panel():
    rgb, lroof = _flat_roof()
    _paint_block(rgb, lroof.grid.finer(5), 20.0, 20.0, 0.0, 4, 3)
    found = ep.detect(rgb, lroof, 5, not_panels=[(20.0, 20.0, 3.0, "solar water heater")], roof_angle_deg=0.0,
                      module=CEP9)
    assert found["rectangles"] == [] and not found["pixels"].any()
    assert found["look_alikes"].sum() * 0.25 > 20               # kept as an obstacle instead


def test_thin_ragged_strip_is_dropped():
    """An L-shaped 1.2 m wide strip of grey texture (a corridor edge) is not a panel block."""
    rgb, lroof = _flat_roof()
    strip = np.zeros(rgb.shape[:2], bool)
    strip[30:42, 20:180] = True                                  # 16 m long, 1.2 m wide
    strip[30:170, 168:180] = True                                # and down the side: an L
    rgb[strip] = GREY
    rgb[strip & (np.arange(rgb.shape[1])[None, :] % 6 == 0)] = FRAME
    found = ep.detect(rgb, lroof, 5, roof_angle_deg=0.0, module=CEP9)
    assert found["rectangles"] == [] and found["blobs"] == []


def test_summary_counts_from_the_rectangles():
    found = {"rectangles": [{"area_m2": 34.4, "panels_estimate": 12}, {"area_m2": 54.1, "panels_estimate": 20}],
             "blobs": [{"area_m2": 30.0}, {"area_m2": 50.0}]}
    s = ep.summary(found, CEP9)
    assert s["existing_panels_m2"] == 88.5 and s["existing_panels_estimate"] == 32
    assert s["existing_panels_pixels_m2"] == 80.0
    assert CEP9.area_m2 == pytest.approx(2.584, abs=0.001)
