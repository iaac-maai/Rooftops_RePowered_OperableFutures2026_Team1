"""Synthetic API responses only; real research outputs are never rewritten here."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from pipeline.common import InputError
from pipeline.step_03_pvgis import acquire
from pipeline.step_03_pvgis.importer import validate_generation_role,validate_case_study_supply
from ui.data import RepositoryData


@pytest.fixture
def acquisition_workspace(tmp_path,monkeypatch):
    cfg=json.loads(Path('config/pvgis_hypothetical.json').read_text())
    cfg.update(raw_dir='raw/hypothetical',output_dir='processed/hypothetical',report_path='reports/hypothetical.json',
        location_metadata='location.json',roof_output_root='roof')
    (tmp_path/'location.json').write_text(json.dumps({'latitude':41.4,'longitude':2.19}))
    for assessment in ('retrospective','additional'):
        directory=tmp_path/'roof'/assessment;directory.mkdir(parents=True)
        with (directory/'roof_capacity_scenarios.csv').open('w',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=['scenario','panel_count','estimated_kwp','assumed_module_wp','azimuth_degrees_from_north','tilt_degrees']);writer.writeheader()
            for index,name in enumerate(acquire.SCENARIOS):
                count=(index+1) if assessment=='retrospective' else (0 if index==0 else 1)
                writer.writerow(dict(scenario=name,panel_count=count,estimated_kwp=count*.5,assumed_module_wp=500,azimuth_degrees_from_north=135,tilt_degrees=10))
    settings=tmp_path/'settings.json';settings.write_text(json.dumps(cfg))
    monkeypatch.setattr(acquire,'ROOT',tmp_path)
    monkeypatch.setattr(acquire,'resolve',lambda path:Path(path) if Path(path).is_absolute() else tmp_path/path)
    return tmp_path,settings,cfg


@pytest.fixture
def source_csv():
    times=pd.date_range('2017-01-01T00:10:00Z',periods=8760,freq='h')
    return ('Synthetic test fixture only\ntime,P,T2m\n'+'\n'.join(f'{stamp:%Y%m%d:%H%M},100,12' for stamp in times)+'\n\nFooter\n').encode()


def test_official_acquisition_cache_temporal_normalization_and_role_guards(acquisition_workspace,source_csv):
    root,settings,cfg=acquisition_workspace
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs['params']))
        return SimpleNamespace(status_code=200,content=source_csv,headers={'Content-Type':'text/csv'})
    result=acquire.run(settings,get=get)
    assert result['available_scenarios']==5 and result['failed_scenarios']==0
    assert len(calls)==3  # three unique capacities; duplicate requests reuse exact cached source
    assert result['actual_installed_capacity_kwp'] is None
    for row in result['scenarios']:
        assert row['hypothetical'] is True and row['energy_sharing_eligible'] is False
        with pytest.raises(InputError): validate_generation_role(row)
        if row['status']=='available':
            assert row['rows']==8760 and row['source_minute_offsets']==[10]
            assert row['annual_generation_kwh']==pytest.approx(876)
            frame=pd.read_csv(root/row['output_csv'])
            assert frame.energy_sharing_eligible.eq(False).all()
            assert frame.data_origin.eq('SIMULATED_PHYSICS').all()
            with pytest.raises(InputError): validate_case_study_supply(frame)
        else:
            assert row['status']=='not_applicable_zero_capacity' and row['annual_generation_kwh'] is None
    acquire.run(settings,get=lambda *args,**kwargs:pytest.fail('Cached responses must not be fetched again'))


def test_api_failure_is_documented_and_manual_fallback_keeps_hypothetical_role(acquisition_workspace,source_csv):
    root,settings,cfg=acquisition_workspace
    result=acquire.run(settings,get=lambda *args,**kwargs:SimpleNamespace(status_code=503,content=b'SYNTHETIC API FAILURE',headers={}))
    assert result['available_scenarios']==0 and result['failed_scenarios']==5
    assert all(row['annual_generation_kwh'] is None for row in result['scenarios'])
    assert list((root/'raw/hypothetical').glob('*/failure.json'))
    manual=root/'manual.csv';manual.write_bytes(source_csv)
    imported=acquire.run(settings,manual_input=manual,scenario_id='retrospective_base')
    selected=next(row for row in imported['scenarios'] if row['scenario_id']=='retrospective_base')
    assert selected['status']=='available' and selected['source']['acquisition']=='MANUAL_PVGIS_EXPORT'
    assert selected['energy_sharing_eligible'] is False
    with pytest.raises(InputError): validate_generation_role(selected)


def test_incomplete_or_wrong_year_csv_rejected(acquisition_workspace,source_csv):
    root,settings,cfg=acquisition_workspace
    record=acquire.settings_for_scenarios(cfg)[0]
    source=root/'short.csv';source.write_text('time,P\n20170101:0010,100\n20170101:0110,200\n')
    with pytest.raises(InputError,match='complete'): acquire.normalize(source,record,root/'out.csv')
    source.write_text('time,P\n20180101:0010,100\n')
    with pytest.raises(InputError,match='year'): acquire.normalize(source,record,root/'out.csv')


def test_live_evidence_keeps_installation_unknown_and_hypotheses_separate():
    from ui.existing_pv import assess
    from ui.solar import hourly,status
    repository=RepositoryData()
    existing=assess(repository)
    assert all(value is None for value in existing['installation'].values())
    assert len(existing['comparisons'])==3
    assert all(row['capacity_error_percent'] is None for row in existing['comparisons'])
    assert existing['municipal_comparison']['current_roof_validation_eligible'] is False
    pv=status(repository)
    assert pv['state']=='pending' and pv['annual_generation_kwh'] is None
    assert pv['hypothetical_state']=='available'
    series=hourly(repository,'retrospective_base')
    assert len(series['hourly'])==8760 and series['energy_sharing_eligible'] is False
    assert 'T' in series['hourly'][0]['timestamp_utc']
    assert hourly(repository,'additional_conservative')['state']=='pending'
    with pytest.raises(ValueError): hourly(repository,'../../private')


def test_case_study_rejects_explicit_hypotheses_or_false_flags_without_rewriting_legacy_inputs():
    legacy=pd.DataFrame({'pv_generation_kwh':[1]})
    validate_case_study_supply(legacy)
    validate_case_study_supply(legacy.assign(energy_sharing_eligible=True,generation_role='existing_verified'))
    for change in ({'hypothetical':True},{'energy_sharing_eligible':False},{'energy_sharing_eligible':'False'},
                   {'generation_role':'counterfactual_validation_only'}):
        with pytest.raises(InputError): validate_case_study_supply(legacy.assign(**change))


def test_changed_assumptions_hide_stale_hypothetical_generation(monkeypatch):
    from ui.solar import status,hourly
    repository=RepositoryData();original=repository.read
    def changed(key):
        result=original(key)
        if key=='pvgis_hypothetical_report':result['settings_sha256']='changed-test-fixture'
        return result
    monkeypatch.setattr(repository,'read',changed)
    assert status(repository)['hypothetical_state']=='not_acquired'
    assert hourly(repository,'retrospective_base')['state']=='pending'
