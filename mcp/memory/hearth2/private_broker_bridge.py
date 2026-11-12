"""Fixed worker-side loopback MCP -> private Unix socket adapter; no credentials.

Standalone stdlib module so the worker needs neither the Store nor root Broker
libraries. The root driver supplies only its scoped socket, never a bearer.
"""
import json
import socket
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer


def create_private_mcp_server(*,socket_path='/run/hearth-memory.sock',port=8010):
    if type(port) is not int or not 0<=port<=65535:raise ValueError('fixed loopback port required')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.send_error(405)
        def do_POST(self):
            if self.path!='/mcp':self.send_error(404);return
            if self.headers.get('Authorization') is not None or self.headers.get('Origin') is not None:
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=65536:self.send_error(413);return
                raw=self.rfile.read(length)
                if len(raw)!=length:raise ValueError()
                request=json.loads(raw)
                with socket.socket(socket.AF_UNIX) as channel:
                    channel.settimeout(5);channel.connect(str(socket_path));channel.sendall(raw+b'\n')
                    answer=channel.makefile('rb').readline(1_000_001)
                if len(answer)>1_000_000 or not answer.endswith(b'\n'):raise ValueError()
                if 'id' not in request:
                    self.send_response(202);self.end_headers();return
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(answer)));self.send_header('Cache-Control','no-store')
                self.end_headers();self.wfile.write(answer)
            except Exception:self.send_error(502,'Private read unavailable')
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__=='__main__':create_private_mcp_server().serve_forever()
