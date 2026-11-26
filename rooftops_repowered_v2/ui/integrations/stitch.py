"""Verify official Stitch MCP and create the explicitly requested design project.

Secrets are decrypted by a Windows DPAPI helper and held only in subprocess/
request memory. They are never printed, exported in the UI or saved in Git.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'ui/design-tools.json'
ENDPOINT = 'https://stitch.googleapis.com/mcp'


def configure_codex():
    """Only augment the previously registered Stitch table; preserve other config."""
    import tomllib
    path = Path.home() / '.codex/config.toml'
    original = path.read_text(encoding='utf-8')
    parsed = tomllib.loads(original)
    server = parsed.get('mcp_servers', {}).get('stitch')
    if not server or server.get('url') != ENDPOINT:
        raise ValueError('Register official Stitch with codex mcp add first.')
    helper = 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + str(Path(__file__).with_name('stitch-headers.ps1')) + '"'
    if 'http_headers_helper' in server:
        if server['http_headers_helper'] != helper:
            raise ValueError('A different Stitch header helper already exists; preserve it for review.')
        return
    replacement = '[mcp_servers.stitch]\nhttp_headers_helper = ' + json.dumps(helper) + '\nstartup_timeout_sec = 20\ntool_timeout_sec = 120\n'
    updated = original.replace('[mcp_servers.stitch]', replacement, 1)
    check = tomllib.loads(updated)
    assert check['mcp_servers']['stitch']['http_headers_helper'] == helper
    # Backup is private, alongside the original; no config/credentials enter Git.
    backup = path.with_name('config.before-stitch-helper.toml')
    if not backup.exists():
        backup.write_text(original, encoding='utf-8')
    path.write_text(updated, encoding='utf-8')
    print('Codex Stitch connector registered with the encrypted local credential helper.')


class Stitch:
    def __init__(self):
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',
            str(Path(__file__).with_name('stitch-headers.ps1'))], capture_output=True, check=True)
        self.headers = json.loads(result.stdout)
        if not self.headers.get('X-Goog-Api-Key'):
            raise ValueError('Stitch authentication is pending. Use the masked setup window.')
        self.sequence = 0
        self.call('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'roofscapes-stitch-setup', 'version': '1'}})
        self.call('notifications/initialized', {})

    def call(self, method, params):
        self.sequence += 1
        payload = {'jsonrpc':'2.0', 'id': self.sequence, 'method':method, 'params':params}
        if method.startswith('notifications/'):
            payload.pop('id')
        headers = {**self.headers, 'Content-Type':'application/json', 'Accept':'application/json, text/event-stream'}
        request = Request(ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method='POST')
        try:
            with urlopen(request, timeout=90) as response:
                raw = response.read().decode()
                session = response.headers.get('Mcp-Session-Id')
                if session:
                    self.headers['Mcp-Session-Id'] = session
        except HTTPError as exc:
            raise ValueError(f'Stitch returned HTTP {exc.code}. Check the API key in Stitch Settings.') from None
        except URLError:
            raise ValueError('Stitch could not be reached. Check network access.') from None
        if not raw.strip():
            return {}
        if raw.lstrip().startswith('data:') or '\ndata:' in raw:
            messages = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')]
            response = next((message for message in messages if message.get('id') == self.sequence), {})
        else:
            response = json.loads(raw)
        if response.get('error') or response.get('result', {}).get('isError'):
            raise ValueError('Stitch rejected the request; no authenticated project update was recorded.')
        return response.get('result', {})


def verify(create_project=False):
    config = json.loads(CONFIG.read_text())
    client = Stitch()
    tools = client.call('tools/list', {}).get('tools', [])
    config['connection_status'] = 'authenticated_mcp_verified'
    config['available_tools'] = [tool['name'] for tool in tools]
    if create_project and config.get('project_creation_state') == 'attempted_needs_review' and not config.get('project_resource'):
        raise ValueError('A previous project-creation attempt needs list_projects review. No duplicate project was requested.')
    if create_project and not config.get('project_resource'):
        tool = next((tool for tool in tools if tool['name'] == 'create_project'), None)
        if not tool or 'title' not in tool['inputSchema'].get('properties', {}) or set(tool['inputSchema'].get('required', [])) - {'title'}:
            raise ValueError('Authenticated, but the project-creation schema needs review before writing.')
        config['project_creation_state'] = 'attempted_needs_review'
        CONFIG.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
        result = client.call('tools/call', {'name':'create_project', 'arguments':{'title':config['project_title']}})
        data = result.get('structuredContent')
        if not data:
            for part in result.get('content', []):
                if part.get('type') == 'text':
                    try:
                        data = json.loads(part['text'])
                        break
                    except json.JSONDecodeError:
                        pass
        if not isinstance(data, dict):
            raise ValueError('Stitch responded, but its new-project response needs review; do not repeat creation blindly.')
        project = data.get('project', data)
        config['project_resource'] = project.get('name') or project.get('id')
        # Store a browser link only when the service supplies one.
        config['project_url'] = project.get('webUrl') or project.get('url')
        config['project_created'] = True
        config['project_creation_state'] = 'created' if config['project_resource'] else 'attempted_needs_review'
    CONFIG.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('Stitch authentication verified. Research Studio project status saved to ui/design-tools.json.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure-codex', action='store_true')
    parser.add_argument('--create-project', action='store_true')
    args = parser.parse_args()
    try:
        if args.configure_codex:
            configure_codex()
        else:
            verify(args.create_project)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else 'The local Stitch credential helper could not run.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
