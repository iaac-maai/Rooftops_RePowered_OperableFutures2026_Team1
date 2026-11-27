"""Step 3: place tilted panel rows on the usable roof area.

Flat Barcelona roofs usually get low-tilt rows on a frame. Rows run along the
building edge whose outward direction is closest to south (in the Eixample's
45-degree grid that means south-east or south-west), because rows squared to
the building fill far more of the roof than rows turned to true south, and at
10 degrees of tilt the yield difference is only a few percent.

Rows are spaced so the row in front does not shade the next one when the sun
is at WINTER_NOON_ELEVATION_DEG. Several grid shifts are tried and the one
that fits the most panels is kept.
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import box

TILT_DEG = 10.0
GAP_M = 0.05               # between panels in a row
WINTER_NOON_ELEVATION_DEG = 25.0  # Barcelona, 21 December at noon
SHIFT_STEP_M = 0.25
# East-West ("ew") rows: pairs of panels leaning against each other, one half facing the building's
# south-side direction and the other the opposite way, no gap for shade (27 Nov 2026).
EW_TILT_DEG = 10.0         # CEP9's real plant: East-West "Delta Wing" at 10 deg [CEP9, email from César Ochoa, 27 Nov 2026]
# Pattern (Breno, from the photo, 27 Nov 2026): pair, gap, pair, gap ... The two halves of a pair touch at the ridge;
# a maintenance gap follows EVERY pair, on one side only (the valley). Racking makers put the walkway there too:
# 150 mm [Schletter FixGrid East-West manual], 8 in = 0.20 m [Unirac RMDT manual].
EW_RIDGE_GAP_M = 0.0       # the halves lean against each other (back to back) [CEP9, 27 Nov 2026; photo]
EW_VALLEY_GAP_M = 0.40     # gap after every pair: measured on ICGC orthophoto / LiDAR, ~0.25 m per pixel, approximate.
                           # Real block 1 repeats every 2.63 m on the photo and 2.66 m in the LiDAR (27 Nov 2026);
                           # minus the pair's depth 2 x 1.134 m x cos 10 deg = 2.234 m -> 0.40 m (LiDAR 0.43 m).
                           # Check: 5 pairs in block 1's 12.79 m = 5 x 2.234 + 4 x 0.40 = 12.77 m.
PANELS_CSV = Path(__file__).resolve().parent / "panels.csv"   # the panel catalogue: the only place panel sizes live
DEFAULT_KEY = "residential_420"


@dataclass(frozen=True)
class Module:
    """One panel model from panels.csv: peak watts and size (sources in panels.csv and docs/SOURCES.md)."""
    wp: int
    long_m: float          # along the row
    short_m: float         # up the slope (landscape)
    label: str
    key: str = ""
    status: str = ""       # REAL (from the project documents) or ASSUMPTION

    @property
    def area_m2(self):
        return self.long_m * self.short_m


NAMES = {"residential_420": "residential", "cep9_540": "CEP9 real"}


def load_catalogue(path=PANELS_CSV):
    """{key: Module} from panels.csv (sizes in mm there, metres here)."""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            long_m, short_m = int(r["length_mm"]) / 1000, int(r["width_mm"]) / 1000
            wp = int(r["wp"])
            name = NAMES.get(r["key"], r["key"])
            out[r["key"]] = Module(wp, long_m, short_m, f"{wp} W {name}, {long_m:.2f} x {short_m:.2f} m",
                                   r["key"], r["status"])
    return out


CATALOGUE = load_catalogue()
# keyed by wattage (420, 540) and by catalogue key ("residential_420", "cep9_540")
MODULES = {**{m.wp: m for m in CATALOGUE.values()}, **CATALOGUE}
WATTAGES = sorted({m.wp for m in CATALOGUE.values()})
DEFAULT_MODULE = CATALOGUE[DEFAULT_KEY]
PANEL_WP = DEFAULT_MODULE.wp
PANEL_LONG_M = DEFAULT_MODULE.long_m
PANEL_SHORT_M = DEFAULT_MODULE.short_m


def get_module(wp_or_key):
    """The Module for a wattage (420, 540) or a catalogue key (residential_420, cep9_540)."""
    if str(wp_or_key) in CATALOGUE:
        return CATALOGUE[str(wp_or_key)]
    try:
        return MODULES[int(wp_or_key)]
    except (KeyError, ValueError):
        raise SystemExit(f"unknown panel {wp_or_key}; choose a wattage {WATTAGES} or a key {sorted(CATALOGUE)}")


@dataclass
class Layout:
    panels: list           # shapely polygons (footprint on the roof, EPSG:25831)
    azimuth_deg: float     # direction the panels face, from north, clockwise
    tilt_deg: float
    module: Module = DEFAULT_MODULE
    cells: list = None     # (row, column) of each panel in the layout grid; rows run along the building
    orientation_table: list = None   # what --orient search tried: azimuth, panels, yield factor, score
    azimuths: list = None  # per-panel azimuth when the halves differ (East-West); None = all face azimuth_deg
    kind: str = "south"    # "south": rows facing one way with shade gaps; "ew": East-West back-to-back pairs

    @property
    def count(self):
        return len(self.panels)

    @property
    def kwp(self):
        return self.count * self.module.wp / 1000

    def subset(self, keep):
        """A new Layout with only the panels where keep is True."""
        cells = None if self.cells is None else [c for c, k in zip(self.cells, keep) if k]
        az = None if self.azimuths is None else [a for a, k in zip(self.azimuths, keep) if k]
        return Layout([p for p, k in zip(self.panels, keep) if k], self.azimuth_deg, self.tilt_deg,
                      self.module, cells, self.orientation_table, az, self.kind)

    def panel_azimuths(self):
        """Azimuth of every panel (an array), for the yield model."""
        return np.full(self.count, self.azimuth_deg) if self.azimuths is None else np.asarray(self.azimuths, float)

    def centres(self):
        return np.array([[p.centroid.x, p.centroid.y] for p in self.panels]).reshape(-1, 2)


def facing_azimuth(footprint):
    """Of the directions square to the building's longest edge, the one closest to south."""
    ring = np.asarray(footprint.minimum_rotated_rectangle.exterior.coords)
    edges = np.diff(ring, axis=0)
    dx, dy = edges[np.argmax(np.hypot(edges[:, 0], edges[:, 1]))]
    edge_az = math.degrees(math.atan2(dx, dy)) % 360          # azimuth of the edge itself
    candidates = [(edge_az + k * 90) % 360 for k in range(4)]
    return min(candidates, key=lambda a: abs(((a - 180) + 180) % 360 - 180))


def row_pitch(tilt_deg=TILT_DEG, winter_elevation_deg=WINTER_NOON_ELEVATION_DEG, short_m=PANEL_SHORT_M):
    """Distance from one row to the next, measured on the roof (metres)."""
    t = math.radians(tilt_deg)
    depth = short_m * math.cos(t)
    rise = short_m * math.sin(t)
    return depth + rise / math.tan(math.radians(winter_elevation_deg))


def lay_out(usable, footprint, tilt_deg=TILT_DEG, azimuth_deg=None, module=DEFAULT_MODULE):
    """usable: shapely (multi)polygon of usable roof (EPSG:25831). Returns a Layout."""
    if usable is None or usable.is_empty:
        return Layout([], azimuth_deg or 180.0, tilt_deg, module, [])
    az = facing_azimuth(footprint) if azimuth_deg is None else azimuth_deg
    # work in a frame where panels face "down" (south = -v): rotate by (az - 180)
    centre = footprint.centroid
    rot = az - 180.0
    local = affinity.rotate(usable, rot, origin=centre)
    minx, miny, maxx, maxy = local.bounds
    long_m = module.long_m
    depth = module.short_m * math.cos(math.radians(tilt_deg))
    pitch_v = row_pitch(tilt_deg, short_m=module.short_m)
    pitch_u = long_m + GAP_M
    shapely.prepare(local)

    best, best_cells = [], []
    for du in np.arange(0, pitch_u, SHIFT_STEP_M):
        for dv in np.arange(0, pitch_v, SHIFT_STEP_M):
            us = np.arange(minx + du, maxx - long_m + 1e-6, pitch_u)
            vs = np.arange(miny + dv, maxy - depth + 1e-6, pitch_v)
            rects = [box(u, v, u + long_m, v + depth) for v in vs for u in us]
            cells = [(j, i) for j in range(len(vs)) for i in range(len(us))]
            if not rects:
                continue
            ok = shapely.contains(local, rects)
            fits = [r for r, k in zip(rects, ok) if k]
            if len(fits) > len(best):
                best = fits
                best_cells = [c for c, k in zip(cells, ok) if k]
    panels = [affinity.rotate(p, -rot, origin=centre) for p in best]
    return Layout(panels, az, tilt_deg, module, best_cells)


def ew_row_offsets(depth, length, ridge_gap=EW_RIDGE_GAP_M, valley_gap=EW_VALLEY_GAP_M):
    """Start of every E-W half-row across the roof (metres from 0), up to length: pair, gap, pair, gap ...
    The two halves of a pair are ridge_gap apart; valley_gap (the maintenance gap) follows every pair."""
    out, v, k = [], 0.0, 0
    while v + depth <= length + 1e-9:
        out.append(v)
        k += 1
        v += depth + (valley_gap if k % 2 == 0 else ridge_gap)
    return out


def lay_out_ew(usable, footprint, tilt_deg=EW_TILT_DEG, azimuth_deg=None, module=DEFAULT_MODULE,
               ridge_gap=EW_RIDGE_GAP_M, valley_gap=EW_VALLEY_GAP_M):
    """East-West layout: rows along the building, in back-to-back pairs (pair, gap, pair, gap ...). In each
    pair the first half faces azimuth_deg (default: the building's south-side direction, facing_azimuth) and
    the second half the opposite way (azimuth + 180), so the high edges meet at the ridge. No gap is left for
    shade (at 10 deg the halves lean against each other); a maintenance gap follows every pair.
    Returns a Layout with kind 'ew' and per-panel azimuths."""
    az = facing_azimuth(footprint) if azimuth_deg is None else azimuth_deg
    if usable is None or usable.is_empty:
        return Layout([], az, tilt_deg, module, [], azimuths=[], kind="ew")
    centre = footprint.centroid
    rot = az - 180.0
    local = affinity.rotate(usable, rot, origin=centre)
    minx, miny, maxx, maxy = local.bounds
    long_m = module.long_m
    depth = module.short_m * math.cos(math.radians(tilt_deg))
    pitch_u = long_m + GAP_M
    period_v = 2 * depth + ridge_gap + valley_gap    # one pair and its gaps
    offsets = ew_row_offsets(depth, maxy - miny + period_v, ridge_gap, valley_gap)
    shapely.prepare(local)
    best, best_cells = [], []
    for du in np.arange(0, pitch_u, SHIFT_STEP_M):
        for dv in np.arange(0, period_v, SHIFT_STEP_M):
            us = np.arange(minx + du, maxx - long_m + 1e-6, pitch_u)
            vs = [miny - period_v + dv + o for o in offsets]
            vs = [v for v in vs if v + depth <= maxy + 1e-6]
            rects = [box(u, v, u + long_m, v + depth) for v in vs for u in us]
            cells = [(j, i) for j in range(len(vs)) for i in range(len(us))]
            if not rects:
                continue
            ok = shapely.contains(local, rects)
            if ok.sum() > len(best):
                best = [r for r, k in zip(rects, ok) if k]
                best_cells = [c for c, k in zip(cells, ok) if k]
    # half-rows alternate: even rows face az (towards -v in the local frame), odd rows face az + 180;
    # the row index counts from the first possible row, so the pairs stay pairs whatever is cut out
    panels = [affinity.rotate(p, -rot, origin=centre) for p in best]
    azimuths = [az if j % 2 == 0 else (az + 180.0) % 360 for j, _ in best_cells]
    return Layout(panels, az, tilt_deg, module, best_cells, azimuths=azimuths, kind="ew")


ORIENT_SPAN_DEG = 45       # --orient search tries the building's axis +/- this much, in steps of ORIENT_STEP_DEG
ORIENT_STEP_DEG = 5


def yield_factor(azimuth_deg, tilt_deg=TILT_DEG):
    """Rough share of the best-orientation (due south) yearly sun a panel gets when it faces
    azimuth_deg. ASSUMPTION: loss = 0.5 x sin(tilt) x (1 - cos(angle away from south)); at 10 degrees of
    tilt and 45 degrees off south that is 2.5%. It only ranks orientations here; the real yield
    comes from step 03's hour-by-hour model once an orientation is chosen."""
    off = math.radians(((azimuth_deg - 180) + 180) % 360 - 180)
    return 1 - 0.5 * math.sin(math.radians(tilt_deg)) * (1 - math.cos(off))


def orientation_table(usable, footprint, tilt_deg=TILT_DEG, module=DEFAULT_MODULE,
                      span=ORIENT_SPAN_DEG, step=ORIENT_STEP_DEG):
    """Lay the panels out at several orientations around the building's own axis (and due south) and
    score each by panels x yield factor. Rows turned a few degrees can fit more panels, but panels
    turned away from south make less, so the score weighs both. Returns the table, best first."""
    base = facing_azimuth(footprint)
    azs = {round((base + off) % 360, 1): off for off in range(-span, span + 1, step)}
    azs.setdefault(180.0, round(180.0 - base))
    rows = []
    for az, off in sorted(azs.items(), key=lambda kv: kv[1]):
        lay = lay_out(usable, footprint, tilt_deg, az, module)
        f = yield_factor(az, tilt_deg)
        rows.append({"azimuth_deg": az, "offset_from_building_deg": off, "panels": lay.count,
                     "yield_factor": round(f, 4), "score": round(lay.count * f, 1),
                     "is_building_axis": off == 0, "is_south": az == 180.0})
    return sorted(rows, key=lambda r: -r["score"])


def lay_out_oriented(usable, footprint, mode="building", tilt_deg=TILT_DEG, module=DEFAULT_MODULE):
    """mode: 'building' = rows along the building edge nearest south (the default since V1),
    'south' = rows facing due south, 'search' = the best of orientation_table(),
    'eastwest' = East-West back-to-back pairs along the building (lay_out_ew, at EW_TILT_DEG)."""
    if mode == "eastwest":
        return lay_out_ew(usable, footprint, EW_TILT_DEG, None, module)
    if mode == "building":
        return lay_out(usable, footprint, tilt_deg, None, module)
    if mode == "south":
        return lay_out(usable, footprint, tilt_deg, 180.0, module)
    if mode != "search":
        raise SystemExit(f"unknown orientation {mode}; choose building, south, search or eastwest")
    if usable is None or usable.is_empty:
        return lay_out(usable, footprint, tilt_deg, None, module)
    table = orientation_table(usable, footprint, tilt_deg, module)
    lay = lay_out(usable, footprint, tilt_deg, table[0]["azimuth_deg"], module)
    lay.orientation_table = table
    return lay
