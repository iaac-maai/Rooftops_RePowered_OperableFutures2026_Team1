"""Public summaries of separately cached hypothetical PVGIS output only."""
import csv
from datetime import datetime

from .data import SourceUnavailable, pending, safe_text

IDS={f'{assessment}_{scenario}' for assessment in ('retrospective','additional')
     for scenario in ('conservative','base','optimistic')}


def check_inputs(repository,report):
    if repository.provenance('pvgis_hypothetical_settings')[0]['sha256']!=report['settings_sha256']:
        raise SourceUnavailable('PVGIS assumptions changed; rerun acquisition before using a current sensitivity result.')
    for row in report['scenarios']:
        if row.get('assessment') in ('retrospective','additional'):
            if repository.provenance(row['assessment'])[0]['sha256']!=row['roof_source_sha256']:
                raise SourceUnavailable('Rooftop capacity source changed; rerun hypothetical PVGIS acquisition.')


def status(repository):
    result={**pending('Actual A160 generation remains unknown. Hypothetical modeled output is separate.',
        ['Verified installed capacity and array specifications before an actual-system generation claim']),
        'installed_capacity_kwp':None,'annual_generation_kwh':None,'actual_generation':None,
        'hypothetical_state':'not_acquired','hypothetical_scenarios':[],'data_origin':None}
    try:
        report=repository.read('pvgis_hypothetical_report')
        check_inputs(repository,report)
        rows=[]
        for row in report['scenarios']:
            if row['scenario_id'] not in IDS: continue
            rows.append({key:row.get(key) for key in ('scenario_id','assessment','scenario','status','capacity_kwp',
                'annual_generation_kwh','monthly_generation_kwh','rows','first_timestamp_utc','last_timestamp_utc',
                'source_minute_offsets','model_version','weather_year','loss_percent','tilt','azimuth','source_url','parameters','roof_id')}
                | {'hypothetical':True,'data_origin':'SIMULATED_PHYSICS','energy_sharing_eligible':False,
                    'raw_response_sha256':row.get('source',{}).get('source_sha256'),
                    'source_retrieved_utc':row.get('source',{}).get('retrieved_utc'),
                    'acquisition_mode':row.get('source',{}).get('acquisition'),
                    'error':safe_text(row.get('error')) or None})
        result.update(hypothetical_state='available' if any(row['status']=='available' for row in rows) else 'unavailable',
            hypothetical_scenarios=rows,
            assumptions=report['scenarios'][0].get('assumptions',{}) if report['scenarios'] else {},
            official_documentation=report['official_documentation'],
            provenance=repository.provenance('pvgis_hypothetical_report'))
    except (SourceUnavailable,KeyError) as exc:
        result['hypothetical_source_message']=safe_text(exc)
    result['manual_fallback']='python -m pipeline pvgis-import-hypothetical --scenario retrospective_base --input YOUR_PVGIS_EXPORT.csv'
    return result


def hourly(repository,scenario_id):
    if scenario_id not in IDS:
        raise ValueError('Unknown hypothetical PVGIS scenario')
    try:
        report=repository.read('pvgis_hypothetical_report')
        check_inputs(repository,report)
        row=next(item for item in report['scenarios'] if item['scenario_id']==scenario_id)
        if row['status']!='available':
            return pending('No hourly source exists for this scenario; zero-capacity cases skip simulation.', [scenario_id])
        # Fixed expected filename, not an arbitrary path accepted from requests/manifests.
        path=(repository.root/'datasets/processed/pvgis/A160/hypothetical'/f'{scenario_id}.csv').resolve()
        if not path.is_relative_to(repository.root) or not path.is_file():
            raise SourceUnavailable('Hypothetical hourly source unavailable')
        import hashlib
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['output_sha256']:
            raise SourceUnavailable('Hypothetical series changed since acquisition; review its provenance')
        with path.open(encoding='utf-8-sig',newline='') as file:
            data=list(csv.DictReader(file))
        # Export the exact UTC instants; browser converts their display only.
        return {'state':'available','scenario_id':scenario_id,'data_origin':'SIMULATED_PHYSICS',
            'hypothetical':True,'energy_sharing_eligible':False,'actual_existing_generation':False,
            'timestamp_basis':'UTC','display_timezone':'Europe/Madrid','unit':'kWh per hourly interval',
            'hourly':[{'timestamp_utc':datetime.fromisoformat(item['timestamp_utc']).isoformat(),'pv_generation_kwh':float(item['pv_generation_kwh'])} for item in data],
            'source_sha256':row['output_sha256'],'source_url':row['source_url'],'model_version':row['model_version']}
    except (SourceUnavailable,KeyError,StopIteration) as exc:
        return pending(safe_text(exc), ['Hypothetical hourly CSV and acquisition manifest'])
