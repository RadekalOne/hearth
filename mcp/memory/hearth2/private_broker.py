"""Root-held Broker grant via one private per-run Unix socket, never worker auth.

The root driver may expose only this socket inode to its workload. No worker
bearer is accepted or returned. Host root and the bounded upstream remain trusted.
Creating this object installs no service or listener; start is explicit.
"""
import os
from pathlib import Path
import socketserver
import stat
import threading
from .broker import BrokerError
from .broker_protocol import TOOLS
from .native_rpc import _decode,canonical_object
from .store import RecordError


def error_response(request,code=-32001):
    ident=request.get('id') if type(request) is dict else None
    if not (type(ident) is str and len(ident)<=256 or type(ident) is int and ident.bit_length()<=63):ident=None
    return {'jsonrpc':'2.0','id':ident,'error':{'code':code,'message':'Private read request denied'}}


class PrivateBrokerChannel:
    def __init__(self,broker,controller,claim,*,directory,wing,room):
        self.broker,self.controller,self.claim=broker,controller,claim
        self.directory=Path(directory);self.socket_path=self.directory/'broker.sock'
        self.wing,self.room=wing,room
        self.__cap=None;self._server=None;self._thread=None;self._inode=None
        self._used=False;self._closed=False

    def metadata(self):
        return {'transport':'private_unix','socket_path':str(self.socket_path),'closed':self._closed}

    def __repr__(self):return 'PrivateBrokerChannel('+str(self.socket_path)+')'

    def check(self):
        if self._closed or self.__cap is None:raise BrokerError('private grant unavailable')
        self.broker.check(self.__cap)
        return True

    def _directory(self):
        if (os.name!='posix' or os.geteuid()!=0 or not self.directory.is_absolute()
                or self.directory.resolve()!=self.directory or len(os.fsencode(self.socket_path))>100):
            raise RecordError('private root socket directory required')
        info=self.directory.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o700:
            raise RecordError('private root socket directory required')

    def start(self):
        if self._used or self._closed:raise RecordError('private channel already consumed')
        self._used=True;self._directory()
        if self.socket_path.exists() or self.socket_path.is_symlink():raise RecordError('private socket path occupied')
        owner=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.request.settimeout(2)
                request=None
                try:
                    raw=self.rfile.readline(65537)
                    if len(raw)>65536 or not raw.endswith(b'\n'):raise BrokerError()
                    try:request=_decode(raw)
                    except Exception:
                        self.wfile.write(canonical_object(error_response(None,-32700))+b'\n');return
                    reply=owner._dispatch(request)
                    data=b'null' if reply is None else canonical_object(reply)
                    if len(data)>1_000_000:raise BrokerError()
                except Exception:data=canonical_object(error_response(request))
                try:self.wfile.write(data+b'\n')
                except Exception:pass
        class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
            daemon_threads=True;block_on_close=False;request_queue_size=4
            def __init__(self,*args,**kwargs):
                self.slots=threading.BoundedSemaphore(8);super().__init__(*args,**kwargs)
            def process_request(self,request,address):
                if not self.slots.acquire(blocking=False):self.shutdown_request(request);return
                try:super().process_request(request,address)
                except Exception:self.slots.release();raise
            def process_request_thread(self,request,address):
                try:super().process_request_thread(request,address)
                finally:self.slots.release()
            def handle_error(self,*args):pass
        try:
            self.__cap=self.broker.mint(self.controller,self.claim,wing=self.wing,room=self.room)
            self._server=Server(str(self.socket_path),Handler)
            info=self.socket_path.stat();self._inode=(info.st_dev,info.st_ino)
            self.socket_path.chmod(0o666)
            self._thread=threading.Thread(target=self._server.serve_forever,kwargs={'poll_interval':.05},daemon=True)
            self._thread.start()
            return self.metadata()
        except Exception:
            self.close();raise RecordError('private Broker channel unavailable') from None

    def _dispatch(self,request):
        try:return self._dispatch_authorized(request)
        except Exception:return error_response(request)

    def _dispatch_authorized(self,request):
        if (type(request) is not dict or set(request)-{'jsonrpc','id','method','params'}
                or request.get('jsonrpc')!='2.0' or type(request.get('method')) is not str
                or 'id' in request and type(request['id']) not in {str,int}):raise BrokerError()
        self.broker.check(self.__cap)
        params=request.get('params',{})
        if type(params) is not dict:raise BrokerError()
        if '_meta' in params:
            meta=params['_meta']
            if type(meta) is not dict or 'progressToken' in meta and type(meta['progressToken']) not in {str,int}:
                raise BrokerError()
            params={k:v for k,v in params.items() if k!='_meta'}
        method=request['method'];ident=request.get('id')
        if method=='notifications/initialized' and 'id' not in request:
            self.broker.check(self.__cap);return None
        if 'id' not in request:raise BrokerError()
        if method=='initialize':
            version=params.get('protocolVersion')
            if type(version) is not str or not 1<=len(version)<=64:raise BrokerError()
            result={'protocolVersion':version if version in {'2024-11-05','2025-03-26','2025-06-18'} else '2024-11-05',
                'capabilities':{'tools':{}},'serverInfo':{'name':'hearth-private-task-memory','version':'1'}}
        elif method=='tools/list' and not params:result={'tools':TOOLS}
        elif method=='tools/call':
            if set(params)!={'name','arguments'}:raise BrokerError()
            value=self.broker.read(self.__cap,params['name'],params['arguments'])
            result={'content':[{'type':'text','text':canonical_object(value).decode('ascii')}]}
        else:return {'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not permitted'}}
        self.broker.check(self.__cap)
        return {'jsonrpc':'2.0','id':ident,'result':result}

    def close(self):
        if self._closed:return
        self._closed=True
        try:
            if self.__cap is not None:self.broker.revoke(self.controller,self.__cap)
        finally:
            self.__cap=None
            if self._server is not None:
                if self._thread is not None and self._thread.is_alive():self._server.shutdown()
                self._server.server_close()
            if self._inode is not None:
                try:
                    info=self.socket_path.lstat()
                    if stat.S_ISSOCK(info.st_mode) and (info.st_dev,info.st_ino)==self._inode:self.socket_path.unlink()
                except FileNotFoundError:pass
