"""Loopback-only read-only HTTP service for the approved research dashboard."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .data import RepositoryData

UI = Path(__file__).resolve().parent
STATIC = {
    '/': (UI / 'index.html', 'text/html; charset=utf-8'),
    '/index.html': (UI / 'index.html', 'text/html; charset=utf-8'),
    '/app.js': (UI / 'app.js', 'text/javascript; charset=utf-8'),
    '/profiles.js': (UI / 'profiles.js', 'text/javascript; charset=utf-8'),
    '/pv-assessment.js': (UI / 'pv-assessment.js', 'text/javascript; charset=utf-8'),
    '/styles.css': (UI / 'styles.css', 'text/css; charset=utf-8'),
    '/integration.css': (UI / 'integration.css', 'text/css; charset=utf-8'),
    '/assets/neighbourhood.jpg': (UI / 'assets/neighbourhood.jpg', 'image/jpeg'),
    '/assets/rooftop-evidence.png': (UI.parent / 'reports/roof_capacity/A160/A160_two_assessments.png', 'image/png'),
}


def handler_for(repository):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'RoofscapesReadOnly/1'

        def log_message(self, *_):
            pass

        def send(self, status, payload, content_type='application/json; charset=utf-8', head=False):
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            if not head:
                self.wfile.write(payload)

        def do_POST(self):
            self.send(405, {'error':'Read-only service; writes are not supported.'})

        do_PUT = do_DELETE = do_PATCH = do_POST

        def do_HEAD(self):
            self.do_GET(head=True)

        def do_GET(self, head=False):
            if self.headers.get('Host', '').split(':')[0] not in ('127.0.0.1','localhost'):
                self.send(403, {'error':'Loopback host required.'}, head=head)
                return
            url = urlsplit(self.path)
            path = unquote(url.path)
            query = parse_qs(url.query, keep_blank_values=True)
            try:
                if path in STATIC:
                    if query:
                        raise ValueError('Unexpected query parameters')
                    file, content_type = STATIC[path]
                    self.send(200, file.read_bytes(), content_type, head=head)
                    return
                routes = {'/api/status':repository.status, '/api/dashboard':repository.dashboard,
                    '/api/case-study/buildings':repository.buildings,
                    '/api/roof/A160/scenarios':repository.scenarios, '/api/roof/A160/reference':repository.reference,
                    '/api/models/office-surrogate':repository.model, '/api/evidence':repository.evidence}
                from .existing_pv import assess
                from .solar import hourly
                routes['/api/roof/A160/existing-pv']=lambda:assess(repository)
                routes.update({f'/api/{stage}/status': lambda stage=stage: repository.stage(stage)
                               for stage in ('pvgis','demand','sharing','impact')})
                if path == '/api/pvgis/hypothetical/hourly':
                    if set(query)!={'scenario'} or len(query['scenario'])!=1:
                        raise ValueError('One known hypothetical scenario is required')
                    result=hourly(repository,query['scenario'][0])
                elif path == '/api/roof/A160/map':
                    if set(query) != {'assessment','scenario'} or any(len(values) != 1 for values in query.values()):
                        raise ValueError('Map requires one assessment and one scenario')
                    result = repository.map(query['assessment'][0], query['scenario'][0])
                elif path in routes:
                    if query:
                        raise ValueError('Unexpected query parameters')
                    result = routes[path]()
                else:
                    self.send(404, {'error':'Unknown allowlisted resource.'}, head=head)
                    return
                self.send(200, result, head=head)
            except ValueError:
                self.send(400, {'error':'Invalid request or source values.'}, head=head)
            except (FileNotFoundError, KeyError, OSError):
                self.send(503, {'error':'Public source unavailable; no results substituted.'}, head=head)
    return Handler


def make_server(port=8765, repository=None):
    return ThreadingHTTPServer(('127.0.0.1', port), handler_for(repository or RepositoryData()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with make_server(args.port) as server:
        print(f'Roofscapes local dashboard: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
