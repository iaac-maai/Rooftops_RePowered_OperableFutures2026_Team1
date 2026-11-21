"""Fill the neighbours file from Catastro: real floor areas, and the homes around the host.

    python -m demand.catastro_fill --neighbours demand/neighbours_a160.csv --out demand/neighbours_a160_catastro.csv

One row of the neighbours file is one CONSUMER: a program with its own meter (or meters),
not a building. A cafe, a pharmacy, a supermarket, the flats of one building. Several rows
can sit in the same building (a cafe on the ground floor, flats above). In collective
self-consumption every meter joins on its own, so this is the right unit.

What this script does, for every row that has lat/lon:
1. asks Catastro which plot is there, and reads its buildings (use, flats, floors, footprint);
2. rows marked whole_building=yes (the host, a university building) get the Catastro floor
   area (footprint x floors). Other rows (a cafe, a shop in a bigger building) keep their
   estimate, because Catastro's open service does not give the area of one premises;
3. if the plot has flats, adds a "home" row for them (the flats above the cafe);
4. scans the streets around the host and adds the nearest residential buildings
   (--homes, at least --min-flats flats each);
5. with --close-radius 200: also adds every residential building with at least one flat
   inside that distance (small old houses count when the circle is small).

Needs internet and shapely (pip install shapely). Answers are cached in
data/catastro_cache.json, so a second run is fast. --offline uses only the cache: no
internet, nothing is downloaded; points that are not in the cache get no Catastro data.
"""
import argparse
import json
import math
import time
from pathlib import Path

import pandas as pd

CACHE = Path("data/catastro_cache.json")
FLOOR_FOR_PREMISES = 3          # buildings with 3+ floors: ground floor = shops, flats above
FLAT_M2_DEFAULT = 85.0
COLUMNS = ["id", "name", "role", "type", "floor_area_m2", "units", "annual_kwh", "hours_weekday",
           "hours_saturday", "hours_sunday", "closed_august", "whole_building", "address",
           "building_refcat", "distance_m", "lat", "lon", "area_source", "notes"]


def distance_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def scan_points(lat, lon, radius_m, step_m):
    """Grid of points inside a circle, nearest first."""
    dlat = step_m / 111320.0
    dlon = step_m / (111320.0 * math.cos(math.radians(lat)))
    n = int(radius_m // step_m)
    pts = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            p = (lat + i * dlat, lon + j * dlon)
            d = distance_m(lat, lon, *p)
            if d <= radius_m:
                pts.append((d, p))
    return [p for _, p in sorted(pts)]


def home_area(info):
    """Floor area used for the flats of one plot: flats x 85 m2 (an average Spanish flat).
    Household electricity follows the number of households more than the m2, and the
    Catastro area includes walls, stairs and the ground floor, so it would overstate use.
    Without a flat count: footprint x floors (minus the ground floor in buildings of 3+ floors)."""
    flats = info.get("dwellings") or 0
    if flats:
        return round(flats * FLAT_M2_DEFAULT)
    floors = info.get("floors") or 1
    res_floors = floors - 1 if floors >= FLOOR_FOR_PREMISES else floors
    return round(info.get("footprint_m2", 0) * max(res_floors, 1))


def short_address(address):
    """'CL PERE IV 81 BARCELONA (BARCELONA)' -> 'CL PERE IV 81'; 'RB POBLENOU 124 N2-126' -> 'RB POBLENOU 124 - 126'."""
    return address.replace(" BARCELONA (BARCELONA)", "").replace(" N2-", " - ").strip()


def home_row(info, lat, lon, host, note):
    return {"name": f"Homes at {short_address(info.get('address') or info['refcat'])}", "role": "neighbour", "type": "home",
            "floor_area_m2": home_area(info), "units": info["dwellings"], "address": info.get("address", ""),
            "building_refcat": info["refcat"], "lat": round(lat, 7), "lon": round(lon, 7),
            "distance_m": round(distance_m(host[0], host[1], lat, lon)),
            "area_source": "Catastro flats x 85 m2", "notes": note}


def fill(neighbours, lookup, radius_m=250, step_m=35, n_homes=5, min_flats=6, log=print, close_radius_m=0):
    """neighbours: DataFrame. lookup(lat, lon) -> plot info dict or None. Returns a new DataFrame."""
    df = neighbours.copy()
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df.astype(object).where(df.notna(), "")
    hosts = df[df["role"].astype(str).str.lower() == "host"]
    if hosts.empty:
        raise ValueError("The neighbours file needs one row with role=host (and its lat/lon).")
    host = (float(hosts.iloc[0]["lat"]), float(hosts.iloc[0]["lon"]))

    seen_home_plots = set(df.loc[df["type"] == "home", "building_refcat"].astype(str))
    new_rows = []
    for i, r in df.iterrows():
        if str(r["lat"]).strip() == "" or str(r["lon"]).strip() == "":
            continue
        info = lookup(float(r["lat"]), float(r["lon"]))
        if not info:
            log(f"{r['id']}: Catastro found nothing at this point")
            continue
        df.at[i, "building_refcat"] = info["refcat"]
        df.at[i, "distance_m"] = round(distance_m(host[0], host[1], float(r["lat"]), float(r["lon"])))
        whole = str(r["whole_building"]).strip().lower() in ("yes", "y", "true", "1")
        if whole and info.get("gross_m2"):
            df.at[i, "floor_area_m2"] = round(info["gross_m2"])
            df.at[i, "area_source"] = f"Catastro (footprint x {info.get('floors')} floors)"
        log(f"{r['id']}: plot {info['refcat']}, use {info.get('use')}, {info.get('dwellings') or 0} flats, "
            f"{info.get('floors')} floors, plot floor area {info.get('gross_m2')} m2"
            + (" -> used" if whole else " (not used: the program is only part of the plot)"))
        if r["type"] != "home" and (info.get("dwellings") or 0) > 0 and info["refcat"] not in seen_home_plots:
            new_rows.append(home_row(info, float(r["lat"]), float(r["lon"]), host,
                                     f"Flats in the same building as {r['name']}"))
            seen_home_plots.add(info["refcat"])

    added = 0
    plots_seen = set(df["building_refcat"].astype(str)) | seen_home_plots
    for lat, lon in scan_points(host[0], host[1], radius_m, step_m):
        if added >= n_homes:
            break
        info = lookup(lat, lon)
        if not info or info["refcat"] in plots_seen:
            continue
        plots_seen.add(info["refcat"])
        if (info.get("dwellings") or 0) >= min_flats and "resid" in str(info.get("use", "")).lower():
            new_rows.append(home_row(info, lat, lon, host, "Residential building near the host (Catastro scan)"))
            added += 1
    close = 0
    if close_radius_m:                    # every home very close to the host, even a single flat
        for lat, lon in scan_points(host[0], host[1], close_radius_m, step_m):
            info = lookup(lat, lon)
            if not info or info["refcat"] in seen_home_plots or info["refcat"] in {r["building_refcat"] for r in new_rows}:
                continue
            if (info.get("dwellings") or 0) >= 1 and "resid" in str(info.get("use", "")).lower():
                new_rows.append(home_row(info, lat, lon, host,
                                         f"Residential building within {close_radius_m:.0f} m of the host (Catastro scan)"))
                close += 1
    log(f"added {len(new_rows)} home rows ({added} from the scan around the host, {close} within the close radius)")

    homes = pd.DataFrame(new_rows, columns=[c for c in COLUMNS if c != "id"])
    taken = {str(x) for x in df["id"]}
    ids, k = [], 1
    for _ in range(len(homes)):
        while f"H{k:02d}" in taken:
            k += 1
        ids.append(f"H{k:02d}")
        taken.add(ids[-1])
    homes.insert(0, "id", ids)
    out = pd.concat([df[COLUMNS], homes[COLUMNS]], ignore_index=True)
    return out


def catastro_lookup(cache_path=CACHE, pause=0.15, offline=False):
    """lookup(lat, lon) using the team's step1.catastro module, with a JSON cache.
    offline=True: answer only from the cache (no internet); unknown points give None."""
    if not offline:
        from step1 import catastro                 # needs requests + shapely
    cache_path = Path(cache_path)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    points, plots = cache.setdefault("points", {}), cache.setdefault("plots", {})

    def save():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    def lookup(lat, lon):
        key = f"{lat:.6f},{lon:.6f}"
        if offline and (key not in points or points[key].get("refcat") and points[key]["refcat"] not in plots):
            return None
        if key not in points:
            try:
                plot = catastro.refcat_from_point(lat, lon)
                points[key] = {"refcat": plot["refcat"], "address": plot.get("address") or ""}
            except Exception as e:                 # no plot here (a street), or the service failed
                points[key] = {"refcat": None, "error": str(e)[:120]}
            time.sleep(pause)
        p = points[key]
        if not p.get("refcat"):
            return None
        ref = p["refcat"]
        if ref not in plots:
            try:
                buildings, parts = catastro.buildings_for_refcat(ref)
                fps = [b["footprint"] for b in buildings if b["footprint"] is not None]
                main = max(buildings, key=lambda b: b["footprint"].area)
                floors = [x["floors_above_ground"] for x in parts if x["floors_above_ground"]]
                fp = sum(f.area for f in fps)
                plots[ref] = {"use": main["current_use"], "dwellings": sum(b["dwellings"] or 0 for b in buildings),
                              "floors": max(floors) if floors else None, "footprint_m2": round(fp, 1),
                              "gross_m2": round(fp * (max(floors) if floors else 1), 1),
                              "year": main["year_built"]}
            except Exception as e:
                plots[ref] = {"error": str(e)[:120]}
            time.sleep(pause)
            save()
        info = plots[ref]
        if "error" in info:
            return None
        return {"refcat": ref, "address": p.get("address", ""), **info}

    lookup.save = save
    return lookup


def main():
    ap = argparse.ArgumentParser(description="Catastro areas for the neighbours, plus the homes around the host")
    ap.add_argument("--neighbours", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius", type=float, default=250, help="metres around the host to look for homes")
    ap.add_argument("--homes", type=int, default=5, help="how many residential buildings to add from the scan")
    ap.add_argument("--min-flats", type=int, default=6)
    ap.add_argument("--close-radius", type=float, default=0,
                    help="also add every residential building (even 1 flat) within this many metres")
    ap.add_argument("--offline", action="store_true", help="use only data/catastro_cache.json (no internet)")
    a = ap.parse_args()
    df = pd.read_csv(a.neighbours, dtype=str).fillna("")
    lookup = catastro_lookup(offline=a.offline)
    out = fill(df, lookup, a.radius, 35, a.homes, a.min_flats, close_radius_m=a.close_radius)
    if not a.offline:
        lookup.save()
    out.to_csv(a.out, index=False)
    print(out[["id", "name", "type", "floor_area_m2", "units", "distance_m", "area_source"]].to_string(index=False))
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
