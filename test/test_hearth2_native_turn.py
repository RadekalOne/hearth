"""Credential-free real-pipe controls for one canonical native turn."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import os
from contextlib import contextmanager
sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.native_rpc import NativeRpcClient,NativeRpcError,canonical_object

THREAD={'model':'gpt-6.1-sol','cwd':'/scratch','approvalPolicy':'never','sandbox':'read-only','ephemeral':True}
TURN={'threadId':'thread-owned','input':[{'type':'text','text':'synthetic prompt'}]}
PEER=r'''
import sys,json,time
mode=sys.argv[1]
def send(x):print(json.dumps(x),flush=True)
def notice(method,**params):send({'method':method,'params':params})
def progress():
 for n in range(5000 if mode=='burst' else 160):notice('item/agentMessage/delta',threadId='thread-owned',turnId='turn-owned',delta='x')
for raw in sys.stdin:
 r=json.loads(raw)
 if 'id' not in r:continue
 method=r['method']
 if method=='initialize':result={}
 elif method=='model/list':
  if mode=='controlflood':progress()
  result={'data':[],'nextCursor':None}
 elif method=='thread/start':result={'thread':{'id':'thread-owned'},'model':'gpt-6.1-sol',
  'approvalPolicy':'on-request' if mode=='badpolicy' else 'never','sandbox':{'type':'readOnly','networkAccess':False}}
 elif method=='turn/start':
  if mode=='hang':time.sleep(5);continue
  if mode=='remote':
   send({'id':r['id'],'error':{'code':-32000,'message':'private entitlement detail'}});continue
  if mode=='badturn':
   send({'id':r['id'],'result':{'turn':{'id':{'private':'must-not-log'},'status':'inProgress'}}});continue
  if mode=='preack':progress()
  send({'id':r['id'],'result':{'turn':{'id':'turn-owned','status':'inProgress','items':[],'error':None}}})
  if mode!='preack':progress()
  if mode=='request':send({'id':900,'method':'item/commandExecution/requestApproval','params':{}});continue
  if mode=='foreign':notice('turn/completed',threadId='thread-foreign',turn={'id':'turn-owned','status':'completed','items':[]});continue
  notice('item/completed',threadId='thread-owned',turnId='turn-owned',item={'type':'agentMessage','id':'message',
   'phase':'final_answer','text':'x'*17000 if mode=='longfinal' else 'done'})
  units={'inputTokens':10,'cachedInputTokens':0,'outputTokens':5,'reasoningOutputTokens':0,'totalTokens':15}
  notice('thread/tokenUsage/updated',threadId='thread-owned',turnId='turn-owned',tokenUsage={'total':units,'last':units})
  notice('turn/completed',threadId='thread-owned',turn={'id':'turn-owned','status':'completed','items':[],'error':None})
  continue
 else:send({'id':r['id'],'error':{'message':'method denied'}});continue
 send({'id':r['id'],'result':result})
'''


class NativeTurnTests(unittest.TestCase):
    def peer(self,mode='normal',*,start_thread=True,**options):
        self.assertTrue(callable(getattr(NativeRpcClient,'turn_start',None)),'canonical turn API missing')
        process=subprocess.Popen([sys.executable,'-u','-c',PEER,mode],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        def close():
            if process.poll() is None:process.kill()
            process.wait(timeout=3);process.stdin.close();process.stdout.close()
        self.addCleanup(close)
        options.setdefault('turn_timeout_seconds',45) # Explicit synthetic fixture policy, not provider timing.
        client=NativeRpcClient(process.stdout,process.stdin,**options);client.initialize()
        if start_thread:client.thread_start(THREAD)
        return client

    def run_turn(self,client,request=None,**overrides):
        self.rows=[];self.stops=[]
        def record(row):self.rows.append(row);return True
        def stop():self.stops.append(True);return True
        args={'before_send':lambda:True,'record_event':record,'stop_workload':stop};args.update(overrides)
        return client.turn_start(TURN if request is None else request,**args)

    def test_more_than64_events_complete_with_bound_ids_usage_and_durable_audit(self):
        client=self.peer();result=self.run_turn(client)
        self.assertEqual(result.native_result['state'],'completed')
        self.assertEqual(result.native_result['text'],'done')
        self.assertEqual(result.thread_id,'thread-owned');self.assertEqual(result.turn_id,'turn-owned')
        self.assertGreater(result.event_count,64);self.assertEqual(self.stops,[])
        self.assertEqual(self.rows[0]['kind'],'native_turn_dispatch_intent')
        self.assertEqual(self.rows[-1]['kind'],'native_turn_terminal')
        self.assertEqual(self.rows[-1]['turn_id'],'turn-owned')
        self.assertIsNone(result.native_result['usage']['actual_charge'])
        changed=result.native_result;changed['text']='forged'
        self.assertEqual(result.native_result['text'],'done')
        self.assertNotIn('synthetic prompt',json.dumps(self.rows))

    def test_pre_ack_events_are_bounded_and_bound_after_owned_response(self):
        result=self.run_turn(self.peer('preack'))
        self.assertEqual(result.native_result['state'],'completed');self.assertGreater(result.event_count,64)

    def test_overrides_wrong_ids_and_subclasses_refuse_before_turn_write(self):
        class Text(str):pass
        cases=[{**TURN,'model':'other'},{**TURN,'config':{}},{**TURN,'threadId':'other'},
            {**TURN,'input':[{'type':'text','text':Text('x')}]},{**TURN,'input':[{'type':'text','text':'x','extra':True}]},
            {**TURN,'input':[{'type':'text','text':'x'*2049}]},None,{'threadId':'thread-owned'}]
        for request in cases:
            client=self.peer()
            with self.subTest(request=type(request).__name__),self.assertRaises(NativeRpcError):
                self.run_turn(client,request={} if request is None else request)
            self.assertEqual(client.last_request_method,'thread/start');self.assertEqual(self.stops,[True])

    def test_fence_or_audit_refusal_sends_no_turn_and_requests_stop(self):
        for change in [{'before_send':lambda:False},{'record_event':lambda row:False}]:
            client=self.peer()
            with self.subTest(change=list(change)),self.assertRaises(NativeRpcError):self.run_turn(client,**change)
            self.assertEqual(client.last_request_method,'thread/start');self.assertEqual(self.stops,[True])

    def test_event_byte_deadline_and_final_text_bounds_stop_workload(self):
        for mode,options in [('normal',{'max_turn_events':100}),('normal',{'max_turn_bytes':1024}),
            ('hang',{'turn_timeout_seconds':.05}),('longfinal',{})]:
            client=self.peer(mode,**options)
            with self.subTest(mode=mode,options=options),self.assertRaises(NativeRpcError):self.run_turn(client)
            self.assertEqual(self.stops,[True])

    def test_foreign_terminal_and_server_requests_never_promote_completion(self):
        for mode in ['foreign','request']:
            client=self.peer(mode,turn_timeout_seconds=.1)
            with self.subTest(mode=mode),self.assertRaises(NativeRpcError):self.run_turn(client)
            self.assertEqual(self.stops,[True])

    def test_turn_replay_and_private_bypass_refused(self):
        client=self.peer();self.run_turn(client);last=client.last_request_id
        with self.assertRaises(NativeRpcError):self.run_turn(client)
        self.assertEqual(client.last_request_id,last)
        with self.assertRaises(NativeRpcError):client._exchange('turn/start',TURN)

    def test_control_phase_still_has64_notification_limit(self):
        client=self.peer('controlflood')
        with self.assertRaises(NativeRpcError):client.model_list()

    def test_effective_thread_policy_mismatch_prevents_turn(self):
        client=self.peer('badpolicy')
        with self.assertRaises(NativeRpcError):self.run_turn(client)
        self.assertEqual(client.last_request_method,'thread/start');self.assertEqual(self.stops,[True])

    def test_failed_stop_is_reported_without_retry(self):
        client=self.peer('hang',turn_timeout_seconds=.05);calls=[]
        def stop():calls.append(True);return False
        with self.assertRaises(NativeRpcError) as error:self.run_turn(client,stop_workload=stop)
        self.assertEqual(calls,[True]);self.assertFalse(error.exception.stop_confirmed)

    def test_turn_deadline_caps_initial_ack_wait(self):
        client=self.peer('hang',turn_timeout_seconds=.05);started=time.monotonic()
        with self.assertRaises(NativeRpcError):self.run_turn(client)
        self.assertLess(time.monotonic()-started,1.)

    def test_authority_revoked_during_dispatch_audit_prevents_turn_write(self):
        client=self.peer();live=[True]
        def audit(row):
            if row['kind']=='native_turn_dispatch_intent':live[0]=False
            return True
        with self.assertRaises(NativeRpcError):
            self.run_turn(client,before_send=lambda:live[0],record_event=audit)
        self.assertEqual(client.last_request_method,'thread/start')
        self.assertEqual(self.stops,[True])

    def test_burst_does_not_pay_heavy_fence_cost_for_each_delta(self):
        calls=[]
        def fence():calls.append(time.monotonic());time.sleep(.002);return True
        result=self.run_turn(self.peer('burst',turn_timeout_seconds=1),before_send=fence)
        self.assertGreater(result.event_count,5000)
        self.assertLessEqual(len(calls),12)

    def test_stream_fence_cadence_and_forced_checks(self):
        from hearth2.native_turn import TurnEvents
        now=[0.];calls=[];live=[True]
        client=self.peer();client.monotonic=lambda:now[0]
        def fence():calls.append(now[0]);return live[0]
        stream=TurnEvents(client,'thread-owned',10,fence)
        stream.check();now[0]=.24;stream.check()
        self.assertEqual(len(calls),1)
        live[0]=False;now[0]=.251
        with self.assertRaises(Exception):stream.check()
        self.assertEqual(len(calls),2)
        live[0]=True;stream.check(force=True)
        self.assertEqual(len(calls),3)

    def test_unset_turn_timeout_is_refused_without_sending(self):
        client=self.peer(turn_timeout_seconds=None)
        with self.assertRaises(NativeRpcError):self.run_turn(client)
        self.assertEqual(client.last_request_method,'thread/start')
        self.assertEqual(self.rows[-1]['failure_class'],'timeout_policy_missing')
        self.assertEqual(self.rows[-1]['send_state'],'not_sent')

    def test_failure_audit_distinguishes_not_sent_written_and_remote_error(self):
        cases=[('normal',{'model':'override'},'request_contract','not_sent',False),
            ('hang',None,'deadline_exceeded','request_written_outcome_unknown',True),
            ('remote',None,'native_remote_error','response_received',True)]
        for mode,request,reason,sent,written in cases:
            client=self.peer(mode,turn_timeout_seconds=.05)
            with self.subTest(mode=mode),self.assertRaises(NativeRpcError) as error:
                self.run_turn(client,request=request)
            row=self.rows[-1]
            self.assertEqual(row['failure_class'],reason);self.assertEqual(row['send_state'],sent)
            self.assertIs(row['request_written'],written);self.assertTrue(row['stop_confirmed'])
            self.assertEqual(row['rpc_id'],None if not written else client.last_request_id)
            if mode=='remote':
                self.assertEqual(len(row['response_sha256']),64)
                self.assertEqual(error.exception.response_sha256,row['response_sha256'])
            self.assertNotIn('private entitlement detail',json.dumps(row))
            self.assertNotIn('synthetic prompt',json.dumps(row))

    def test_partial_pipe_write_cannot_be_classified_as_never_sent(self):
        client=self.peer();original=os.write;count=[0]
        def broken(fd,raw):
            if fd!=client.writer.fileno():return original(fd,raw)
            count[0]+=1
            if count[0]==1:return original(fd,raw[:7])
            raise OSError('private local failure')
        with patch('hearth2.native_rpc.os.write',side_effect=broken),self.assertRaises(NativeRpcError):
            self.run_turn(client)
        row=self.rows[-1]
        self.assertEqual(row['send_state'],'partial_write_outcome_unknown')
        self.assertIsNone(row['request_written']);self.assertEqual(row['bytes_written'],7)
        self.assertEqual(row['stage'],'request_write')
        self.assertNotIn('private local failure',json.dumps(row))

    def test_pre_ack_authority_and_event_exhaustion_preserve_cause(self):
        client=self.peer('preack',max_turn_events=100)
        with self.assertRaises(NativeRpcError):self.run_turn(client)
        self.assertEqual(self.rows[-1]['failure_class'],'event_bound_exceeded')
        client=self.peer('preack');tick=[0.];calls=[]
        def clock():tick[0]+=.1;return tick[0]
        client.monotonic=clock
        def fence():calls.append(True);return len(calls)<=2
        with self.assertRaises(NativeRpcError):self.run_turn(client,before_send=fence)
        self.assertEqual(self.rows[-1]['failure_class'],'authority_refused')

    def test_audit_failure_exception_keeps_session_request_and_thread_correlation(self):
        client=self.peer('remote')
        def audit(row):
            if row['kind']!='native_turn_dispatch_intent':raise OSError('private audit detail')
            self.assertEqual(row['send_state'],'possibly_sent_unconfirmed')
            self.assertEqual(row['request_sha256'],hashlib.sha256(canonical_object(TURN)).hexdigest())
            return True
        with self.assertRaises(NativeRpcError) as error:self.run_turn(client,record_event=audit)
        row=error.exception.failure_evidence
        self.assertEqual(row['rpc_session'],client.session_id)
        self.assertEqual(row['thread_id'],'thread-owned');self.assertIsNone(row['turn_id'])
        self.assertEqual(len(row['request_sha256']),64)
        self.assertEqual(row['failure_class'],'native_remote_error')
        self.assertEqual(row['send_state'],'response_received')
        self.assertNotIn('private audit detail',json.dumps(row))

    def test_malformed_native_turn_identity_is_not_copied_into_failure_evidence(self):
        with self.assertRaises(NativeRpcError):self.run_turn(self.peer('badturn'))
        self.assertIsNone(self.rows[-1]['turn_id'])
        self.assertNotIn('must-not-log',json.dumps(self.rows))

    def test_repeated_thread_start_refuses_before_any_second_request(self):
        client=self.peer();last=client.last_request_id
        with self.assertRaises(NativeRpcError):client.thread_start(THREAD)
        self.assertEqual(client.last_request_id,last)
        self.assertEqual(self.run_turn(client).thread_id,'thread-owned')

    def test_failed_first_thread_write_cannot_be_retried(self):
        client=self.peer(start_thread=False)
        with patch.object(client,'_write',side_effect=OSError('synthetic write failure')):
            with self.assertRaises(NativeRpcError):client.thread_start(THREAD)
        last=client.last_request_id
        with self.assertRaises(NativeRpcError):client.thread_start(THREAD)
        self.assertEqual(client.last_request_id,last)

    def test_interrupt_stops_once_audits_and_reraises_original_control_exception(self):
        for phase in ['before_send','after_ack']:
            for kind in [KeyboardInterrupt,SystemExit]:
                client=self.peer();control=kind('private-control-detail')
                def fence():
                    if phase=='before_send':raise control
                    return True
                def audit(row):
                    self.rows.append(row)
                    if row['kind']=='native_turn_started':raise control
                    return True
                with self.subTest(phase=phase,kind=kind),self.assertRaises(kind) as error:
                    self.run_turn(client,before_send=fence,record_event=audit)
                self.assertIs(error.exception,control);self.assertEqual(self.stops,[True])
                self.assertEqual(self.rows[-1]['failure_class'],'interrupted')
                self.assertEqual(self.rows[-1]['send_state'],'not_sent' if phase=='before_send' else 'response_received')
                self.assertNotIn('private-control-detail',json.dumps(self.rows))

    def test_interrupt_while_acquiring_turn_lock_also_stops_and_audits(self):
        for kind in [KeyboardInterrupt,SystemExit]:
            client=self.peer();control=kind('private-lock-detail')
            @contextmanager
            def interrupted(method):
                raise control
                yield
            with patch.object(client,'_serialized',interrupted),self.assertRaises(kind) as error:
                self.run_turn(client)
            self.assertIs(error.exception,control);self.assertEqual(self.stops,[True])
            row=self.rows[-1]
            self.assertEqual(row['stage'],'serialization');self.assertEqual(row['send_state'],'not_sent')
            self.assertEqual(row['failure_class'],'interrupted');self.assertTrue(row['stop_confirmed'])
            self.assertNotIn('private-lock-detail',json.dumps(row))

    def test_outer_lock_exit_interrupt_uses_conservative_unknown_send_evidence(self):
        client=self.peer();original=client._serialized;depth=[0];control=KeyboardInterrupt()
        @contextmanager
        def exit_interrupted(method):
            outer=depth[0]==0;depth[0]+=1
            try:
                with original(method):yield
            finally:depth[0]-=1
            if outer:raise control
        with patch.object(client,'_serialized',exit_interrupted),self.assertRaises(KeyboardInterrupt):
            self.run_turn(client)
        self.assertEqual(self.stops,[True]);row=self.rows[-1]
        self.assertEqual(row['send_state'],'possibly_sent_unconfirmed')
        self.assertIsNone(row['request_written']);self.assertIsNone(row['bytes_written'])

    def test_second_interrupt_inside_stop_does_not_replace_original_or_skip_audit(self):
        client=self.peer();first=KeyboardInterrupt();calls=[]
        def fence():raise first
        def stop():calls.append(True);raise SystemExit()
        with self.assertRaises(KeyboardInterrupt) as error:
            self.run_turn(client,before_send=fence,stop_workload=stop)
        self.assertIs(error.exception,first);self.assertEqual(calls,[True])
        self.assertFalse(self.rows[-1]['stop_confirmed'])


if __name__=='__main__':unittest.main()
