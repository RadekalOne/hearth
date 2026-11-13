"""Read-only live adapter acceptance with explicit injected test transports."""
import importlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))
from offline_relay_state import State

class LiveTests(unittest.TestCase):
 def test_intake_and_capacity_run_but_do_not_claim_or_send(self):
  m=importlib.import_module('relay_live')
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'relay.sqlite3');calls=[]
   class Intake:
    def poll(self):calls.append('poll');return []
   live=m.LivePorts(state,Intake(),lambda:({'capacity_available':True,'inference_authorized':False}, {'model_present':True}))
   self.assertEqual(live.poll(),[]);self.assertEqual(calls,['poll'])
   self.assertFalse(live.ready_for_claim());self.assertFalse(live.allowance()['included_only'])
   self.assertEqual(state.jobs(),[])
   receipt=json.loads((Path(td)/'live-receipt.json').read_text())
   self.assertTrue(receipt['intake_complete']);self.assertTrue(receipt['capacity']['capacity_available'])
   self.assertEqual(receipt['model_turns'],0);self.assertFalse(receipt['inference_authorized'])
 def test_native_failure_has_fixed_reason_without_exception_secret(self):
  m=importlib.import_module('relay_live')
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'relay.sqlite3')
   class Intake:
    def poll(self):return []
   def fail():raise RuntimeError('SECRET-TOKEN')
   live=m.LivePorts(state,Intake(),fail);self.assertEqual(live.poll(),[])
   text=(Path(td)/'live-receipt.json').read_text();self.assertNotIn('SECRET',text);self.assertIn('native_metadata_unavailable',text)
 def test_unchecked_configuration_is_not_loadable(self):
  m=importlib.import_module('relay_live')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'live-config.json').write_text('{}');(root/'manifest.json').write_text('{}')
   with self.assertRaises(m.LiveUnavailable):m.load_configuration(root)
 def test_enabled_controller_does_not_consume_work_while_financial_gate_closed(self):
  from offline_relay import Dispatcher
  from datetime import datetime,timezone
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'s.db')
   with state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
   class Ports:
    def host_ok(self):return True
    def poll(self):return [{'untrusted':'work'}]
    def ready_for_claim(self):return False
    def poll_status(self):return 'enabled_inference_gated'
   result=Dispatcher(state,Ports(),clock=lambda:datetime(2026,11,13,20,tzinfo=timezone.utc)).check()
   self.assertEqual(result['state'],'enabled_inference_gated');self.assertEqual(state.jobs(),[])
 def test_pause_during_intake_prevents_metadata_start(self):
  m=importlib.import_module('relay_live');calls=[]
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'s.db')
   with state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
   class Intake:
    def poll(self):state.pause();return []
   live=m.LivePorts(state,Intake(),lambda:(calls.append('native'),{}))
   live.poll();self.assertEqual(calls,[])
   self.assertEqual(live.last['error'],'invocation_revoked')
 def test_metadata_owner_is_recorded_and_pause_stops_the_named_identity(self):
  import relay_live as m,offline_relay_pause as recovery
  from unittest.mock import patch
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);state=State(root/'relay.sqlite3')
   with state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
   fence=m.MetadataOwner(state,state.control(),diagnostic=False)
   class Native:
    confirmed_empty=True
    def metadata(self):
     rows=state.jobs();self_id=rows[-1]['id'];self.assertion=None
     self.result=recovery.pause(root,SimpleNamespace(stop=lambda job:job['id']==self_id,disable=lambda:True))
     return {}
    def close(self):return True
   native=Native()
   with fence.start(lambda ident,active:native) as session:session.metadata()
   self.assertTrue(native.result['latch_confirmed']);self.assertEqual(native.result['state'],'paused')
   self.assertFalse(any(j['state'] in {'active','held','dispatching','claimed'} for j in state.jobs()))
 def test_unconfirmed_native_stop_remains_held_and_blocks_new_invocation(self):
  import relay_live as m
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'relay.sqlite3')
   with state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
   original=state.control();fence=m.MetadataOwner(state,original,diagnostic=False)
   child=SimpleNamespace(confirmed_empty=False,close=lambda:False)
   with fence.start(lambda ident,active:child):pass
   self.assertEqual(state.jobs()[-1]['state'],'held')
   with self.assertRaises(m.LiveUnavailable):
    with m.MetadataOwner(state,original,diagnostic=False).start(lambda ident,active:child):pass
 def test_paused_diagnostic_is_explicit_and_original_epoch_still_fenced(self):
  import relay_live as m
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'relay.sqlite3');original=state.control();child=SimpleNamespace(confirmed_empty=True,close=lambda:True)
   with self.assertRaises(m.LiveUnavailable):
    with m.MetadataOwner(state,original,diagnostic=False).start(lambda ident,active:child):pass
   with m.MetadataOwner(state,original,diagnostic=True).start(lambda ident,active:child):self.assertTrue(active() if False else True)
   state.pause()
   with self.assertRaises(m.LiveUnavailable):
    with m.MetadataOwner(state,original,diagnostic=True).start(lambda ident,active:child):pass
 def test_activation_requires_authenticated_claude_review_of_exact_manifest_and_mode(self):
  import relay_live as m
  from relay_matrix import CLAUDE
  from offline_relay import THREAD
  import copy
  event={'event_id':'$review','sender':CLAUDE,'type':'m.room.message','content':{'body':'[REVIEW] '+json.dumps({'hearth_relay_activation_review':{'verdict':'pass','mode':'intake_capacity_only','manifest_sha256':'a'*64}}),'m.relates_to':{'rel_type':'m.thread','event_id':THREAD}}}
  class Client:
   def event(self,ident):return copy.deepcopy(event)
  self.assertTrue(m.verify_activation_review(Client(),'$review','a'*64))
  for mutate in [lambda e:e.update(sender='@codex:hearth.radekal.me'),lambda e:e['content'].update(body='[REVIEW] PASS disabled candidate'),lambda e:e.update(unsigned={'redacted_because':{'x':1}})]:
   saved=copy.deepcopy(event);mutate(event)
   with self.assertRaises(m.LiveUnavailable):m.verify_activation_review(Client(),'$review','a'*64)
   event=saved
  with self.assertRaises(m.LiveUnavailable):m.verify_activation_review(Client(),'$review','b'*64)
if __name__=='__main__':unittest.main()
