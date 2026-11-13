"""Native metadata/financial gating: fake child protocol, never a model/provider."""
import importlib,json,sys,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))

class NativeTests(unittest.TestCase):
 def setUp(self):
  self.m=importlib.import_module('relay_native');self.now=datetime.now(timezone.utc)
  self.obs={'observed_at':self.now.isoformat(),'account_type':'chatgpt','requires_auth':True,'model_present':True,'binary_verified':True,
   'rates':{'limitId':'codex','primary':{'usedPercent':7,'windowDurationMins':10080,'resetsAt':int(self.now.timestamp())+1000},'secondary':None,
    'credits':{'hasCredits':False,'unlimited':False},'rateLimitReachedType':None},'rpc_evidence':{'account':{'id':1,'sha256':'a'*64},'limits':{'id':2,'sha256':'b'*64}}}
 def test_capacity_is_live_evidence_not_financial_authority(self):
  result=self.m.assess_capacity(self.obs,self.now)
  self.assertTrue(result['capacity_available']);self.assertFalse(result['inference_authorized'])
  self.assertFalse(result['included_only_verified']);self.assertIn('financial',result['reason'])
 def test_exhausted_stale_unknown_or_paid_credit_capacity_refuses(self):
  import copy
  for mutate in [lambda x:x.update(observed_at=(self.now-timedelta(seconds=61)).isoformat()),
    lambda x:x.update(account_type='apiKey'),lambda x:x['rates']['primary'].update(usedPercent=100),
    lambda x:x['rates'].update(credits={'hasCredits':True,'unlimited':False}),lambda x:x['rates'].update(primary=None),
    lambda x:x.update(model_present=False),lambda x:x['rates']['primary'].update(resetsAt=0)]:
   obs=copy.deepcopy(self.obs);mutate(obs);self.assertFalse(self.m.assess_capacity(obs,self.now)['capacity_available'])
 def test_no_per_run_paid_approval_means_zero_turn_calls(self):
  calls=[]
  with self.assertRaises(self.m.NativeRefused):self.m.authorize_turn(self.obs,approval=None,financial_boundary=None,work={'work_id':'x'},now=self.now)
  self.assertEqual(calls,[])
 def test_caller_boolean_cannot_supply_a_financial_boundary(self):
  with self.assertRaises(self.m.NativeRefused):self.m.authorize_turn(self.obs,approval={'approved':True},financial_boundary={'included_only':True},work={'work_id':'x'},now=self.now)
 def test_account_observation_redacts_email_and_token_fields(self):
  a={'account':{'type':'chatgpt','email':'private@example.test','accessToken':'synthetic-secret'},'requiresOpenaiAuth':True}
  r=self.m.sanitize_observation(a,{'rateLimits':self.obs['rates']},{'data':[{'id':'gpt-6.1-sol','model':'gpt-6.1-sol'}],'nextCursor':None},self.now,{})
  self.assertNotIn('private',json.dumps(r));self.assertNotIn('synthetic-secret',json.dumps(r));self.assertEqual(r['account_type'],'chatgpt')
 def test_incomplete_or_substituted_model_catalog_refuses(self):
  for models in [{'data':[{'model':'other'}],'nextCursor':None},{'data':[{'model':'gpt-6.1-sol'}],'nextCursor':'more'}]:
   r=self.m.sanitize_observation({'account':{'type':'chatgpt'},'requiresOpenaiAuth':True},{'rateLimits':self.obs['rates']},models,self.now,{})
   self.assertFalse(r['model_present'])
 def test_fixture_native_stdio_metadata_has_no_turn_start(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);trace=root/'calls.jsonl';script=root/'fake.py'
   script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line);m=r['method']
 with open(sys.argv[1],'a') as f:f.write(m+'\\n')
 if 'id' not in r:continue
 values={'initialize':{},'account/read':{'account':{'type':'chatgpt'},'requiresOpenaiAuth':True},'account/rateLimits/read':{'rateLimits':{'primary':{'usedPercent':1,'resetsAt':9999999999},'secondary':None,'credits':{'hasCredits':False,'unlimited':False}}},'model/list':{'data':[{'id':'gpt-6.1-sol','model':'gpt-6.1-sol'}],'nextCursor':None}}
 print(json.dumps({'id':r['id'],'result':values[m]}),flush=True)
''',encoding='utf-8')
   with self.m.NativeSession.fixture([sys.executable,'-I',str(script),str(trace)],root) as client:observation=client.metadata()
   self.assertTrue(observation['model_present']);self.assertNotIn('turn/start',trace.read_text());self.assertNotIn('thread/start',trace.read_text())
 def test_silent_native_process_is_stopped_with_bounded_failure(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   with self.assertRaises(self.m.NativeRefused):
    with self.m.NativeSession.fixture([sys.executable,'-I','-c','import time;time.sleep(10)'],root,timeout=.2) as client:client.metadata()
   self.assertTrue(client.confirmed_empty)
class NativeHardeningTests(unittest.TestCase):
 def test_nested_metadata_retains_only_documented_numeric_fields(self):
  from relay_native import sanitize_observation
  now=datetime.now(timezone.utc)
  rates={'primary':{'usedPercent':1,'resetsAt':9999999999,'accessToken':'DO-NOT-KEEP'},'secondary':None,'credits':{'hasCredits':False,'unlimited':False,'credential':'DO-NOT-KEEP'}}
  result=sanitize_observation({'account':{'type':'chatgpt'}},{'rateLimits':rates},{'data':[]},now,{})
  self.assertNotIn('DO-NOT-KEEP',json.dumps(result))
 def test_nonreading_child_cannot_block_request_write(self):
  from relay_native import NativeSession,NativeRefused
  import time
  with tempfile.TemporaryDirectory() as td:
   start=time.monotonic()
   with self.assertRaises(NativeRefused):
    with NativeSession.fixture([sys.executable,'-I','-c','import time;time.sleep(2)'],Path(td),timeout=.1) as c:
     c._send({'method':'initialize','padding':'x'*120000})
   self.assertLess(time.monotonic()-start,1.5)
   self.assertTrue(c.confirmed_empty)
 def test_malformed_retained_account_and_rate_fields_cannot_persist_credentials(self):
  from relay_native import sanitize_observation
  rates={'limitId':'TOKEN-SECRET','planType':'TOKEN-SECRET','rateLimitReachedType':{'token':'TOKEN-SECRET'},'primary':None,'secondary':None,'credits':None}
  for a,r in [({'type':{'accessToken':'TOKEN-SECRET'}},{'token':'TOKEN-SECRET'}),({'type':'TOKEN-SECRET'},'TOKEN-SECRET')]:
   result=sanitize_observation({'account':a,'requiresOpenaiAuth':r},{'rateLimits':rates},{'data':[]},datetime.now(timezone.utc),{})
   self.assertNotIn('TOKEN-SECRET',json.dumps(result))
if __name__=='__main__':unittest.main()
