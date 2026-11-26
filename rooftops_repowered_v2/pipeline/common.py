"""Project-relative configuration, reproducibility and input validation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class InputError(ValueError):
    """An input is missing or unsuitable; include an actionable explanation."""


def now():
    return datetime.now(timezone.utc).isoformat()


def load_config(path=None):
    source = Path(path) if path else ROOT / 'config/project.json'
    cfg = json.loads(source.read_text(encoding='utf-8'))
    cfg['_config_path'] = str(source.resolve())
    return cfg


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def directory(cfg, name):
    path = resolve(cfg['paths'][name])
    path.mkdir(parents=True, exist_ok=True)
    return path


def require_file(path):
    path = Path(path)
    if not path.is_file():
        raise InputError(f'Missing input: {path}. See README.md and reports/NEXT_STEPS.md.')
    return path


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def sha256(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def require_columns(frame, columns, label):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise InputError(f'{label}: missing columns {sorted(missing)}')
