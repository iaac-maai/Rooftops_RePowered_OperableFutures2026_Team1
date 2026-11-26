"""Test connector configuration and duplicate-prevention with no live credentials."""
import json
from pathlib import Path
import tomllib
import pytest
from ui.integrations import stitch


def test_stitch_configuration_preserves_other_settings_and_is_idempotent(tmp_path,monkeypatch):
    home=tmp_path/'user';directory=home/'.codex';directory.mkdir(parents=True)
    path=directory/'config.toml'
    path.write_text('[features]\nexample = true\n[mcp_servers.stitch]\nurl = "https://stitch.googleapis.com/mcp"\n')
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:home))
    stitch.configure_codex()
    after=path.read_text();data=tomllib.loads(after)
    assert data['features']['example'] is True
    assert 'stitch-headers.ps1' in data['mcp_servers']['stitch']['http_headers_helper']
    assert 'X-Goog-Api-Key' not in after
    stitch.configure_codex()
    assert path.read_text()==after


def test_project_creation_uses_returned_resource_and_does_not_repeat(tmp_path,monkeypatch):
    config=tmp_path/'design-tools.json'
    config.write_text(json.dumps({'project_title':'SYNTHETIC_TEST_PROJECT','project_resource':None,'project_url':None}))
    calls=[]
    class FakeStitch:
        def call(self,method,params):
            calls.append(method)
            if method=='tools/list':
                return {'tools':[{'name':'create_project','inputSchema':{'properties':{'title':{'type':'string'}},'required':['title']}}]}
            return {'structuredContent':{'name':'projects/synthetic-test-resource'}}
    monkeypatch.setattr(stitch,'CONFIG',config)
    monkeypatch.setattr(stitch,'Stitch',FakeStitch)
    stitch.verify(create_project=True)
    data=json.loads(config.read_text())
    assert data['project_resource']=='projects/synthetic-test-resource'
    assert data['project_url'] is None  # no guessed browser URL
    stitch.verify(create_project=True)
    assert calls.count('tools/call')==1
    data['project_resource']=None;data['project_creation_state']='attempted_needs_review'
    config.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='No duplicate'):
        stitch.verify(create_project=True)
    assert calls.count('tools/call')==1
