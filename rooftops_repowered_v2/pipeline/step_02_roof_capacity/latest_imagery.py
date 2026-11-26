"""Check capture metadata at A160, including ICGC's provisional/current layers."""
import json

from pipeline.common import ROOT, now, write_json
from .acquisition import SourceSession


def run():
    raw = ROOT / 'datasets/raw/roof_capacity/A160/source_probes'
    source = json.loads((ROOT / 'reports/roof_capacity/A160/rooftop_sources.json').read_text())
    session = SourceSession(raw / 'latest_layer_responses')
    results = []
    for layer in ('ortofoto_color_provisional', 'ortofoto_color_vigent', 'ortofoto_color_2025'):
        params = {'SERVICE': 'WMS', 'VERSION': '1.1.1', 'REQUEST': 'GetFeatureInfo',
            'LAYERS': layer, 'QUERY_LAYERS': layer, 'STYLES': '', 'SRS': 'EPSG:25831',
            'BBOX': ','.join(map(str, source['ortho_bbox_25831'])),
            'WIDTH': 774, 'HEIGHT': 940, 'X': 387, 'Y': 470, 'INFO_FORMAT': 'text/html'}
        response = session.get('https://geoserveis.icgc.cat/servei/catalunya/orto-territorial/wms', params=params, timeout=60)
        response.raise_for_status()
        (raw / f'{layer}_latest_feature_info.txt').write_bytes(response.content)
        results.append({'layer': layer, 'feature_info': response.text})
    params.update(REQUEST='GetMap', LAYERS='ortofoto_color_provisional', FORMAT='image/png')
    for key in ('QUERY_LAYERS', 'X', 'Y', 'INFO_FORMAT'):
        params.pop(key, None)
    response = session.get('https://geoserveis.icgc.cat/servei/catalunya/orto-territorial/wms', params=params, timeout=90)
    response.raise_for_status()
    (raw / 'A160_provisional_2026.png').write_bytes(response.content)
    report = {'checked_utc': now(), 'location': 'A160 image centre', 'layers': results, 'sources': session.records}
    write_json(ROOT / 'reports/roof_capacity/A160/latest_imagery_check.json', report)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    run()
