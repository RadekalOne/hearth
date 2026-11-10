"""Concrete one-attempt native thread adapter; never creates a provider turn.

The root driver owns the isolated process, mount proof, original container,
claim/deadline fencing and cleanup. No service or executable is selected here.
"""
from datetime import datetime, timezone
import math
import threading
import time
import uuid
from .native_model_guard import start_codex_thread, ModelSelectionRefused, ModelAuditUnavailable
from .native_rpc import NativeReply, NativeRpcError


class NativeLaunchRefused(RuntimeError):pass
class NativeLaunchConsumed(RuntimeError):pass


class CodexThreadLauncher:
    def __init__(self,client,*,mounted_binary,expected_binary_sha256,expected_catalog_sha256,
                 record_decision,pre_thread_fence,clock=None,monotonic=time.monotonic,max_catalog_age=60):
        if (not callable(record_decision) or not callable(pre_thread_fence)
                or type(max_catalog_age) not in (int,float) or not math.isfinite(max_catalog_age)
                or not 0<max_catalog_age<=60):raise ValueError('trusted launch dependencies required')
        self.client,self.binary=client,mounted_binary
        self.binary_pin,self.catalog_pin=expected_binary_sha256,expected_catalog_sha256
        self.record,self.fence=record_decision,pre_thread_fence
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.monotonic,self.max_age=monotonic,max_catalog_age
        self.attempt_id=uuid.uuid4().hex;self._used=False;self._lock=threading.Lock()

    def _metadata(self,reply):
        now=self.clock()
        if not isinstance(now,datetime) or now.tzinfo is None:
            raise ModelAuditUnavailable('trusted aware audit clock required')
        age=None
        if reply is not None:
            value=self.monotonic()-reply.received_monotonic
            if type(value) in (int,float) and math.isfinite(value):age=value
        return {'launch_attempt_id':self.attempt_id,
            'client_list_sha256':reply.sha256 if reply else None,
            'client_list_rpc_id':reply.rpc_id if reply else None,
            'client_list_rpc_session':reply.session_id if reply else self.client.session_id,
            'client_list_received_at':reply.received_at if reply else None,
            'client_list_age_seconds':age,
            'client_list_fresh':age is not None and 0<=age<=self.max_age,
            'decision_at':now.astimezone(timezone.utc).isoformat()}

    def _audit(self,decision,reply,*,enforce_fresh=False):
        row={**decision,**self._metadata(reply)}
        stale=enforce_fresh and not row['client_list_fresh'] and row.get('outcome')=='allowed'
        if stale:row.update(outcome='refused',reason='client_list_stale',failure_class='model_selection')
        if self.record(dict(row)) is not True:raise ModelAuditUnavailable('durable model decision acknowledgement required')
        if stale:raise ModelSelectionRefused(row)
        return True

    def launch_thread(self,request):
        with self._lock:
            if self._used:raise NativeLaunchConsumed('native launch attempt already consumed')
            self._used=True
        reply=None
        try:
            self.client.initialize();reply=self.client.model_list()
            if (not isinstance(reply,NativeReply) or reply.method!='model/list'
                    or reply.session_id!=self.client.session_id
                    or reply.rpc_id!=self.client.last_request_id):raise ValueError('catalog origin mismatch')
            models=reply.value
        except Exception as error:
            failed_reply=error.response if isinstance(error,NativeRpcError) else None
            catalog_reply=failed_reply if failed_reply is not None and error.method=='model/list' else None
            self._audit({'kind':'native_launch_setup','outcome':'refused',
                'reason':'client_list_unavailable','failure_class':'native_setup',
                'client_list_status':'error' if catalog_reply else 'unavailable',
                'native_response_sha256':error.response_sha256 if isinstance(error,NativeRpcError) else None,
                'native_rpc_id':error.rpc_id if isinstance(error,NativeRpcError) else None,
                'native_rpc_method':error.method if isinstance(error,NativeRpcError) else None},catalog_reply)
            raise NativeLaunchRefused('client_list_unavailable') from None
        def audit(decision):return self._audit(decision,reply,enforce_fresh=True)
        def create(params):
            checked=False
            def before_send():
                nonlocal checked
                try:authorized=self.fence() is True
                except Exception:authorized=False
                if not authorized:
                    self._audit({'kind':'native_launch_authority','outcome':'refused',
                        'reason':'pre_thread_fence_refused','failure_class':'authority'},reply)
                    raise NativeLaunchRefused('pre_thread_fence_refused')
                if not self._metadata(reply)['client_list_fresh']:
                    row={'kind':'native_model_selection','outcome':'allowed','reason':'exact_model_in_both_catalogs','failure_class':None}
                    self._audit(row,reply,enforce_fresh=True)
                checked=True
            try:
                result=self.client.thread_start(params,before_send=before_send).value
                if (result.get('model')!=params['model']
                        or result.get('sandbox')!={'type':'readOnly','networkAccess':False}):
                    raise NativeRpcError('thread/start',self.client.last_request_id,'effective_profile_mismatch')
                return result
            except (ModelSelectionRefused,NativeLaunchRefused,ModelAuditUnavailable):raise
            except Exception as error:
                if not checked and not isinstance(error,NativeRpcError):raise
                self._audit({'kind':'native_thread_start_failure','outcome':'failed',
                    'reason':'thread_start_error','failure_class':'native_setup'},reply)
                raise
        return start_codex_thread(request,mounted_binary=self.binary,
            expected_binary_sha256=self.binary_pin,expected_catalog_sha256=self.catalog_pin,
            model_list=models,record_decision=audit,thread_start=create)
