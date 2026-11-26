"""Download the handoff's eight core CSVs, preserving provenance and failures.

Python standard library + curl; no API keys. Run with the project's Python.
Raw files are published only after CSV validation. Reruns validate and reuse them.
"""
from __future__ import annotations

import argparse
import codecs
import concurrent.futures
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
KINDS = {
    'bcn_electricity_2025': 'OBSERVED_AGGREGATE',
    'bcn_municipal_pv_2025': 'OFFICIAL_INSTALLATION_REGISTER',
    'catalonia_energy_certificates': 'OFFICIAL_CERTIFICATE',
    'catalonia_self_consumption_registry': 'OFFICIAL_INSTALLATION_REGISTER',
    'catalonia_hourly_electricity_demand': 'OBSERVED_AGGREGATE',
    'bdg2_metadata': 'REFERENCE_BUILDING_METADATA',
    'bdg2_cleaned_electricity': 'OBSERVED_METER',
    'bdg2_weather': 'REFERENCE_WEATHER',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def sources():
    # The original handoff was renamed by the user; the supplement has no source manifest.
    candidates = [BASE / 'rooftops_repowered_v2_1_context.txt', BASE / 'rooftops_repowered_v2_context.txt']
    handoff_path = next((p for p in candidates if p.is_file()), None)
    if handoff_path is None:
        raise FileNotFoundError('Original V2/V2.1 handoff with section O source manifest is missing.')
    handoff = handoff_path.read_text(encoding='utf-8')
    section = handoff.split('O. ACTUAL SOURCE MANIFEST', 1)[1].split('P. APPENDIX', 1)[0]
    pattern = r'ID: (\S+)\s+LOCAL FILE: ([^\r\n]+)\s+DOWNLOAD URL: (\S+)\s+CATALOG: (\S+)\s+PURPOSE: ([^\r\n]+)\s+SIZE NOTE: ([^\r\n]+)'
    records = [dict(zip(('id', 'local_file', 'url', 'catalog', 'purpose', 'size_note'), m))
               for m in re.findall(pattern, section)]
    if len(records) != 8:
        raise ValueError(f'Expected eight source records; found {len(records)}')
    for record in records:
        record['provenance'] = KINDS[record['id']]
        record['format'] = 'CSV (publisher original; encoding and separator inspected after download)'
        record['license_status'] = 'Consult publisher metadata/license; public access does not imply unrestricted reuse'
    return records


def fetch(url, destination, log, timeout=3600):
    destination.parent.mkdir(parents=True, exist_ok=True)
    args = ['curl.exe', '--fail', '--location', '--silent', '--show-error',
            '--connect-timeout', '30', '--max-time', str(timeout),
            '--retry', '2', '--retry-delay', '3',
            '--user-agent', 'RoofscapesResearchDatasetDownloader/1.0',
            '--output', str(destination), '--write-out', '%{http_code}\n%{url_effective}\n%{size_download}', url]
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    with log.open('a', encoding='utf-8') as handle:
        handle.write(f'\n{now()} {url}\n{result.stdout}\n{result.stderr}\n')
    if result.returncode:
        raise RuntimeError(f'curl exit {result.returncode}: {result.stderr.strip()[-800:]}')
    lines = result.stdout.splitlines()
    return {'http_status': lines[0], 'resolved_url': lines[1]}


def inspect_csv(path):
    with path.open('rb') as handle:
        head = handle.read(65536)
    if not head:
        raise ValueError('Empty response')
    stripped = head.lstrip().lower()
    if stripped.startswith(b'version https://git-lfs.github.com/spec'):
        raise ValueError('Git LFS pointer, not data')
    if stripped.startswith((b'<!doctype', b'<html', b'<?xml', b'{', b'[')):
        raise ValueError('Response is HTML/XML/JSON, not CSV')
    encoding = 'utf-8-sig'
    try:
        sample = codecs.getincrementaldecoder(encoding)().decode(head, final=False)
    except UnicodeDecodeError:
        encoding = 'cp1252'
        sample = head.decode(encoding)
    # Infer from the header; wide meter files can exceed Sniffer's sample size.
    header_line = sample.splitlines()[0]
    delimiter = max((',', ';', '\t', '|'), key=header_line.count)
    if header_line.count(delimiter) == 0:
        raise ValueError('No multi-column CSV header found')
    csv.field_size_limit(10_000_000)
    with path.open(encoding=encoding, newline='') as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader)
        rows = 0
        inconsistent = 0
        for row in reader:
            if not row:
                continue
            rows += 1
            inconsistent += len(row) != len(header)
    if rows == 0 or inconsistent:
        raise ValueError(f'Invalid CSV: {rows} data rows, {inconsistent} inconsistent rows')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest(), 'encoding': encoding,
            'delimiter': delimiter, 'columns': header, 'row_count': rows,
            'column_count': len(header), 'validation': 'CSV structure only; units/missingness/timezones need data audit'}


def download(record, root):
    target = root / record['local_file']
    partial = target.with_suffix(target.suffix + '.part')
    log = root / 'logs' / f"{record['id']}.log"
    result = {**record, 'started_utc': now(), 'status': 'failed', 'attempts': []}
    print(f"START {record['id']}", flush=True)
    try:
        if target.exists():
            result.update(inspect_csv(target), status='existing_validated')
            return result
        urls = [record['url']]
        if 'raw.githubusercontent.com/' in record['url']:
            urls.append(record['url'].replace('raw.githubusercontent.com/', 'media.githubusercontent.com/media/'))
        if 'analisi.transparenciacatalunya.cat/' in record['url']:
            dataset_id = record['url'].split('/views/')[1].split('/')[0]
            metadata = root / 'metadata' / f"{record['id']}.json"
            try:
                fetch(f'https://analisi.transparenciacatalunya.cat/api/views/{dataset_id}.json', metadata, log, 120)
                info = json.loads(metadata.read_text(encoding='utf-8'))
                result['publisher_title'] = info.get('name')
                result['publisher_license_id'] = info.get('licenseId')
            except Exception as exc:
                result['metadata_warning'] = str(exc)
            urls.append(f'https://analisi.transparenciacatalunya.cat/api/views/{dataset_id}/rows.csv?accessType=DOWNLOAD')
        for url in urls:
            try:
                response = fetch(url, partial, log)
                details = inspect_csv(partial)
                partial.replace(target)
                result.update(response, **details, status='downloaded', downloaded_from=url)
                break
            except Exception as exc:
                result['attempts'].append({'url': url, 'error': str(exc)})
        if result['status'] == 'failed':
            result['error'] = 'All download candidates failed; see attempts and per-source log'
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        result['finished_utc'] = now()
        write_json(root / 'logs' / f"{record['id']}_report.json", result)
        print(f"{result['status'].upper()} {record['id']} {result.get('bytes', 0):,} bytes", flush=True)
    return result


def write_inventory(root, reports):
    """Small, readable index; full schemas and provenance remain in JSON reports."""
    fields = ['id', 'status', 'local_file', 'provenance', 'bytes', 'row_count',
              'column_count', 'encoding', 'delimiter', 'sha256', 'downloaded_from']
    with (root / 'dataset_inventory.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=BASE / 'datasets')
    parser.add_argument('--only', nargs='*', help='Retry selected source IDs')
    args = parser.parse_args()
    root = args.root.resolve()
    for directory in ('logs', 'metadata', 'raw', 'inputs', 'synthetic', 'processed',
                      'manual_exports/pvgis', 'manual_exports/barcelona_solar_map',
                      'manual_exports/emissions_tariffs', 'results'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (BASE / 'pipeline' / 'models').mkdir(parents=True, exist_ok=True)
    records = sources()
    write_json(root / 'dataset_sources.json', {'created_utc': now(), 'sources': records})
    selected = [r for r in records if not args.only or r['id'] in args.only]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda r: download(r, root), selected))
    reports = []
    for record in records:
        path = root / 'logs' / f"{record['id']}_report.json"
        if path.exists():
            reports.append(json.loads(path.read_text(encoding='utf-8')))
    write_json(root / 'logs/dataset_download_report.json', {'updated_utc': now(), 'datasets': reports})
    write_inventory(root, reports)
    successes = sum(r['status'] in ('downloaded', 'existing_validated') for r in reports)
    print(f'Validated {successes}/{len(records)} core CSVs. Report: {root / "logs/dataset_download_report.json"}', flush=True)
    return 0 if successes == len(records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
