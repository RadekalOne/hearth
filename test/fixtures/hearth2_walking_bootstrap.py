"""Container-only synthetic provider and broker bridge; never a live profile."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

signal.alarm(80)
native='/opt/codex/bin/codex'
if hashlib.sha256(Path(native).read_bytes()).hexdigest()!='f1cd7fa4ac866c724122f173d408a95385257cbcc9ac5ce5ddba42669c74ba97':
    raise RuntimeError('fixture binary pin mismatch')
home=Path('/scratch/codex-home');home.mkdir(mode=0o700)
(home/'config.toml').write_bytes(Path('/fixture/config.toml').read_bytes())
if list(home.glob('auth*')):raise RuntimeError('fixture home must have no auth files')
task=json.loads(Path('/fixture/task.json').read_text())


class MCP(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.send_error(405)
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<=65536:self.send_error(413);return
        request=json.loads(self.rfile.read(length))
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(5);sock.connect('/bridge/broker.sock')
            sock.sendall(json.dumps({'authorization':self.headers.get('Authorization'), 'request':request}).encode()+b'\n')
            answer=sock.makefile('rb').readline(65537)
        if 'id' not in request:self.send_response(202);self.end_headers();return
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(answer)));self.end_headers();self.wfile.write(answer)


class Provider(BaseHTTPRequestHandler):
    calls=0
    def log_message(self,*args):pass
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<=1_000_000:self.send_error(413);return
        body=json.loads(self.rfile.read(length));Provider.calls+=1
        if body.get('model')!='gpt-6.1-sol' or Provider.calls>2:
            self.send_error(400,'fixture model/count refused: '+str(body.get('model'))+'/'+str(Provider.calls));return
        response={'id':'resp_walk_'+str(Provider.calls),'object':'response','created_at':int(time.time()),
            'status':'in_progress','model':body['model'],'output':[]}
        events=[('response.created',{'type':'response.created','response':response})]
        if Provider.calls==1:
            items=[{'type':'function_call','id':'fc_read','call_id':'call_read','namespace':'mcp__hearth',
                'name':'memory_get','arguments':json.dumps({'drawer_id':'drawer_fixture'})}]
        else:
            outputs=[x for x in body.get('input',[]) if x.get('type')=='function_call_output' and x.get('call_id')=='call_read']
            if len(outputs)!=1 or 'synthetic-memory-'+task['challenge'] not in json.dumps(outputs):
                self.send_error(400,'fixture memory output missing: '+json.dumps(outputs)[:900]);return
            text=json.dumps(task['closeout']) if task['mode']=='positive' else 'Synthetic completed turn with no structured closeout.'
            items=[{'type':'message','id':'msg_walk','role':'assistant','status':'completed',
                'content':[{'type':'output_text','text':text,'annotations':[]}]}]
        for index,item in enumerate(items):
            events.append(('response.output_item.added',{'type':'response.output_item.added','output_index':index,'item':item}))
            events.append(('response.output_item.done',{'type':'response.output_item.done','output_index':index,'item':item}))
        response={**response,'status':'completed','output':items,'usage':{'input_tokens':10,'output_tokens':5,'total_tokens':15}}
        events.append(('response.completed',{'type':'response.completed','response':response}))
        data=''.join('event: '+kind+'\ndata: '+json.dumps(value)+'\n\n' for kind,value in events).encode()
        self.send_response(200);self.send_header('Content-Type','text/event-stream')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)


if __name__=='__main__':
    # Both endpoints live in this isolated container's loopback namespace.
    child=os.fork()
    if child==0:
        mcp=ThreadingHTTPServer(('127.0.0.1',8010),MCP)
        threading.Thread(target=mcp.serve_forever,daemon=True).start()
        ThreadingHTTPServer(('127.0.0.1',8099),Provider).serve_forever()
        os._exit(0)
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/scratch','CODEX_HOME':str(home),
        'LANG':'C.UTF-8','HEARTH_BROKER_CAPABILITY':os.environ['HEARTH_BROKER_CAPABILITY']}
    os.execve(native,[native,'app-server','--listen','stdio://'],env)
