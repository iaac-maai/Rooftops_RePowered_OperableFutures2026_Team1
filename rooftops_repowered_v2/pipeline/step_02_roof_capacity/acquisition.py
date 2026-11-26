"""Cache V1 public building lookup as a candidate, never as verified as-built QA."""
from hashlib import sha256 as digest
import json

from pyproj import Transformer
import requests
from shapely.geometry import Point
import unicodedata
import re

from pipeline.common import InputError, ROOT, now, require_file, resolve, write_json
from . import catastro, geocode
from .adapter import write_geojson


class SourceSession(requests.Session):
    def __init__(self, cache):
        super().__init__()
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.records = []
        self.headers['User-Agent'] = 'Roofscapes-RePowered-Research/0.2'

    def get(self, url, **kwargs):
        try:
            response = super().get(url, **kwargs)
            name = f'{len(self.records):02d}_{digest(response.url.encode()).hexdigest()[:12]}'
            raw = self.cache / f'{name}.response'
            raw.write_bytes(response.content)
            self.records.append({'url': response.url, 'retrieved_utc': now(), 'status': response.status_code,
                                 'sha256': digest(response.content).hexdigest(), 'cache': str(raw)})
            return response
        except requests.RequestException as exc:
            self.records.append({'url': url, 'retrieved_utc': now(), 'error': str(exc)})
            raise


def address_compatible(expected, actual):
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKD', value or '').upper() if not unicodedata.combining(c))
    expected, actual = normalize(expected), normalize(actual)
    number = re.search(r'\b(\d+)\b', expected)
    # A160 lookup is deliberately stricter than V1's "take the largest parcel building" fallback.
    return bool(number and re.search(rf'\b0*{number.group(1)}\b', actual) and 'ALMOG' in actual)


def fetch_building(settings_path='config/roof_capacity.json'):
    settings = json.loads(require_file(resolve(settings_path)).read_text(encoding='utf-8'))
    root = ROOT / 'datasets/raw/roof_capacity' / settings['building_id'] / 'building_lookup'
    report = ROOT / 'reports/roof_capacity' / settings['building_id'] / 'building_lookup.json'
    session = SourceSession(root)
    result = {'building_id': settings['building_id'], 'status': 'blocked', 'sources': session.records,
              'geometry_verified_current': False, 'data_origin': 'OFFICIAL_GEO'}
    try:
        hit = geocode.geocode(settings['address'], session, settings.get('search_bounds_wgs84'))
        result['geocoder_candidate'] = hit
        plot = catastro.refcat_from_point(hit['lat'], hit['lon'], session)
        result['cadastral_candidate'] = plot
        buildings, _ = catastro.buildings_for_refcat(plot['refcat'], session)
        point = Point(*Transformer.from_crs(4326, 25831, always_xy=True).transform(hit['lon'], hit['lat']))
        matching = [b for b in buildings if b['footprint'].covers(point)]
        candidate_path = root / 'parcel_building_candidates.geojson'
        write_geojson(candidate_path, [b['footprint'] for b in buildings],
                      [{'building_id': b['id'], 'year_built': b['year_built'], 'data_origin': 'OFFICIAL_GEO',
                        'verified_as_built': False} for b in buildings])
        if len(matching) != 1 or not address_compatible(settings['address'], plot.get('address')):
            raise InputError(f'Address/point did not identify exactly one matching building. Inspect {candidate_path}; no largest-building fallback is used.')
        building = matching[0]
        target = resolve(settings['footprint_path'])
        if target.exists():
            raise InputError(f'Candidate exists at {target}; refusing to overwrite user-reviewed geometry.')
        target.parent.mkdir(parents=True, exist_ok=True)
        write_geojson(target, [building['footprint']], [{'building_id': settings['building_id'], 'refcat': plot['refcat'],
                       'source_building_id': building['id'], 'year_built': building['year_built'],
                       'geometry_verified_current': False, 'data_origin': 'OFFICIAL_GEO'}])
        result.update(status='candidate_requires_review', footprint=str(target), refcat=plot['refcat'],
                      cadastral_year_built=building['year_built'],
                      warning='Public cadastral candidate only. Confirm A160 current geometry against post-construction plans/imagery before enabling capacity estimation.')
        return result
    except (requests.RequestException, catastro.CatastroError, geocode.GeocodeError, ValueError, OSError) as exc:
        result['blocker'] = str(exc)
        raise InputError(f'Public building lookup blocked: {exc}. Raw source responses are cached under {root}.') from exc
    finally:
        write_json(report, result)
