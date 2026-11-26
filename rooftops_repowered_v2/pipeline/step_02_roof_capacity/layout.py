# Ported from IAAC MaAI Team 1 V1: pipeline/step3/layout.py
# See V1_PROVENANCE.json for original source hash and revision.
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
import math
from dataclasses import dataclass

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import box

PANEL_LONG_M = 1.76        # along the row
PANEL_SHORT_M = 1.13       # up the slope (landscape)
PANEL_WP = 420             # peak watts per panel (about 21% efficient)
TILT_DEG = 10.0
GAP_M = 0.05               # between panels in a row
WINTER_NOON_ELEVATION_DEG = 25.0  # Barcelona, 21 December at noon
SHIFT_STEP_M = 0.25


@dataclass
class Layout:
    panels: list           # shapely polygons (footprint on the roof, EPSG:25831)
    azimuth_deg: float     # direction the panels face, from north, clockwise
    tilt_deg: float
    module_wp: float = PANEL_WP

    @property
    def count(self):
        return len(self.panels)

    @property
    def kwp(self):
        return self.count * self.module_wp / 1000

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


def row_pitch(tilt_deg=TILT_DEG, winter_elevation_deg=WINTER_NOON_ELEVATION_DEG,
              panel_short_m=PANEL_SHORT_M):
    """Distance from one row to the next, measured on the roof (metres)."""
    t = math.radians(tilt_deg)
    depth = panel_short_m * math.cos(t)
    rise = panel_short_m * math.sin(t)
    return depth + rise / math.tan(math.radians(winter_elevation_deg))


def lay_out(usable, footprint, tilt_deg=TILT_DEG, azimuth_deg=None,
            panel_long_m=PANEL_LONG_M, panel_short_m=PANEL_SHORT_M,
            module_wp=PANEL_WP, gap_m=GAP_M, winter_elevation_deg=WINTER_NOON_ELEVATION_DEG,
            shift_step_m=SHIFT_STEP_M):
    """usable: shapely (multi)polygon of usable roof (EPSG:25831). Returns a Layout."""
    if usable is None or usable.is_empty:
        return Layout([], 180.0 if azimuth_deg is None else azimuth_deg, tilt_deg, module_wp)
    az = facing_azimuth(footprint) if azimuth_deg is None else azimuth_deg
    # work in a frame where panels face "down" (south = -v): rotate by (az - 180)
    centre = footprint.centroid
    rot = az - 180.0
    local = affinity.rotate(usable, rot, origin=centre)
    minx, miny, maxx, maxy = local.bounds
    depth = panel_short_m * math.cos(math.radians(tilt_deg))
    pitch_v = row_pitch(tilt_deg, winter_elevation_deg, panel_short_m)
    pitch_u = panel_long_m + gap_m
    shapely.prepare(local)

    best = []
    for du in np.arange(0, pitch_u, shift_step_m):
        for dv in np.arange(0, pitch_v, shift_step_m):
            us = np.arange(minx + du, maxx - panel_long_m + 1e-6, pitch_u)
            vs = np.arange(miny + dv, maxy - depth + 1e-6, pitch_v)
            rects = [box(u, v, u + panel_long_m, v + depth) for v in vs for u in us]
            if not rects:
                continue
            fits = [r for r, ok in zip(rects, shapely.contains(local, rects)) if ok]
            if len(fits) > len(best):
                best = fits
    panels = [affinity.rotate(p, -rot, origin=centre) for p in best]
    return Layout(panels, az, tilt_deg, module_wp)
