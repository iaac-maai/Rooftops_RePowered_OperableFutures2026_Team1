"""Official seriescalc acquisition for explicitly hypothetical A160 scenarios.

Uses the existing PVGIS/temporal importer. Outputs stay outside case-study PV
inputs and retain energy_sharing_eligible=false; existing-generation guards remain.
"""
import calendar
import csv
import hashlib
import json
import math
from urllib.parse import urlencode

import requests

from pipeline.common import InputError, ROOT, now, require_file, resolve, sha256, write_json
from .importer import import_hourly

ENDPOINT='https://re.jrc.ec.europa.eu/api/v5_3/seriescalc'
SCENARIOS=('conservative','base','optimistic')
ASSESSMENTS=('retrospective','additional')


def load_settings(path='config/pvgis_hypothetical.json'):
    cfg=json.loads(require_file(resolve(path)).read_text(encoding='utf-8'))
    if cfg['endpoint']!=ENDPOINT or cfg['assessment_scope']!='HYPOTHETICAL_CAPACITY_SENSITIVITY_NOT_EXISTING_GENERATION':
        raise InputError('This acquisition route only supports official hypothetical seriescalc requests.')
    if cfg['timestamp_basis']!='UTC' or cfg['power_unit']!='W':
        raise InputError('Explicit PVGIS UTC/W metadata required.')
    if type(cfg['weather_year']) is not int or not 2005<=cfg['weather_year']<=2023 or not 0<=cfg['loss_percent']<=100:
        raise InputError('Year/loss outside the documented 5.3 SARAH3 range.')
    if cfg['raddatabase']!='PVGIS-SARAH3':
        raise InputError('Review dataset/year ranges before adding a different weather source.')
    for key in ('raw_dir','output_dir','report_path'):
        if not resolve(cfg[key]).resolve().is_relative_to(ROOT) or '/hypothetical' not in str(cfg[key]).replace('\\','/'):
            raise InputError('Hypothetical outputs must remain in their separate workspace directories.')
    return cfg


def settings_for_scenarios(cfg):
    location=json.loads(require_file(resolve(cfg['location_metadata'])).read_text())
    records=[]
    for assessment in cfg['assessments']:
        if assessment not in ASSESSMENTS:
            raise InputError('Unknown hypothetical assessment.')
        path=resolve(cfg['roof_output_root'])/assessment/'roof_capacity_scenarios.csv'
        with require_file(path).open(encoding='utf-8-sig',newline='') as file:
            rows=list(csv.DictReader(file))
        if len(rows)!=3 or {row['scenario'] for row in rows}!=set(SCENARIOS):
            raise InputError('Expected three named rooftop scenarios.')
        for row in rows:
            count=int(row['panel_count']);capacity=float(row['estimated_kwp']);wp=float(row['assumed_module_wp'])
            if count<0 or not all(math.isfinite(value) for value in (capacity,wp)) or capacity<0 or wp<=0 or abs(count*wp/1000-capacity)>1e-6:
                raise InputError('Roof module/capacity values disagree.')
            azimuth=float(row['azimuth_degrees_from_north'])
            if not math.isfinite(azimuth) or not 0<=azimuth<360 or not 0<=float(row['tilt_degrees'])<=90:
                raise InputError('Invalid hypothetical array orientation/tilt.')
            params={'lat':location['latitude'],'lon':location['longitude'],'startyear':cfg['weather_year'],
                'endyear':cfg['weather_year'],'raddatabase':cfg['raddatabase'],'pvcalculation':1,
                'peakpower':capacity,'loss':cfg['loss_percent'],'angle':float(row['tilt_degrees']),
                'aspect':((azimuth-180+180)%360)-180,'pvtechchoice':cfg['pvtechchoice'],
                'mountingplace':cfg['mountingplace'],'trackingtype':0,'usehorizon':cfg['usehorizon'],
                'outputformat':'csv','browser':0}
            records.append({'scenario_id':f'{assessment}_{row["scenario"]}','assessment':assessment,
                'scenario':row['scenario'],'building_id':'A160','roof_id':f'A160_{assessment}_{row["scenario"]}',
                'generation_role':'counterfactual_validation_only' if assessment=='retrospective' else 'incremental_proposed',
                'data_origin':'SIMULATED_PHYSICS','hypothetical':True,'existing_installed_capacity_verified':False,
                'energy_sharing_eligible':False,'capacity_kwp':capacity,'tilt':params['angle'],'azimuth':params['aspect'],
                'weather_year':cfg['weather_year'],'loss_percent':cfg['loss_percent'],'timestamp_basis':'UTC','power_unit':'W',
                'model_version':'PVGIS_5.3_seriescalc_SARAH3','parameters':params,
                'source_url':ENDPOINT+'?'+urlencode(params),'roof_source_path':str(path.relative_to(ROOT)),
                'roof_source_sha256':sha256(path),'assumptions':cfg['assumptions']})
    return records


def normalize(source,record,target,require_full_year=True):
    frame=import_hourly(require_file(source),'UTC','W')
    if not frame.timestamp_utc.is_monotonic_increasing:
        raise InputError('PVGIS source order is not chronological; review instead of silently sorting.')
    year=record['weather_year']
    if not frame.timestamp_utc.dt.year.eq(year).all():
        raise InputError('PVGIS source year does not match its scenario settings.')
    if require_full_year and len(frame)!=(8784 if calendar.isleap(year) else 8760):
        raise InputError('PVGIS source must contain the complete selected hourly year.')
    # The importer preserves source minute offsets; no flooring/calendar relabeling.
    frame['roof_id']=record['roof_id']
    frame['scenario_id']=record['scenario_id']
    frame['generation_role']=record['generation_role']
    frame['hypothetical']=True
    frame['energy_sharing_eligible']=False
    frame['model_version']=record['model_version']
    target.parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(target,index=False)
    return {'rows':len(frame),'annual_generation_kwh':float(frame.pv_generation_kwh.sum()),
        'monthly_generation_kwh':{str(int(month)):float(value) for month,value in frame.groupby(frame.timestamp_utc.dt.month).pv_generation_kwh.sum().items()},
        'first_timestamp_utc':frame.timestamp_utc.iloc[0].isoformat(),'last_timestamp_utc':frame.timestamp_utc.iloc[-1].isoformat(),
        'source_minute_offsets':sorted(int(value) for value in frame.timestamp_utc.dt.minute.unique()),
        'output_csv':str(target.relative_to(ROOT)),'output_sha256':sha256(target),'unit':'kWh per hourly interval'}


def run(settings_path='config/pvgis_hypothetical.json',manual_input=None,scenario_id=None,get=None):
    cfg=load_settings(settings_path)
    records=settings_for_scenarios(cfg)
    if manual_input and scenario_id not in {record['scenario_id'] for record in records}:
        raise InputError('Manual import needs an exact allowlisted scenario ID.')
    report_path=resolve(cfg['report_path'])
    previous=json.loads(report_path.read_text()) if report_path.exists() else {}
    previous_rows={row['scenario_id']:row for row in previous.get('scenarios',[])}
    report={'created_utc':now(),'state':'hypothetical_only','data_origin':'SIMULATED_PHYSICS',
        'verified_existing_generation':None,'actual_installed_capacity_kwp':None,'energy_sharing_eligible':False,
        'settings_path':str(resolve(settings_path).relative_to(ROOT)),'settings_sha256':sha256(resolve(settings_path)),
        'official_documentation':cfg['official_documentation'],'scenarios':[]}
    requester=get or requests.get
    for record in records:
        if manual_input and record['scenario_id']!=scenario_id:
            previous_row=previous_rows.get(record['scenario_id'])
            compatible=previous_row and previous_row.get('source_url')==record['source_url'] and previous_row.get('roof_source_sha256')==record['roof_source_sha256']
            report['scenarios'].append(previous_row if compatible else {**record,'status':'not_acquired'})
            continue
        result={**record}
        if record['capacity_kwp']==0:
            result.update(status='not_applicable_zero_capacity',annual_generation_kwh=None,rows=0)
            report['scenarios'].append(result)
            continue
        key=hashlib.sha256(record['source_url'].encode()).hexdigest()[:20]
        cache=resolve(cfg['raw_dir'])/key
        raw=cache/'seriescalc.csv';metadata=cache/'source.json'
        cache.mkdir(parents=True,exist_ok=True)
        try:
            if manual_input:
                source=require_file(resolve(manual_input))
                # Preserve exact manual response separately from API cache.
                raw=cache/f'manual_{sha256(source)[:12]}.csv'
                if not raw.exists(): raw.write_bytes(source.read_bytes())
                source_meta={'source_url':record['source_url'],'retrieved_utc':now(),'acquisition':'MANUAL_PVGIS_EXPORT',
                    'source_sha256':sha256(raw),'parameters_declared_not_server_verified':True}
                write_json(raw.with_suffix('.source.json'),source_meta)
            elif raw.exists() and metadata.exists():
                source_meta=json.loads(metadata.read_text())
                if source_meta['source_sha256']!=sha256(raw):
                    raise InputError('Cached PVGIS response hash changed; review before reuse.')
            else:
                response=requester(ENDPOINT,params=record['parameters'],timeout=(10,60),headers={'User-Agent':'Roofscapes-RePowered-Research/0.3'})
                received=now()
                (cache/'http_response.bin').write_bytes(response.content)
                if response.status_code!=200:
                    write_json(cache/'failure.json',{'retrieved_utc':received,'source_url':record['source_url'],
                        'http_status':response.status_code,'response_sha256':sha256(cache/'http_response.bin')})
                    raise InputError(f'Official PVGIS API returned HTTP {response.status_code}; manual CSV fallback remains available.')
                raw.write_bytes(response.content)
                source_meta={'source_url':record['source_url'],'retrieved_utc':received,'acquisition':'OFFICIAL_PVGIS_API',
                    'http_status':response.status_code,'content_type':response.headers.get('Content-Type'),
                    'source_sha256':sha256(raw),'parameters':record['parameters']}
                write_json(metadata,source_meta)
            target=resolve(cfg['output_dir'])/(record['scenario_id']+'.csv')
            statistics=normalize(raw,record,target)
            result.update(status='available',**statistics,source=source_meta,raw_response_path=str(raw.relative_to(ROOT)))
            write_json(target.with_suffix('.settings.json'),result)
            print(record['scenario_id'],statistics['rows'],f'{statistics["annual_generation_kwh"]:.2f} modeled kWh',flush=True)
        except (InputError,requests.RequestException,OSError,ValueError) as exc:
            result.update(status='failed',annual_generation_kwh=None,error=str(exc),
                manual_fallback='python -m pipeline pvgis-import-hypothetical --scenario '+record['scenario_id']+' --input YOUR_PVGIS_EXPORT.csv')
            print(record['scenario_id'],'unavailable; failure documented, no series invented',flush=True)
        report['scenarios'].append(result)
        write_json(report_path,report)
    report['failed_scenarios']=sum(row.get('status')=='failed' for row in report['scenarios'])
    report['available_scenarios']=sum(row.get('status')=='available' for row in report['scenarios'])
    write_json(report_path,report)
    return report
