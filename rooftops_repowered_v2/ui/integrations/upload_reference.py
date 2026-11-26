"""Upload the exact user-approved source HTML to the requested private Stitch project.

Uses Google's published BatchCreateScreens upload contract. Credentials stay in
memory; no API key, file payload or signed download URL is printed or recorded.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .stitch import CONFIG, ROOT, Stitch


def unpack(result):
    if result.get('structuredContent'):
        return result['structuredContent']
    for item in result.get('content', []):
        if item.get('type')=='text':
            try:
                return json.loads(item['text'])
            except json.JSONDecodeError:
                pass
    raise ValueError('The service response needs review.')


def returned_screens(result):
    if isinstance(result.get('screens'),list):
        return result['screens']
    candidates=result.get('responses',result.get('results',[]))
    return [item.get('screen',item) for item in candidates if isinstance(item,dict)]


def run():
    config=json.loads(CONFIG.read_text())
    source=(ROOT/config['approved_ui_source']).resolve()
    if not source.is_relative_to(ROOT) or source.suffix!='.html':
        raise ValueError('Only the approved workspace HTML source can be uploaded.')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    client=Stitch()
    project=unpack(client.call('tools/call',{'name':'get_project','arguments':{'name':config['project_resource']}}))
    if project.get('visibility')!='PRIVATE' or project.get('name')!=config['project_resource']:
        raise ValueError('The requested private project could not be verified.')
    if config.get('approved_template_upload',{}).get('sha256')==digest:
        if config['approved_template_upload'].get('state')=='uploaded':
            print('The approved HTML reference is already linked; no duplicate upload.')
            return
        raise ValueError('Review the earlier upload attempt in Stitch before requesting a duplicate.')
    if config.get('approved_template_upload'):
        raise ValueError('An existing reference is retained. Review a new reference version explicitly before uploading again.')
    resource=config['project_resource']
    project_id=resource.split('/')[-1]
    if not project_id.isdigit():
        raise ValueError('Unexpected project resource.')
    screen={'title':'Approved Roofscapes prototype - seven-view HTML source',
        'htmlCode':{'fileContentBase64':base64.b64encode(source.read_bytes()).decode(), 'mimeType':'text/html'},
        'screenType':'DOCUMENT', 'isCreatedByClient':True, 'generatedBy':'UserUploadedHtml'}
    payload={'parent':resource,'requests':[{'screen':screen}],'createScreenInstances':True}
    config['approved_template_upload']={'state':'attempted_needs_review','sha256':digest,
        'source':config['approved_ui_source'],'bytes':source.stat().st_size,'mime_type':'text/html'}
    CONFIG.write_text(json.dumps(config,indent=2)+'\n')
    request=Request(f'https://stitch.googleapis.com/v1/{resource}/screens:batchCreate',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type':'application/json','X-Goog-Api-Key':client.headers['X-Goog-Api-Key']})
    try:
        with urlopen(request,timeout=120) as response:
            created=json.loads(response.read())
    except HTTPError as exc:
        raise ValueError(f'Stitch upload returned HTTP {exc.code}; review before retrying.') from None
    except URLError:
        raise ValueError('Upload outcome is uncertain; inspect the project before retrying.') from None
    screens=returned_screens(created)
    if not screens:
        listed=unpack(client.call('tools/call',{'name':'list_screens','arguments':{'projectId':project_id}}))
        screens=[item for item in listed.get('screens',[]) if item.get('title')==screen['title']]
        if len(screens)!=1:
            screens=[]
    if not screens:
        raise ValueError('Stitch returned no screen resource; inspect the project before retrying.')
    config['approved_template_upload'].update(state='uploaded',
        screen_resources=[item.get('name') or item.get('id') for item in screens],
        verified_utc=datetime.now(timezone.utc).isoformat(),
        upload_contract_source='https://github.com/google-labs-code/stitch-skills/blob/main/plugins/stitch-design/skills/upload-to-stitch/scripts/upload_to_stitch.py')
    # This is a UI deep link derived from an API-verified project, not a newly guessed resource.
    config['project_url']=f'https://stitch.google.com/projects/{project_id}'
    config['project_url_basis']='Stitch UI project route for API-verified private resource; sign-in required'
    CONFIG.write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps({'project_title':project.get('title'),'project_visibility':project.get('visibility'),
        'project_url':config['project_url'],'uploaded_source':config['approved_ui_source'],
        'uploaded_bytes':source.stat().st_size,'screen_resources':config['approved_template_upload']['screen_resources']},indent=2))


if __name__=='__main__':
    try:
        run()
    except ValueError as exc:
        raise SystemExit(str(exc))
