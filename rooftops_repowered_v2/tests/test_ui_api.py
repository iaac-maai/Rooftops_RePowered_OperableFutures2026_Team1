"""Read-only UI boundaries: real provenance, null unknowns and allowlisted reads."""
from copy import deepcopy
import hashlib
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from ui.data import RepositoryData, ROOT, SourceUnavailable, safe_text, safe_url
from ui.server import make_server


def test_real_scenarios_model_metrics_and_generation_roles():
    result=RepositoryData().dashboard()
    roof=result['roof']
    assert roof['installed_capacity_kwp'] is None and roof['installed_capacity_verified'] is False
    for assessment,expected in [('retrospective',[95.34,110.88,116.76]),('additional',[0,1.26,1.26])]:
        rows=roof['assessments'][assessment]['scenarios']
        assert [row['estimated_kwp'] for row in rows]==expected
        assert all(row['unit']=='kWp' and row['evidence_state']=='PROVISIONAL_ESTIMATE' for row in rows)
        assert roof['assessments'][assessment]['provenance'][0]['sha256']
    assert result['reference']['pre_installation_source_independence'] is False
    assert result['reference']['municipal_comparison']['current_roof_validation_eligible'] is False
    model=result['model']
    assert model['real_building_accuracy_validated'] is False
    assert model['training_origin']=='SIMULATED_PHYSICS'
    metric=next(row for row in model['metrics'] if row['model']=='office_energyplus_xgboost' and row['split']=='test')
    assert metric['mae_kwh']==pytest.approx(.6480661087936059)
    assert result['buildings']['buildings'][0]['existing_pv_status']=='visually_confirmed_specifications_unverified'
    for stage in ('pvgis','demand','sharing','impact'):
        assert result[stage]['state']=='pending' and result[stage]['results'] is None
    serialized=json.dumps(result)
    assert str(ROOT) not in serialized and 'C:\\Users' not in serialized
    assert 'credential.xml' not in serialized and 'X-Goog-Api-Key' not in serialized


def test_missing_files_never_fabricate_results(tmp_path):
    result=RepositoryData(tmp_path).dashboard()
    assert result['roof']['state']=='partial'
    assert result['roof']['assessments']['retrospective']['state']=='pending'
    for key in ('buildings','model','reference'):
        assert result[key]['state']=='pending'
    assert result['roof']['installed_capacity_kwp'] is None


@pytest.mark.parametrize('invalid',['duplicate','nan','assessment','count'])
def test_corrupt_source_is_pending(monkeypatch,invalid):
    repository=RepositoryData()
    original=repository.read
    rows=deepcopy(original('retrospective'))
    if invalid=='duplicate': rows[0]['scenario']='base'
    elif invalid=='nan': rows[0]['estimated_kwp']='nan'
    elif invalid=='assessment': rows[0]['assessment']='additional'
    else: rows[0]['panel_count']='1'
    monkeypatch.setattr(repository,'read',lambda key:rows if key=='retrospective' else original(key))
    result=repository.scenarios()['assessments']['retrospective']
    assert result['state']=='pending' and result['results'] is None


def test_allowlist_and_path_redaction(tmp_path,monkeypatch):
    repository=RepositoryData(tmp_path)
    with pytest.raises(ValueError): repository.read('../../config/project.json')
    (tmp_path/'outside.csv').write_text('private')
    inside=tmp_path/'inner';inside.mkdir()
    from ui.data import SOURCES
    monkeypatch.setitem(SOURCES,'buildings','../outside.csv')
    with pytest.raises(SourceUnavailable): RepositoryData(inside).read('buildings')
    assert safe_url('file:///C:/Users/private') is None
    assert safe_url('https://user:password@example.com') is None
    assert safe_url('https://example.com')=='https://example.com'
    assert 'private' not in safe_text('C:\\Users\\private\\secret')


def test_map_roles_and_public_properties(monkeypatch):
    repository=RepositoryData();original=repository.read
    def with_private_property(key):
        source=deepcopy(original(key))
        for feature in source['features']:
            feature['properties']['cache_path']='C:\\Users\\private'
        return source
    monkeypatch.setattr(repository,'read',with_private_property)
    result=repository.map('additional','base')
    assert result['crs']=='EPSG:4326' and result['observed_reference_included'] is False
    assert 'cache_path' not in json.dumps(result) and 'private' not in json.dumps(result)
    with pytest.raises(ValueError): repository.map('existing','base')
    with pytest.raises(ValueError): repository.map('additional','../../private')


@pytest.fixture
def running_ui():
    server=make_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)


def test_http_routes_and_forbidden_reads(running_ui):
    for path in ('/api/status','/api/dashboard','/api/case-study/buildings','/api/roof/A160/scenarios',
        '/api/roof/A160/reference','/api/models/office-surrogate','/api/evidence',
        '/api/pvgis/status','/api/demand/status','/api/sharing/status','/api/impact/status',
        '/api/roof/A160/map?assessment=additional&scenario=base'):
        with urlopen(running_ui+path) as response:
            assert response.status==200
            assert not response.headers.get('Access-Control-Allow-Origin')
            json.loads(response.read())
    for path,code in [('/api/status?path=../../.codex/config.toml',400),
        ('/api/roof/A160/map?assessment=additional&scenario=bogus',400),
        ('/api/roof/A160/map?assessment=additional&assessment=retrospective&scenario=base',400),
        ('/../config/project.json',404),('/%2e%2e/.git/config',404),('/design-tools.json',404),
        ('/integrations/stitch-headers.ps1',404),('/api/file?path=../../.codex/config.toml',404)]:
        with pytest.raises(HTTPError) as caught: urlopen(running_ui+path)
        assert caught.value.code==code
    for method in ('POST','PUT','PATCH','DELETE'):
        with pytest.raises(HTTPError) as caught: urlopen(Request(running_ui+'/api/status',data=b'{}',method=method))
        assert caught.value.code==405
    with pytest.raises(HTTPError) as caught:
        urlopen(Request(running_ui+'/api/status',headers={'Host':'untrusted.example'}))
    assert caught.value.code==403


def test_models_reports_prediction_and_approved_template_unchanged():
    preservation=json.loads((ROOT/'ui/docs/preservation.json').read_text())
    for name,digest in preservation['sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
