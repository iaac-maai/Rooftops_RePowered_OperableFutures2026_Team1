"""Step 2b: find solar panels already on the roof, from the orthophoto + LiDAR (rules, no AI).

Why: we want to tell existing panels apart from room for new ones, and for the
validation on the CEP9 school we also want the opposite, to pretend the roof is
empty so our layout can be compared with the real one.

How (on the 0.1 m photo grid, inside the footprint):
1. Panel pixels are neutral grey or blue (red minus blue under NEUTRAL_MAX_WARMTH),
   neither black shadow nor white render, while the bare roof here is warm
   (gravel, tan membrane: red is 40-60 above blue).
2. Panels have texture: module frames and row gaps make the brightness vary
   over a few pixels. Smooth grey surfaces (concrete, render) do not.
3. Clean up: remove anything narrower than a panel (OPEN_PX), close the gaps
   between rows, and keep blobs of at least MIN_BLOB_M2. Thin, ragged blobs
   (narrower than THIN_M and filling less than MIN_FILL of their bounding
   rectangle) are strips along walls and corridors, not panel rows, and are
   dropped. Real rows on CEP9 fill 78-90% of their rectangle, the strips 31-34%.
4. LiDAR check: a panel blob sits on the roof, not on a wall. Blobs with less
   than MIN_ON_SURFACE of their area on a LiDAR roof surface (or on a cell
   that LiDAR marked as obstacle only because the panels stick up) are
   dropped. For each blob we also report the height ripple (rows of tilted
   panels show up as stripes 0.1-0.6 m high); flush glazing and very flat
   panels show none.

5. Things that look like panels but are not (solar water heaters, glazing) are listed
   by hand in not_panels.csv (refcat, x, y, radius_m, what). A blob whose centre
   is within radius_m of a listed point is not counted as a panel; it stays on the
   roof as an obstacle, also when the roof is treated as empty.

6. Rectangles (fit_rectangles): real panels sit in neat rectangular groups, so each
   kept blob becomes one or more oriented rectangles. The angle is the roof's edge
   (or edge + 90 degrees), whichever the strongest edges in the photo follow. The
   blob is split where row or column occupancy drops below SPLIT_SHARE (so an L
   gives two rectangles), each part is boxed and snapped to whole panels when that
   changes its area by less than SNAP_MAX_CHANGE, close neighbours are merged, and
   rectangles under MIN_RECT_PANELS panels or under MIN_RECT_FILL blob pixels are
   dropped. The count comes from the panel pitch: panels per row x rows.

All thresholds are ASSUMPTIONS, tuned by eye on the two CEP9 roofs
(21 Nov 2026), where the photo shows dark grey modules on the Institut Quatre
Cantons roof and light-blue rows on the Escola Pere IV roof.
"""
import csv
from pathlib import Path

import math

import numpy as np
from scipy import ndimage
from shapely.geometry import Polygon

NEUTRAL_MAX_WARMTH = 30   # red - blue below this = not the warm roof finish
MIN_BRIGHT, MAX_BRIGHT = 60, 235
NEUTRAL_SHARE = 0.6       # share of neutral pixels in a 0.9 m window
MIN_TEXTURE = 10          # mean local brightness std (0-255 scale) in a 0.9 m window
OPEN_PX = 7               # 0.7 m: thinner things (wall tops, edges) are removed; steep single panel rows are about 1 m wide
CLOSE_PX = 7              # 0.7 m: gaps between panel rows are closed
MIN_BLOB_M2 = 6.0         # about 2 panels; smaller pieces are edges and corners, not panel blocks
THIN_M = 2.0              # a blob narrower than this ...
MIN_FILL = 0.5            # ... that also fills less than half of its bounding rectangle is a strip along a wall
MIN_ON_SURFACE = 0.6      # share of a blob that must lie on LiDAR roof surface (or low raised cells)
RAISED_MAX_M = 1.5        # obstacle cells at most this high above the surface can be panel rows (steep rows on CEP9 reach about 1.2 m)
# rectangles (fit_rectangles); all ASSUMPTIONS
SPLIT_SHARE = 0.5         # cut a blob where row/column occupancy falls below this share of its fullest row/column
MERGE_GAP_M = 0.5         # rectangles with the same angle closer than this are merged ...
MERGE_MAX_EMPTY = 0.15    # ... when the merged box is at most this much bigger than the two together
MIN_RECT_PANELS = 2       # smaller rectangles are dropped
MIN_RECT_FILL = 0.6       # rectangles with less than this share of their area on blob pixels are dropped
SNAP_MAX_CHANGE = 0.15    # snap a rectangle to whole panels only if that changes its area by less than this
EXISTING_ROW_GAP_M = 0.18 # gap between existing panel rows: measured on the CEP9 Institut photo (the brightness repeats
                          # every 1.30 m across the rows, minus 1.134 m x cos 10 deg = 1.12 m of panel). The photo is
                          # about 0.25 m per pixel, so this is approximate: ASSUMPTION backed by one measurement
NOT_PANELS_PATH = Path(__file__).resolve().parent / "not_panels.csv"


def load_not_panels(refcat, path=NOT_PANELS_PATH):
    """[(x, y, radius_m, what)] listed for this plot in not_panels.csv."""
    if not refcat or not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [(float(r["x"]), float(r["y"]), float(r["radius_m"]), r["what"].strip())
                for r in csv.DictReader(f) if r["refcat"].strip()[:14].upper() == refcat[:14].upper()]


def _local_std(v, size):
    m = ndimage.uniform_filter(v, size)
    return np.sqrt(np.maximum(ndimage.uniform_filter(v * v, size) - m * m, 0))


def photo_candidates(rgb, roof):
    """Pixels that look like panels on the photo (bool, same shape as roof)."""
    rgb = rgb.astype(float)
    r, b = rgb[..., 0], rgb[..., 2]
    v = rgb.mean(axis=2)
    neutral = (r - b < NEUTRAL_MAX_WARMTH) & (v > MIN_BRIGHT) & (v < MAX_BRIGHT)
    texture = ndimage.uniform_filter(_local_std(v, 7), 9)
    m = roof & (ndimage.uniform_filter(neutral.astype(float), 9) > NEUTRAL_SHARE) & (texture > MIN_TEXTURE)
    m = ndimage.binary_opening(m, np.ones((OPEN_PX, OPEN_PX)))
    return ndimage.binary_closing(m, np.ones((CLOSE_PX, CLOSE_PX))) & roof


def detect(rgb, lroof, factor, not_panels=(), roof_angle_deg=None, module=None):
    """Existing panels on one roof.

    rgb: photo on lroof.grid.finer(factor); lroof: step 02 LiDAR reading;
    not_panels: [(x, y, radius_m, what)] of look-alikes to leave out (load_not_panels);
    roof_angle_deg: roof edge direction (roof_edge_angle(footprint)); default: the roof cells' own;
    module: panel model for the rectangles' panel count (default: the catalogue default).
    Returns a dict: pixels (panel pixels on the photo grid), blobs, rectangles,
    rect_fine / rect_coarse (rectangles on the photo / LiDAR grid; these are what step 03
    and the usable area use), look_alikes (LiDAR grid; they stay obstacles).
    """
    from .layout import DEFAULT_MODULE
    module = module or DEFAULT_MODULE
    if roof_angle_deg is None:
        roof_angle_deg = roof_edge_angle(lroof.grid.cells_to_polygon(lroof.roof))
    fine_grid = lroof.grid.finer(factor)
    brightness = rgb.astype(float).mean(axis=2)
    from .grid import upsample

    roof_fine = upsample(lroof.roof, factor)
    cand = photo_candidates(rgb, roof_fine)
    surface = lroof.surface_id >= 0
    base = _surface_height(lroof)
    raised = lroof.obstacle & np.isfinite(lroof.dsm) & (lroof.dsm - base <= RAISED_MAX_M)
    ok_fine = upsample(surface | raised, factor)

    px_m2 = (lroof.grid.res / factor) ** 2
    lab, n = ndimage.label(cand)
    keep = np.zeros_like(cand)
    other = np.zeros_like(cand)
    blobs, rectangles = [], []
    for k in range(1, n + 1):
        cells = lab == k
        area = cells.sum() * px_m2
        if area < MIN_BLOB_M2 or ok_fine[cells].mean() < MIN_ON_SURFACE or _is_strip(cells, lroof.grid.res / factor):
            continue
        rows, cols = np.nonzero(cells)
        cx = lroof.grid.x0 + (cols.mean() + 0.5) * lroof.grid.res / factor
        cy = lroof.grid.y1 - (rows.mean() + 0.5) * lroof.grid.res / factor
        if any(np.hypot(cx - x, cy - y) <= r for x, y, r, _ in not_panels):
            other |= cells
            continue
        keep |= cells
        coarse = cells.reshape(lroof.roof.shape[0], factor, lroof.roof.shape[1], factor).mean(axis=(1, 3)) >= 0.5
        h = lroof.dsm[coarse & np.isfinite(lroof.dsm)]
        rects, angle = fit_rectangles(cells, fine_grid, roof_angle_deg, module, brightness)
        rectangles += rects
        blobs.append({
            "area_m2": round(float(area), 1),
            "x": round(float(cx), 2),
            "y": round(float(cy), 2),
            "lidar_ripple_m": round(float(np.std(h - np.median(h))), 2) if h.size >= 4 else None,
            "angle_deg": round(angle, 1),
            "rectangles": len(rects),
        })
    shape = (lroof.roof.shape[0], factor, lroof.roof.shape[1], factor)
    coarse_other = other.reshape(shape).mean(axis=(1, 3)) > 0
    rect_fine = rectangles_mask(rectangles, fine_grid) & roof_fine
    rect_coarse = rect_fine.reshape(shape).mean(axis=(1, 3)) >= 0.5
    return {"pixels": keep, "blobs": sorted(blobs, key=lambda b: -b["area_m2"]),
            "rectangles": sorted(rectangles, key=lambda r: -r["area_m2"]),
            "rect_fine": rect_fine, "rect_coarse": rect_coarse & lroof.roof,
            "look_alikes": coarse_other & lroof.roof, "roof_angle_deg": round(roof_angle_deg, 1)}


def _is_strip(cells, px_m):
    """True for a thin, ragged blob: narrower than THIN_M and filling under MIN_FILL of its rectangle."""
    from shapely.geometry import MultiPoint
    width = ndimage.distance_transform_edt(cells).max() * 2 * px_m
    if width >= THIN_M:
        return False
    rows, cols = np.nonzero(cells)
    rect = MultiPoint(np.column_stack([cols, rows])).minimum_rotated_rectangle
    return cells.sum() / max(rect.area, 1.0) < MIN_FILL


def _surface_height(lroof):
    """Height of the nearest roof surface for every cell (for 'how far does this stick up')."""
    surface = lroof.surface_id >= 0
    if not surface.any():
        return np.full(lroof.dsm.shape, np.nanmedian(lroof.dsm))
    _, (ri, ci) = ndimage.distance_transform_edt(~surface, return_indices=True)
    return lroof.dsm[ri, ci]


def summary(found, module):
    """Area and count of existing panels from the rectangles (count = panels per row x rows, from the
    panel pitch of module), plus the raw pixel area for comparison."""
    rects = found["rectangles"]
    pu, pv = pitches(module)
    return {"existing_panels_m2": round(sum(r["area_m2"] for r in rects), 1),
            "existing_panels_estimate": int(sum(r["panels_estimate"] for r in rects)),
            "existing_panels_estimate_note": f"per rectangle: panels per row x rows, pitch {pu:.2f} m along the row and "
                                             f"{pv:.2f} m across ({module.label})",
            "existing_panels_pixels_m2": round(sum(b["area_m2"] for b in found["blobs"]), 1),
            "existing_panel_rectangles": rects,
            "existing_panel_blocks": found["blobs"]}


# ---------- rectangles ----------

def roof_edge_angle(footprint):
    """Direction of the footprint's longest edge (of its minimum rotated rectangle), degrees in [0, 180),
    counter-clockwise from east: the same building axis layout.py uses for --orient building."""
    ring = np.asarray(footprint.minimum_rotated_rectangle.exterior.coords)
    edges = np.diff(ring, axis=0)
    dx, dy = edges[np.argmax(np.hypot(edges[:, 0], edges[:, 1]))]
    return math.degrees(math.atan2(dy, dx)) % 180


def photo_edge_angle(brightness, mask):
    """Strongest edge direction inside mask (structure tensor), degrees in [0, 180) from east.
    brightness is a north-up image (row 0 = north); None if there is no texture."""
    gy_img, gx = np.gradient(brightness.astype(float))
    gy = -gy_img                                   # image rows run south, world y runs north
    jxx, jyy, jxy = (gx * gx)[mask].sum(), (gy * gy)[mask].sum(), (gx * gy)[mask].sum()
    if jxx + jyy == 0:
        return None
    grad = 0.5 * math.degrees(math.atan2(2 * jxy, jxx - jyy))   # dominant gradient direction
    return (grad + 90) % 180                       # edges run across the gradient


def _angle_gap(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


def choose_angle(roof_angle, photo_angle):
    """The roof angle or roof angle + 90, whichever is closer to the photo's edges (rows run that way)."""
    options = [roof_angle % 180, (roof_angle + 90) % 180]
    if photo_angle is None:
        return options[0]
    return min(options, key=lambda a: _angle_gap(a, photo_angle))


def pitches(module, tilt_deg=None, row_gap_m=None):
    """(along the row, across the rows) panel pitch in metres for existing panels."""
    from .layout import GAP_M, TILT_DEG
    tilt = TILT_DEG if tilt_deg is None else tilt_deg
    gap = EXISTING_ROW_GAP_M if row_gap_m is None else row_gap_m
    return module.long_m + GAP_M, module.short_m * math.cos(math.radians(tilt)) + gap


def _split(occ, depth=0):
    """Split a 2-D occupancy array into parts [(r0, r1, c0, c1)], cutting where a row or
    column holds less than SPLIT_SHARE of the fullest one."""
    rows = np.flatnonzero(occ.any(axis=1))
    cols = np.flatnonzero(occ.any(axis=0))
    if rows.size == 0:
        return []
    r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    sub = occ[r0:r1, c0:c1]
    if depth > 8:
        return [(r0, r1, c0, c1)]
    for axis in (0, 1):                            # 0: profile over columns, 1: over rows
        prof = sub.sum(axis=axis).astype(float)
        high = prof >= SPLIT_SHARE * prof.max()
        cuts = np.flatnonzero(np.diff(high.astype(int))) + 1
        if cuts.size == 0:
            continue
        parts = []
        for a, b in zip(np.r_[0, cuts], np.r_[cuts, prof.size]):
            piece = np.zeros_like(sub)
            if axis == 0:
                piece[:, a:b] = sub[:, a:b]
            else:
                piece[a:b, :] = sub[a:b, :]
            for (pr0, pr1, pc0, pc1) in _split(piece, depth + 1):
                parts.append((r0 + pr0, r0 + pr1, c0 + pc0, c0 + pc1))
        return parts
    return [(r0, r1, c0, c1)]


def _snap(length, width, pu, pv, depth):
    """Whole panels along a row (n), rows (m), and the size: snapped if that changes the area
    by less than SNAP_MAX_CHANGE, else the fitted size (snapped = False)."""
    from .layout import GAP_M
    n = max(1, round((length + GAP_M) / pu))
    m = max(1, round((width - depth) / pv) + 1)
    sl, sw = n * pu - GAP_M, depth + (m - 1) * pv
    ok = abs(sl * sw - length * width) <= SNAP_MAX_CHANGE * length * width
    return n, m, ((sl, sw) if ok else (length, width)), ok


def _merge(boxes):
    """Merge boxes (u0, u1, v0, v1) closer than MERGE_GAP_M when their joint box is not mostly empty."""
    def area(q):
        return (q[1] - q[0]) * (q[3] - q[2])
    boxes = [list(b) for b in boxes]
    merged = True
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                gap = max(max(a[0], b[0]) - min(a[1], b[1]), max(a[2], b[2]) - min(a[3], b[3]))
                joint = [min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3])]
                if gap <= MERGE_GAP_M and area(joint) <= (1 + MERGE_MAX_EMPTY) * (area(a) + area(b)):
                    boxes[i] = joint
                    del boxes[j]
                    merged = True
                    break
            if merged:
                break
    return boxes


def fit_rectangles(blob_mask, grid, roof_angle_deg, module, brightness=None):
    """Oriented rectangles for one blob of panel pixels.

    blob_mask: bool array on grid (the 0.1 m photo grid); roof_angle_deg: roof edge direction
    (roof_edge_angle); module: panel model (layout.Module); brightness: photo brightness on the
    same grid, to check the angle. Returns (rectangles, angle used). Each rectangle is a dict with
    corners (EPSG:25831, closed ring), angle_deg, length_m (along the rows), width_m, area_m2,
    panels_per_row, rows, panels_estimate, fill_share and snapped.
    """
    photo = photo_edge_angle(brightness, blob_mask) if brightness is not None else None
    angle = choose_angle(roof_angle_deg, photo)
    rows, cols = np.nonzero(blob_mask)
    if rows.size == 0:
        return [], angle
    res = grid.res
    x = grid.x0 + (cols + 0.5) * res
    y = grid.y1 - (rows + 0.5) * res
    t = math.radians(angle)
    ux, uy = math.cos(t), math.sin(t)
    u = x * ux + y * uy                            # along the rows
    v = -x * uy + y * ux                           # across the rows
    iu = np.floor((u - u.min()) / res).astype(int)
    iv = np.floor((v - v.min()) / res).astype(int)
    occ = np.zeros((iv.max() + 1, iu.max() + 1), bool)
    occ[iv, iu] = True
    occ = ndimage.binary_closing(occ, np.ones((3, 3)))   # fill the pinholes left by turning the pixels

    pu, pv = pitches(module)
    depth = pv - EXISTING_ROW_GAP_M
    boxes = []
    for r0, r1, c0, c1 in _split(occ):
        length, width = (c1 - c0) * res, (r1 - r0) * res
        if min(length, width) < 0.85 * depth or length * width < 0.85 * MIN_RECT_PANELS * module.area_m2:
            continue                               # room for at least MIN_RECT_PANELS panels, one row deep
        boxes.append([u.min() + c0 * res, u.min() + c1 * res, v.min() + r0 * res, v.min() + r1 * res])

    out = []
    for b0, b1, v0, v1 in _merge(boxes):
        # rows run along u (the photo's direction) whenever whole panels fit that way; only if they
        # don't, try the panels turned (rows along v, e.g. a strip one panel long and many panels deep)
        a = _snap(b1 - b0, v1 - v0, pu, pv, depth)                 # rows along u
        b = _snap(v1 - v0, b1 - b0, pu, pv, depth)                 # rows along v
        along_v = not a[3] and b[3]
        if along_v:
            n, m, (sw, sl), snapped = b
            row_angle = (angle + 90) % 180
        else:
            n, m, (sl, sw), snapped = a
            row_angle = angle
        cu, cv = (b0 + b1) / 2, (v0 + v1) / 2
        b0, b1, v0, v1 = cu - sl / 2, cu + sl / 2, cv - sw / 2, cv + sw / 2
        corners = [(uu * ux - vv * uy, uu * uy + vv * ux) for uu, vv in ((b0, v0), (b1, v0), (b1, v1), (b0, v1))]
        inside = (u >= b0) & (u <= b1) & (v >= v0) & (v <= v1)
        fill = inside.sum() * res * res / (sl * sw)
        if not snapped:                            # odd size (e.g. a steep single row): count by area instead
            n, m = max(1, round(sl * sw / (pu * pv))), 1
        if n * m < MIN_RECT_PANELS or fill < MIN_RECT_FILL:
            continue
        out.append({"corners": [[round(p, 2), round(q, 2)] for p, q in corners + [corners[0]]],
                    "angle_deg": round(row_angle, 1),
                    "length_m": round(sw if along_v else sl, 2), "width_m": round(sl if along_v else sw, 2),
                    "area_m2": round(sl * sw, 1), "panels_per_row": n, "rows": m, "panels_estimate": n * m,
                    "fill_share": round(float(min(fill, 1.0)), 2), "snapped": bool(snapped)})
    return out, angle


def rectangles_mask(rectangles, grid):
    """Cells of grid whose centre lies inside any rectangle."""
    out = np.zeros((grid.height, grid.width), bool)
    for r in rectangles:
        out |= grid.mask(Polygon(r["corners"]))
    return out
