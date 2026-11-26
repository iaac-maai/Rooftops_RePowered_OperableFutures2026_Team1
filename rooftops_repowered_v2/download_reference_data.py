"""Cache publisher metadata and obtain Barcelona's optional cadastral buildings.

The other optional sources need a selected area, archetype or accounting year.
They are recorded as pending rather than replaced with arbitrary example data.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from download_datasets import BASE, fetch, now, write_json


ROOT = BASE / 'datasets'
ATOM = {'a': 'http://www.w3.org/2005/Atom'}


def cache(url, relative):
    path = ROOT / relative
    response = fetch(url, path, ROOT / 'logs/reference_downloads.log', 600)
    print(f'CACHED {relative}', flush=True)
    return path, response


def main():
    results = []
    for name, url, filename in [
        ('bdg2_license', 'https://raw.githubusercontent.com/buds-lab/building-data-genome-project-2/master/LICENSE', 'metadata/bdg2_LICENSE.txt'),
        ('bdg2_readme', 'https://raw.githubusercontent.com/buds-lab/building-data-genome-project-2/master/README.md', 'metadata/bdg2_README.md'),
        ('bcn_electricity_catalog', 'https://opendata-ajuntament.barcelona.cat/data/api/3/action/package_show?id=consum-electricitat-bcn', 'metadata/barcelona_electricity_catalog.json'),
        ('bcn_municipal_pv_catalog', 'https://opendata-ajuntament.barcelona.cat/data/api/3/action/package_show?id=plaques-fotovoltaiques', 'metadata/barcelona_municipal_pv_catalog.json'),
    ]:
        try:
            path, response = cache(url, filename)
            if path.suffix == '.json':
                info = json.loads(path.read_text(encoding='utf-8'))
                if not info.get('success'):
                    raise ValueError('CKAN catalog did not return success')
            results.append({'id': name, 'url': url, 'file': filename, 'status': 'downloaded', **response})
        except Exception as exc:
            results.append({'id': name, 'url': url, 'status': 'failed', 'error': str(exc)})
    try:
        url = 'https://www.catastro.hacienda.gob.es/INSPIRE/buildings/ES.SDGC.BU.atom.xml'
        path, _ = cache(url, 'metadata/cadastre_buildings_spain.atom.xml')
        feed = ET.parse(path)
        candidates = [e for e in feed.findall('a:entry', ATOM)
                      if 'BARCELONA' in (e.findtext('a:title', '', ATOM)).upper()]
        if len(candidates) != 1:
            raise ValueError(f'Expected one Barcelona provincial feed; found {len(candidates)}')
        links = candidates[0].findall('a:link', ATOM)
        url = next(link.attrib['href'] for link in links if 'atom' in link.attrib.get('type', ''))
        path, _ = cache(url, 'metadata/cadastre_buildings_barcelona.atom.xml')
        feed = ET.parse(path)
        candidates = [e for e in feed.findall('a:entry', ATOM)
                      if 'BARCELONA' in e.findtext('a:title', '', ATOM).upper()]
        # Province feed has one entry per municipality: select city by its title,
        # not neighbouring municipalities with similar place names.
        candidates = [e for e in candidates
                      if e.findtext('a:title', '', ATOM).strip().upper()
                      in ('08900-BARCELONA BUILDINGS', 'BARCELONA')]
        if len(candidates) != 1:
            raise ValueError(f'Expected one Barcelona municipality; found {len(candidates)}. Inspect cached feed.')
        entry = candidates[0]
        url = next(link.attrib['href'] for link in entry.findall('a:link', ATOM)
                   if '.zip' in link.attrib.get('href', '').lower())
        filename = 'raw/cadastre_barcelona/barcelona_buildings.gml.zip'
        path, response = cache(url, filename)
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f'Corrupt ZIP member: {bad}')
            members = archive.namelist()
            if not any(name.endswith('.gml') for name in members):
                raise ValueError('Archive has no GML building data')
        results.append({'id': 'cadastre_barcelona_buildings', 'status': 'downloaded',
                        'provenance': 'OFFICIAL_GEO', 'url': url, 'file': filename,
                        'format': 'Publisher ZIP containing INSPIRE GML', 'members': members,
                        'publisher_updated': entry.findtext('a:updated', '', ATOM),
                        'publisher_rights': entry.findtext('a:rights', '', ATOM), **response})
    except Exception as exc:
        results.append({'id': 'cadastre_barcelona_buildings', 'status': 'failed', 'error': str(exc)})
    write_json(ROOT / 'logs/reference_download_report.json', {'updated_utc': now(), 'references': results})
    for result in results:
        print(result['id'], result['status'], result.get('error', ''), flush=True)


if __name__ == '__main__':
    main()
