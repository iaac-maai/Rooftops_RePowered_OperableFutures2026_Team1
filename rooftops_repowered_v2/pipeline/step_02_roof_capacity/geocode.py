# Ported from IAAC MaAI Team 1 V1: pipeline/step1/geocode.py
# See V1_PROVENANCE.json for original source hash and revision.
"""Turn an address typed by the owner into a point (latitude, longitude).

Two geocoders are tried in order:
1. ICGC geocoder (Catalan mapping institute): best with Catalan street names.
2. Nominatim (OpenStreetMap): fallback.

If the owner taps the building on a map instead, skip this module and pass the
point straight to the next step.
"""
import requests

ICGC_URL = "https://eines.icgc.cat/geocodificador/cerca"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "rooftop-solar-studio/0.1 (student project)"
TIMEOUT = 20


class GeocodeError(Exception):
    pass


def geocode_icgc(address, session=None):
    r = (session or requests).get(ICGC_URL, params={"text": address, "size": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    features = r.json().get("features", [])
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"][:2]
    label = features[0].get("properties", {}).get("etiqueta") or features[0].get("properties", {}).get("label")
    return {"lat": lat, "lon": lon, "label": label, "source": "ICGC"}


def geocode_nominatim(address, session=None, bounds=None):
    params = {"q": address, "format": "json", "limit": 1, "countrycodes": "es"}
    if bounds:
        west, south, east, north = bounds
        params.update(viewbox=f'{west},{north},{east},{south}', bounded=1)
    r = (session or requests).get(
        NOMINATIM_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    results = r.json()
    if not results:
        return None
    return {
        "lat": float(results[0]["lat"]),
        "lon": float(results[0]["lon"]),
        "label": results[0].get("display_name"),
        "source": "Nominatim",
    }


def geocode(address, session=None, bounds=None):
    """Return {lat, lon, label, source} for an address, or raise GeocodeError."""
    errors = []
    for fn in (geocode_icgc, geocode_nominatim):
        try:
            hit = fn(address, session, bounds) if fn is geocode_nominatim else fn(address, session)
            if hit:
                if bounds and not (bounds[0] <= hit['lon'] <= bounds[2] and bounds[1] <= hit['lat'] <= bounds[3]):
                    errors.append(f'{fn.__name__}: candidate outside the declared Barcelona search area')
                    continue
                return hit
            errors.append(f"{fn.__name__}: no result")
        except (requests.RequestException, KeyError, ValueError) as e:
            errors.append(f"{fn.__name__}: {e}")
    raise GeocodeError(f"Could not find '{address}'. " + "; ".join(errors))
