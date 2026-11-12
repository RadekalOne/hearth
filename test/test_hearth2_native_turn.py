"""Credential-free real-pipe controls for one canonical native turn."""
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.native_rpc import NativeRpcClient,NativeRpcError

THREAD={'model':'gpt-6.1-sol','cwd':'/scratch','approvalPolicy':'never','sandbox':'read-only','ephemeral':True}
TURN={'threadId':'thread-owned','input':[{'type':'text','text':'synthetic prompt'}]}
PEER=r'''
import sys,json,time
mode=sys.argv[1]
def send(x):print(json.dumps(x),flush=True)
def notice(method,**params):send({'method':method,'params':params})
def progress():
 for n in range(160):notice('item/agentMessage/delta',threadId='thread-owned',turnId='turn-owned',delta='x')
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
    def peer(self,mode='normal',**options):
        self.assertTrue(callable(getattr(NativeRpcClient,'turn_start',None)),'canonical turn API missing')
        process=subprocess.Popen([sys.executable,'-u','-c',PEER,mode],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        def close():
            if process.poll() is None:process.kill()
            process.wait(timeout=3);process.stdin.close();process.stdout.close()
        self.addCleanup(close)
        client=NativeRpcClient(process.stdout,process.stdin,**options);client.initialize();client.thread_start(THREAD)
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


if __name__=='__main__':unittest.main()
