import hashlib
import json
from pathlib import Path
import joblib


def test_trained_artifacts_are_unchanged_and_old_baseline_pickles_load():
    report = json.loads(Path('reports/integration/folder_migration.json').read_text())
    for name, before in report['model_artifact_sha256_before'].items():
        path = Path(name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        joblib.load(path)
    assert Path('pipeline/models').is_dir()
    for old, new in report['folders'].items():
        assert Path('pipeline', new).is_dir()
        assert not Path('pipeline', old).exists()
