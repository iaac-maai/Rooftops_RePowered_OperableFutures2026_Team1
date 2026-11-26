"""Streaming structural/missingness audit of the eight original core datasets."""
import json
import numpy as np
import pandas as pd

from pipeline.common import directory, now, require_file, sha256, write_json

TIME_COLUMNS = {
    'bcn_electricity_2025': 'Data',
    'catalonia_hourly_electricity_demand': 'DATA',
    'bdg2_cleaned_electricity': 'timestamp',
    'bdg2_weather': 'timestamp',
}


def run(cfg):
    root = directory(cfg, 'datasets')
    out = directory(cfg, 'reports') / 'data_audit'
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(require_file(root / 'dataset_sources.json').read_text(encoding='utf-8'))
    summary, fields, issues = [], [], []
    for source in manifest['sources']:
        sid = source['id']
        path = root / source['local_file']
        print(f'AUDIT {sid}', flush=True)
        if not path.is_file():
            summary.append({'source_id': sid, 'status': 'missing', 'path': str(path)})
            issues.append(f'{sid}: file missing; rerun download_datasets.py --only {sid}.')
            continue
        recorded = root / 'logs' / f'{sid}_report.json'
        info = json.loads(recorded.read_text(encoding='utf-8')) if recorded.exists() else {}
        encoding, sep = info.get('encoding', 'utf-8-sig'), info.get('delimiter', ',')
        count = 0
        nulls = None
        numeric_min, numeric_max, negative, zeros = {}, {}, {}, {}
        times = []
        invalid_times = 0
        time_col = TIME_COLUMNS.get(sid)
        meter = sid == 'bdg2_cleaned_electricity'
        try:
            for chunk in pd.read_csv(path, encoding=encoding, sep=sep, dtype=str,
                                     chunksize=500 if meter else 20000):
                count += len(chunk)
                missing = chunk.isna() | chunk.eq('')
                n = missing.sum()
                nulls = n if nulls is None else nulls.add(n, fill_value=0)
                if time_col:
                    ts = pd.to_datetime(chunk[time_col], errors='coerce',
                                        dayfirst=sid == 'catalonia_hourly_electricity_demand')
                    invalid_times += int(ts.isna().sum())
                    times.extend(ts.dropna().tolist())
                if meter:
                    values = chunk.drop(columns='timestamp').apply(pd.to_numeric, errors='coerce')
                    for col in values:
                        v = values[col]
                        numeric_min[col] = min(numeric_min.get(col, np.inf), v.min(skipna=True)) if v.notna().any() else numeric_min.get(col, np.inf)
                        numeric_max[col] = max(numeric_max.get(col, -np.inf), v.max(skipna=True)) if v.notna().any() else numeric_max.get(col, -np.inf)
                        negative[col] = negative.get(col, 0) + int(v.lt(0).sum())
                        zeros[col] = zeros.get(col, 0) + int(v.eq(0).sum())
            digest = sha256(path)
            hash_ok = not info.get('sha256') or digest == info['sha256']
            if not hash_ok:
                issues.append(f'{sid}: checksum differs from downloaded original; inspect before use.')
            for col, n in nulls.items():
                fields.append({'source_id': sid, 'column': col, 'rows': count,
                               'missing_count': int(n), 'missing_fraction': float(n / count) if count else None,
                               'numeric_min': numeric_min.get(col), 'numeric_max': numeric_max.get(col),
                               'negative_count': negative.get(col), 'zero_count': zeros.get(col),
                               'provenance': source['provenance']})
            summary.append({'source_id': sid, 'status': 'audited' if hash_ok else 'checksum_mismatch',
                            'rows': count, 'columns': len(nulls), 'bytes': path.stat().st_size,
                            'missing_cells': int(nulls.sum()), 'encoding': encoding, 'separator': sep,
                            'timestamp_column': time_col, 'invalid_timestamps': invalid_times,
                            'timestamp_start': str(min(times)) if times else None,
                            'timestamp_end': str(max(times)) if times else None,
                            'sha256': digest, 'provenance': source['provenance'], 'catalog': source['catalog']})
        except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
            summary.append({'source_id': sid, 'status': 'invalid', 'error': str(exc)})
            issues.append(f'{sid}: {exc}')
    pd.DataFrame(summary).to_csv(root / 'processed/data_quality_report.csv', index=False)
    pd.DataFrame(fields).replace([np.inf, -np.inf], np.nan).to_csv(out / 'column_quality.csv', index=False)
    write_json(out / 'audit_summary.json', {'created_utc': now(), 'sources': summary, 'issues': issues,
                                          'scope': 'Full CSV scan, null counts, timestamp coverage, meter sign/range and hashes. Not a legal/license or measurement-accuracy certification.'})
    notes = ['# Dataset audit', '', *[f"- {r['source_id']}: {r['status']}; {r.get('rows', '?'):,} rows." if isinstance(r.get('rows'), int) else f"- {r['source_id']}: {r['status']}" for r in summary],
             '', '## Interpretation', '',
             '- BDG2 cleaned electricity is hourly kWh in site-local wall time. Missing readings remain missing, never zero-filled.',
             '- Cleaned BDG2 labels are publisher-filtered observations; their coverage is not raw meter completeness.',
             '- Aggregate Catalonia/Barcelona data and certificates are not building-level hourly training targets.',
             '- The downloaded Barcelona 2025 consumption file ends November 30; do not treat it as a complete annual total.',
             '- Catalonia demand uses one date row with H01–H25 columns; inspect DST conventions before reshaping.',
             '- BDG2 has no observed hourly occupancy schedules. Manual scenario schedules remain external assumptions.',
             '- See column_quality.csv for field names, missingness and electricity meter ranges.',
             '', '## Issues', '', *[f'- {issue}' for issue in issues]]
    (out / 'README.md').write_text('\n'.join(notes) + '\n', encoding='utf-8')
    if issues:
        from pipeline.common import InputError
        raise InputError('Dataset audit needs attention: ' + '; '.join(issues))
    return summary
