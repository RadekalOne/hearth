"""Proposal launcher fixtures exercise real stdio; never contact a provider."""
import importlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))

class LaunchTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('relay_launch')
 def test_proposal_scope_and_base_are_checked_before_writing(self):
  source={'mcp/memory/hearth2/a.py':'old\n'}
  with tempfile.TemporaryDirectory() as td:
   target=Path(td)/'candidate'
   import hashlib
   good={'changes':[{'path':next(iter(source)),'base_sha256':hashlib.sha256(b'old\n').hexdigest(),'text':'new\n'}]}
   receipt=self.m.write_proposal(source,good,target)
   self.assertEqual((target/next(iter(source))).read_text(),'new\n');self.assertEqual(receipt['files'],1)
   for change in [{'path':'../escape.py','base_sha256':'a'*64,'text':'bad'}, {'path':next(iter(source)),'base_sha256':'a'*64,'text':'bad'}]:
    with self.assertRaises(self.m.LaunchRefused):self.m.write_proposal(source,{'changes':[change]},Path(td)/'bad')
   self.assertFalse((Path(td)/'bad').exists())
 def test_duplicate_extra_keys_and_large_proposals_refuse(self):
  import hashlib
  p='test/test_hearth2_x.py';source={p:'x'};h=hashlib.sha256(b'x').hexdigest()
  for changes in [[{'path':p,'base_sha256':h,'text':'y','command':'whoami'}], [{'path':p,'base_sha256':h,'text':'y'}]*2, [{'path':p,'base_sha256':h,'text':'x'*65537}]]:
   with tempfile.TemporaryDirectory() as td:
    with self.assertRaises(self.m.LaunchRefused):self.m.write_proposal(source,{'changes':changes},Path(td)/'candidate')
 def test_live_launch_has_durable_no_send_receipt_without_paid_authority(self):
  from offline_relay_state import State
  from datetime import datetime,timezone
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'s.db');launch=self.m.Launcher(state,Path(td))
   result=launch.run({'id':'a'*32,'epoch':0},observation={},snapshot={'test/test_hearth2_x.py':'x'},approval=None,financial_boundary=None)
   self.assertEqual(result['send_state'],'not_sent');self.assertTrue(result['confirmed_empty']);self.assertNotEqual(result['exit_code'],0)
   self.assertEqual(launch.attempt('a'*32)['send_state'],'not_sent')
 def test_one_attempt_fence_survives_restart(self):
  from offline_relay_state import State
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'s.db');job={'id':'a'*32,'epoch':0};first=self.m.Launcher(state,Path(td));first.run(job,observation={},snapshot={},approval=None,financial_boundary=None)
   again=self.m.Launcher(state,Path(td))
   with self.assertRaises(self.m.LaunchRefused):again.run(job,observation={},snapshot={},approval=None,financial_boundary=None)
 def test_fake_native_turn_is_tool_free_and_stops_before_receipt(self):
  from relay_native import NativeSession
  import hashlib
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);script=root/'fake.py';trace=root/'trace';p='test/test_hearth2_x.py'
   proposal={'changes':[{'path':p,'base_sha256':hashlib.sha256(b'old').hexdigest(),'text':'new'}]}
   script.write_text('''import json,sys
for line in sys.stdin:
 r=json.loads(line);m=r['method']
 with open(sys.argv[1],'a') as f:f.write(m+'\\n')
 if m=='thread/start':result={'thread':{'id':'fixture-thread'}}
 elif m=='turn/start':result={'turn':{'id':'fixture-turn'}}
 else:result={}
 if 'id' in r:print(json.dumps({'id':r['id'],'result':result}),flush=True)
 if m=='turn/start':
  print(json.dumps({'method':'item/completed','params':{'threadId':'fixture-thread','turnId':'fixture-turn','item':{'type':'agentMessage','text':sys.argv[2]}}}),flush=True)
  print(json.dumps({'method':'turn/completed','params':{'threadId':'fixture-thread','turn':{'id':'fixture-turn','status':'completed'}}}),flush=True)
''')
   with NativeSession.fixture([sys.executable,'-I',str(script),str(trace),json.dumps(proposal)],root) as native:
    got=native.fixture_proposal('synthetic prompt')
   self.assertEqual(got,proposal);self.assertTrue(native.confirmed_empty)
   self.assertEqual(trace.read_text().count('turn/start'),1)
if __name__=='__main__':unittest.main()
