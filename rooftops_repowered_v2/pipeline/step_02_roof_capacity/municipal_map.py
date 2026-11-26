# Ported from IAAC MaAI Team 1 V1: pipeline/step4/energy_map.py
# See V1_PROVENANCE.json for original source hash and revision.
"""Benchmark: the city's own solar potential for each roof (Barcelona Mapa d'Energia).

The Ajuntament's energy map (coneixement-eu.bcn.cat/mapaEnergia) shows solar PV,
solar thermal and mini-wind potential per roof. It was made around 2015 from
radiation, cartography and Catastro data (no LiDAR, no neighbour shade). We do
NOT use it to replace steps 2-4. We put its numbers next to ours, roof by roof.

How it works: the viewer keeps its data in CARTO, in a table called
"fotovoltaica". Its config.js names the CARTO SQL address and the public key the
viewer itself uses. This script reads config.js, then asks CARTO once for every
PV roof polygon around our blocks (data/energy_map/fotovoltaica.geojson) and
adds them up per Catastro plot. City fields (from the viewer's popup):

    radiacio    solar radiation on the roof        superficie  sunny roof area, m2
    superfici1  usable area, m2                    potencia_i  installable power, kW
    energia_ge  electricity generated, kWh/yr      est_emis_h  CO2 saved, kg/yr
    inversio_e  estimated investment, EUR          estalvi_ec  estimated saving, EUR/yr

    python -m step4.energy_map --discover            # show the CARTO address and the table's columns
    python -m step4.energy_map --address "Carrer del Bruc 59, Barcelona"
    python -m step4.energy_map data\\roof_test_set\\roof_test_set.csv --ranking data\\yield_all_v2\\ranking.csv --out data\\energy_map

With the roof test set, plot outlines are read from roof_test_set.geojson next to
the CSV, so every city polygon whose centre falls in a plot counts for that plot.
Without it, the roof's lat/lon point is used. Run again with --refresh to
download the city data again.
"""
import argparse
import csv
import json
import re
from pathlib import Path

import requests
import shapely
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

CONFIG_URL = "https://coneixement-eu.bcn.cat/mapaEnergia/js/config.js"
DEFAULT_OUT = Path("data/energy_map")
TABLE = "fotovoltaica"
SUM_FIELDS = ("superficie", "superfici1", "potencia_i", "energia_ge", "est_emis_h", "inversio_e", "cost_mante",
              "estalvi_ec")
HEADERS = {"User-Agent": "research-studio-solar-pipeline/1.0"}
TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:25831", always_xy=True)
MARGIN_DEG = 0.002   # about 200 m around the roofs


# ---------- where the data is ----------

def read_config(js_text):
    """SQL address, key and table names from the viewer's config.js."""
    def get(name):
        m = re.search(rf'var\s+{name}\s*=\s*"([^"]*)"', js_text)
        return m.group(1) if m else None
    sql_url = get("SQL_URL")
    if not sql_url:
        raise SystemExit("config.js has no SQL_URL: the viewer has changed. Paste config.js to Claude.")
    if sql_url.startswith("//"):
        sql_url = "https:" + sql_url
    return {"sql_url": sql_url, "api_key": get("API_KEY"),
            "tables": re.findall(r'TABLE_NAMES\[\d+\]\s*=\s*"([^"]+)"', js_text)}


def find_service(session=None, config_url=CONFIG_URL):
    s = session or requests.Session()
    r = s.get(config_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return read_config(r.text)


def sql(svc, query, fmt="geojson", session=None):
    s = session or requests.Session()
    data = {"q": query, "format": fmt}
    if svc.get("api_key"):
        data["api_key"] = svc["api_key"]
    r = s.post(svc["sql_url"], data=data, headers=HEADERS, timeout=120)
    if not r.ok:
        raise SystemExit(f"CARTO said {r.status_code}: {r.text[:300]}")
    return r.json()


def sample(svc, table=TABLE, session=None):
    rows = sql(svc, f"SELECT * FROM {table} LIMIT 1", "json", session).get("rows", [])
    return {k: v for k, v in rows[0].items() if k not in ("the_geom", "the_geom_webmercator")} if rows else {}


def download_polygons(svc, bbox, path, table=TABLE, session=None):
    """Every city PV polygon in bbox (min_lon, min_lat, max_lon, max_lat), saved as GeoJSON."""
    x0, y0, x1, y1 = bbox
    q = (f"SELECT * FROM {table} WHERE the_geom && "
         f"ST_MakeEnvelope({x0:.6f}, {y0:.6f}, {x1:.6f}, {y1:.6f}, 4326)")
    fc = sql(svc, q, "geojson", session)
    for f in fc.get("features", []):
        f["properties"].pop("the_geom_webmercator", None)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return fc


# ---------- adding up per roof ----------

def _number(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")   # 12.345,6 -> 12345.6
    try:
        return float(t.replace(",", "."))
    except ValueError:
        return None


class CityRoofs:
    """The city's PV polygons in EPSG:25831, ready to be added up per plot."""

    def __init__(self, fc):
        self.items = []
        for f in fc.get("features", []):
            if not f.get("geometry"):
                continue
            g = shapely.transform(shape(f["geometry"]), TO_UTM.transform, interleaved=False)
            self.items.append((g, g.representative_point(), f["properties"]))
        self.tree = STRtree([p for _, p, _ in self.items]) if self.items else None

    def in_area(self, area):
        """City polygons whose centre is inside `area` (a plot or building outline)."""
        if self.tree is None:
            return []
        return [self.items[i] for i in self.tree.query(area) if area.contains(self.items[i][1])]

    def at_point(self, pt, max_m=5.0):
        """Fallback without an outline: polygons containing the point (or within max_m)."""
        return [it for it in self.items if it[0].distance(pt) <= max_m]

    @staticmethod
    def total(items):
        out = {"city_polygons": len(items)}
        for k in SUM_FIELDS:
            vals = [v for v in (_number(p.get(k)) for _, _, p in items) if v is not None]
            out[k] = round(sum(vals), 1) if vals else None
        rad = [v for v in (_number(p.get("radiacio")) for _, _, p in items) if v is not None]
        out["radiacio"] = round(sum(rad) / len(rad), 1) if rad else None
        return out


def load_city(svc, out, bbox, refresh=False, session=None):
    path = Path(out) / f"{TABLE}.geojson"
    if path.exists() and not refresh:
        fc = json.loads(path.read_text(encoding="utf-8"))
    else:
        fc = download_polygons(svc, bbox, path, session=session)
        print(f"downloaded {len(fc.get('features', []))} city PV polygons -> {path}")
    return CityRoofs(fc)


def bbox_of(points_lonlat):
    lons, lats = zip(*points_lonlat)
    return min(lons) - MARGIN_DEG, min(lats) - MARGIN_DEG, max(lons) + MARGIN_DEG, max(lats) + MARGIN_DEG


