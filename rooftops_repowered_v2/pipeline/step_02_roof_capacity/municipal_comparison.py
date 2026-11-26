"""Compare a separately sourced municipal potential map; never add capacities."""
from datetime import date
import json
import pandas as pd

from pipeline.common import InputError, ROOT, require_file, resolve
from .adapter import completion_cutoff, load_geometry
from .municipal_map import CityRoofs


def compare(settings_path, polygons_path, source_date, source_url, output):
    if not source_url:
        raise InputError('Municipal comparison needs its publisher source URL.')
    vintage = date.fromisoformat(source_date)
    settings = json.loads(require_file(resolve(settings_path)).read_text(encoding='utf-8'))
    footprint = load_geometry(settings['footprint_path'], settings['footprint_crs'])
    data = json.loads(require_file(resolve(polygons_path)).read_text(encoding='utf-8'))
    city = CityRoofs(data)
    matched = city.in_area(footprint)
    totals = city.total(matched)
    result = {'building_id': settings['building_id'], 'municipal_source_date': source_date,
              'source_url': source_url, 'data_origin': 'ESTIMATED_ROOF',
              'municipal_potential_kw_source': totals['potencia_i'],
              'municipal_usable_area_m2': totals['superfici1'], 'matched_polygons': totals['city_polygons'],
              'municipal_modeled_generation_kwh_year': totals['energia_ge'],
              'post_completion_vintage': vintage > completion_cutoff(settings),
              'record_dates_are_survey_dates': False,
              'current_roof_validation_eligible': vintage > completion_cutoff(settings),
              'matched_record_ids': '|'.join(str(p.get('cartodb_id')) for _, _, p in matched),
              'source_created_dates': '|'.join(sorted({str(p.get('created_at')) for _, _, p in matched})),
              'source_updated_dates': '|'.join(sorted({str(p.get('updated_at')) for _, _, p in matched})),
              'comparison_only': True, 'combined_capacity_kwp': None,
              'notes': 'Representative-point geometry association, not a cadastral parcel join. Record timestamps do not establish survey dates. Pre-2022 map records describe legacy geometry and cannot validate modern A160. Never sum city potential with V1/V2 panel estimates.'}
    target = resolve(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([result]).to_csv(target, index=False)
    return result
