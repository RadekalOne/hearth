"""Offline root launch-boundary tests; no native account or provider call."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
REQUEST={'model':'gpt-6.1-sol','cwd':'/scratch','approvalPolicy':'never',
         'sandbox':'read-only','ephemeral':True}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        for name in ['native_rpc','native_model_audit','native_thread_launcher']:
            self.assertIsNotNone(importlib.util.find_spec('hearth2.'+name),name+' not implemented')
        self.rpc=importlib.import_module('hearth2.native_rpc')
        self.audit=importlib.import_module('hearth2.native_model_audit')
        self.launcher=importlib.import_module('hearth2.native_thread_launcher')
        self.guard=importlib.import_module('hearth2.native_model_guard')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.binary=self.root/'native'
        raw=json.dumps({'models':[{'slug':'gpt-6.1-sol'}]},indent=2).encode()
        self.binary.write_bytes(b'fixture'+raw+b'\0')
        self.binary_pin=hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.catalog_pin=hashlib.sha256(raw).hexdigest()
        self.t=100.;self.rows=[];self.calls=[]
        owner=self
        class Client:
            session_id='1'*32;last_request_id=None;last_request_method=None
            def initialize(self): owner.calls.append('initialize')
            def model_list(self):
                owner.calls.append('model/list');self.last_request_id=2;self.last_request_method='model/list'
                return owner.reply('model/list',2,{'data':[{'id':'gpt-6.1-sol','model':'gpt-6.1-sol'}],'nextCursor':None})
            def thread_start(self,request,*,before_send=None):
                if before_send:before_send()
                owner.calls.append(('thread/start',dict(request)))
                return owner.reply('thread/start',3,{'model':request['model'],
                    'sandbox':{'type':'readOnly','networkAccess':False},'thread':{'id':'test'}})
        self.client=Client()
    def reply(self,method,ident,result):
        raw=json.dumps({'id':ident,'result':result},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
        return self.rpc.NativeReply(method,ident,'1'*32,raw,'2026-11-10T14:00:00+00:00',100.)
    def record(self,row): self.rows.append(dict(row));return True
    def build(self,**changes):
        args=dict(mounted_binary=self.binary,expected_binary_sha256=self.binary_pin,
            expected_catalog_sha256=self.catalog_pin,record_decision=self.record,
            pre_thread_fence=lambda:True,monotonic=lambda:self.t)
        args.update(changes)
        return self.launcher.CodexThreadLauncher(self.client,**args)
    def test_fresh_catalog_hash_rpc_id_session_and_timestamp_are_recorded_before_thread(self):
        expected=self.client.model_list().sha256;self.calls=[]
        original=self.client.thread_start
        def start(request,**kw):
            self.assertEqual(self.rows[-1]['client_list_sha256'],expected)
            self.assertEqual(self.rows[-1]['client_list_rpc_id'],2)
            return original(request,**kw)
        self.client.thread_start=start
        result=self.build().launch_thread(REQUEST)
        self.assertEqual(result['model'],'gpt-6.1-sol')
        self.assertEqual(self.rows[0]['client_list_rpc_session'],'1'*32)
        self.assertEqual(self.rows[0]['client_list_received_at'],'2026-11-10T14:00:00+00:00')
        self.assertTrue(self.rows[0]['client_list_fresh'])
        self.assertEqual([x for x in self.calls if isinstance(x,tuple)],[('thread/start',REQUEST)])
    def test_unknown_model_refuses_with_catalog_provenance_and_no_thread(self):
        with self.assertRaises(self.guard.ModelSelectionRefused):
            self.build().launch_thread({**REQUEST,'model':'unsupported'})
        self.assertEqual(self.rows[0]['reason'],'model_not_allowed')
        self.assertEqual(self.rows[0]['client_list_rpc_id'],2)
        self.assertEqual(len(self.rows[0]['client_list_sha256']),64)
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_stale_or_future_monotonic_catalog_refuses_with_record(self):
        for t in [161.,99.,float('nan')]:
            self.t=t;self.rows=[];self.calls=[]
            with self.subTest(t=t),self.assertRaises(self.guard.ModelSelectionRefused):
                self.build().launch_thread(REQUEST)
            self.assertEqual(self.rows[-1]['reason'],'client_list_stale')
            self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_final_fence_rechecks_freshness_after_model_audit(self):
        def fence():self.t=161.;return True
        with self.assertRaises(self.guard.ModelSelectionRefused):
            self.build(pre_thread_fence=fence).launch_thread(REQUEST)
        self.assertEqual(self.rows[-1]['reason'],'client_list_stale')
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_freshness_is_rechecked_after_transport_serialization_delay(self):
        original=self.client.thread_start
        def delayed(request,*,before_send=None):
            self.t=161.
            return original(request,before_send=before_send)
        self.client.thread_start=delayed
        with self.assertRaises(self.guard.ModelSelectionRefused):self.build().launch_thread(REQUEST)
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_authority_is_rechecked_after_transport_serialization_delay(self):
        permit=[True];original=self.client.thread_start
        def delayed(request,*,before_send=None):
            permit[0]=False
            return original(request,before_send=before_send)
        self.client.thread_start=delayed
        with self.assertRaises(self.launcher.NativeLaunchRefused):
            self.build(pre_thread_fence=lambda:permit[0]).launch_thread(REQUEST)
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_revoked_fence_refuses_and_records_distinct_authority_failure(self):
        with self.assertRaises(self.launcher.NativeLaunchRefused):
            self.build(pre_thread_fence=lambda:False).launch_thread(REQUEST)
        self.assertEqual(self.rows[-1]['failure_class'],'authority')
        self.assertEqual(self.rows[-1]['reason'],'pre_thread_fence_refused')
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_unexpected_checker_error_keeps_catalog_evidence_and_audit(self):
        with patch.object(self.guard,'_check',side_effect=RuntimeError('secret detail')):
            with self.assertRaises(self.guard.ModelSelectionRefused):self.build().launch_thread(REQUEST)
        self.assertEqual(self.rows[-1]['failure_class'],'guard_error')
        self.assertEqual(self.rows[-1]['client_list_rpc_id'],2)
        self.assertNotIn('secret detail',json.dumps(self.rows))
    def test_audit_exception_blocks_native_and_is_not_retried(self):
        n=[]
        def failed(row):n.append(row);raise OSError('full')
        gate=self.build(record_decision=failed)
        with self.assertRaises(OSError):gate.launch_thread(REQUEST)
        with self.assertRaises(self.launcher.NativeLaunchConsumed):gate.launch_thread(REQUEST)
        self.assertEqual(len(n),1);self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_single_use_prevents_a_second_thread_and_catalog_request(self):
        gate=self.build();gate.launch_thread(REQUEST)
        with self.assertRaises(self.launcher.NativeLaunchConsumed):gate.launch_thread(REQUEST)
        self.assertEqual(self.calls.count('model/list'),1)
        self.assertEqual(len([x for x in self.calls if isinstance(x,tuple)]),1)
    def test_missing_model_list_is_audited_setup_failure_not_selection(self):
        def failed():raise self.rpc.NativeRpcError('model/list',2,'remote_error')
        self.client.model_list=failed
        with self.assertRaises(self.launcher.NativeLaunchRefused):self.build().launch_thread(REQUEST)
        self.assertEqual(self.rows[-1]['failure_class'],'native_setup')
        self.assertEqual(self.rows[-1]['reason'],'client_list_unavailable')
        self.assertEqual(self.rows[-1]['native_rpc_id'],2)
        self.assertEqual(self.rows[-1]['native_rpc_method'],'model/list')
        self.assertIsNone(self.rows[-1]['client_list_sha256'])
    def test_naive_audit_clock_is_not_silently_treated_as_local_time(self):
        with self.assertRaises(self.guard.ModelAuditUnavailable):
            self.build(clock=lambda:datetime(2026,11,10)).launch_thread(REQUEST)
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
    def test_native_thread_error_is_audited_as_setup_not_model_selection(self):
        def failed(request,*,before_send=None):
            if before_send:before_send()
            raise self.rpc.NativeRpcError('thread/start',3,'remote_error')
        self.client.thread_start=failed
        with self.assertRaises(self.rpc.NativeRpcError):self.build().launch_thread(REQUEST)
        self.assertEqual(self.rows[-1]['failure_class'],'native_setup')
        self.assertEqual(self.rows[-1]['reason'],'thread_start_error')
    def test_model_list_error_response_keeps_hash_rpc_session_and_timestamp(self):
        raw=json.dumps({'id':2,'error':{'code':-1,'message':'untrusted detail'}},sort_keys=True,separators=(',',':')).encode()
        response=self.rpc.NativeReply('model/list',2,'1'*32,raw,'2026-11-10T14:00:00+00:00',100.)
        def failed():
            raise self.rpc.NativeRpcError('model/list',2,'remote_error',response.sha256,response=response)
        self.client.model_list=failed
        with self.assertRaises(self.launcher.NativeLaunchRefused):self.build().launch_thread(REQUEST)
        row=self.rows[-1]
        self.assertEqual(row['client_list_sha256'],response.sha256)
        self.assertEqual(row['client_list_rpc_id'],2)
        self.assertEqual(row['client_list_rpc_session'],'1'*32)
        self.assertEqual(row['client_list_received_at'],response.received_at)
        self.assertEqual(row['client_list_status'],'error')
        self.assertNotIn('untrusted detail',json.dumps(row))
    def test_journal_is_private_append_only_and_detects_corrupt_tail(self):
        journal=self.audit.RootModelDecisionJournal(self.root)
        self.assertIs(journal.record({'reason':'first'}),True)
        self.assertIs(journal.record({'reason':'second'}),True)
        self.assertEqual([x['audit_seq'] for x in journal.read_records()],[1,2])
        p=self.root/'model-decisions.jsonl';self.assertEqual(p.stat().st_mode&0o777,0o600)
        with p.open('ab') as f:f.write(b'{bad')
        before=p.read_bytes()
        with self.assertRaises(self.guard.ModelAuditUnavailable):journal.record({'reason':'third'})
        self.assertEqual(p.read_bytes(),before)
    def test_journal_refuses_symlink_and_nonprivate_directory(self):
        target=self.root/'target';target.write_text('')
        (self.root/'model-decisions.jsonl').symlink_to(target)
        with self.assertRaises(self.guard.ModelAuditUnavailable):self.audit.RootModelDecisionJournal(self.root).record({})
        (self.root/'model-decisions.jsonl').unlink();self.root.chmod(0o755)
        with self.assertRaises(self.guard.ModelAuditUnavailable):self.audit.RootModelDecisionJournal(self.root).record({})


class RpcTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.native_rpc'),'native_rpc not implemented')
        self.rpc=importlib.import_module('hearth2.native_rpc')
    def peer(self,mode='normal',**opts):
        script='''import sys,json,time
mode=sys.argv[1]
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r:continue
 if mode=='hang':time.sleep(5);continue
 if mode=='duplicate':print('{"id":1,"id":1,"result":{}}',flush=True);continue
 if mode=='oversize':print('x'*4096,flush=True);continue
 if mode=='wrongid':print(json.dumps({'id':999,'result':{}}),flush=True);continue
 if mode=='remote_model_error' and r['method']=='model/list':
  print(json.dumps({'id':r['id'],'error':{'code':-1,'message':'untrusted remote detail'}}),flush=True);continue
 result={'userAgent':'fixture'} if r['method']=='initialize' else {'data':[],'nextCursor':None}
 print(json.dumps({'id':r['id'],'result':result}),flush=True)
'''
        p=subprocess.Popen([sys.executable,'-u','-c',script,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        def close():
            if p.poll() is None:p.kill()
            p.wait(timeout=3);p.stdin.close();p.stdout.close()
        self.addCleanup(close)
        return self.rpc.NativeRpcClient(p.stdout,p.stdin,**opts)
    def test_real_pipe_protocol_owns_ids_and_hashes_exact_response(self):
        client=self.peer();client.initialize();reply=client.model_list()
        self.assertEqual(reply.rpc_id,2);self.assertEqual(reply.method,'model/list')
        self.assertEqual(reply.sha256,hashlib.sha256(reply.canonical).hexdigest())
        self.assertEqual(reply.value,{'data':[],'nextCursor':None})
        changed=reply.value;changed['data'].append('tampered');self.assertEqual(reply.value['data'],[])
    def test_duplicate_wrong_id_oversize_and_timeout_refuse(self):
        for mode in ['duplicate','wrongid','oversize','hang']:
            with self.subTest(mode=mode),self.assertRaises(self.rpc.NativeRpcError):
                self.peer(mode,timeout_seconds=.2,max_frame=1024).initialize()
    def test_turn_exists_only_with_public_context_and_no_arbitrary_rpc_api(self):
        client=self.peer()
        self.assertTrue(callable(getattr(client,'turn_start',None)))
        with self.assertRaises(self.rpc.NativeRpcError):client._exchange('turn/start',{})
    def test_real_pipe_remote_error_retains_owned_response_evidence(self):
        client=self.peer('remote_model_error');client.initialize()
        with self.assertRaises(self.rpc.NativeRpcError) as error:client.model_list()
        failure=error.exception
        self.assertEqual(failure.rpc_id,2)
        self.assertEqual(failure.response_sha256,failure.response.sha256)
        self.assertEqual(failure.response.session_id,client.session_id)
        self.assertEqual(failure.response.method,'model/list')
        self.assertTrue(failure.response.received_at.endswith('+00:00'))
    def test_rpc_serialization_wait_is_bounded(self):
        client=self.peer(timeout_seconds=.05)
        acquired=threading.Event()
        def hold():
            with client._lock:acquired.set();time.sleep(.3)
        thread=threading.Thread(target=hold);thread.start();acquired.wait(1)
        try:
            with self.assertRaises(self.rpc.NativeRpcError) as error:client.initialize()
            self.assertEqual(error.exception.code,'serialization_timeout')
        finally:thread.join(1)


if __name__=='__main__':unittest.main()
