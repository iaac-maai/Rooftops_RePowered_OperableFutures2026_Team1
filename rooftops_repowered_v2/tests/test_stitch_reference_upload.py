"""Reference uploads preserve privacy/idempotency and verify uncertain responses."""
import json
import pytest
from ui.integrations import upload_reference as upload


@pytest.mark.parametrize('response_kind',['screens','responses','readback'])
def test_reference_upload_no_secret_logging_and_no_duplicate(tmp_path,monkeypatch,capsys,response_kind):
    source=tmp_path/'approved.html';source.write_text('<h1>APPROVED TEST FIXTURE</h1>')
    config_path=tmp_path/'design-tools.json'
    config_path.write_text(json.dumps({'approved_ui_source':'approved.html','project_resource':'projects/123'}))
    title='Approved Roofscapes prototype - seven-view HTML source'
    screen={'name':'projects/123/screens/test-fixture','title':title}
    requests=[]
    class FakeClient:
        headers={'X-Goog-Api-Key':'SYNTHETIC_SECRET_NEVER_LOG'}
        def call(self,method,params):
            if params['name']=='get_project':
                return {'structuredContent':{'name':'projects/123','title':'TEST PROJECT','visibility':'PRIVATE'}}
            return {'structuredContent':{'screens':[screen]}}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def read(self):
            data={'screens':[screen]} if response_kind=='screens' else {'responses':[{'screen':screen}]} if response_kind=='responses' else {'accepted':True}
            return json.dumps(data).encode()
    def send(request,**kwargs):
        requests.append(request)
        return Response()
    monkeypatch.setattr(upload,'ROOT',tmp_path)
    monkeypatch.setattr(upload,'CONFIG',config_path)
    monkeypatch.setattr(upload,'Stitch',FakeClient)
    monkeypatch.setattr(upload,'urlopen',send)
    upload.run();upload.run()
    saved=json.loads(config_path.read_text())
    assert saved['approved_template_upload']['state']=='uploaded'
    assert saved['approved_template_upload']['screen_resources']==[screen['name']]
    assert len(requests)==1
    assert requests[0].full_url=='https://stitch.googleapis.com/v1/projects/123/screens:batchCreate'
    assert 'SYNTHETIC_SECRET' not in capsys.readouterr().out
    assert 'SYNTHETIC_SECRET' not in config_path.read_text()
