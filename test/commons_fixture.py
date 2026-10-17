"""Local-only adapter test transport around the real file store, not a model."""
import importlib.util
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer

spec = importlib.util.spec_from_file_location('commons_fixture_store', Path(__file__).parents[1] / 'mcp/memory/commons_files.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
temp = tempfile.TemporaryDirectory()
# macOS exposes its temporary directory through /var -> /private/var.
# Use the canonical fixture path; the store still rejects linked paths.
store = module.CommonsStore(Path(temp.name).resolve() / 'commons')
participants = {'codex', 'kimi3', 'glm53', 'hy4', 'mavis'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        principal = self.headers.get('Authorization', '').removeprefix('Bearer fixture-')
        try:
            if principal not in participants:
                raise PermissionError('Fixture principal not enrolled')
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            name, args = body['name'], body['arguments']
            if name == 'commons_entry_create':
                value = store.create(author=principal, **args)
            elif name == 'commons_files_list':
                value = store.list(**args)
            elif name == 'commons_files_read':
                value = store.read(**args)
            else:
                raise ValueError('Unknown tool')
            output = {'content': [{'type': 'text', 'text': json.dumps(value)}]}
        except (ValueError, PermissionError) as error:
            output = {'isError': True, 'content': [{'type': 'text', 'text': str(error)}]}
        payload = json.dumps(output).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class LoopbackServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer's default bind performs reverse DNS via getfqdn, which can
        # block on offline CI hosts. This fixture only ever serves loopback.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address


server = LoopbackServer(('127.0.0.1', 0), Handler)
print(json.dumps({'port': server.server_port}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
    temp.cleanup()
