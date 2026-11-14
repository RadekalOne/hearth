"""Claude review regressions, entirely credential-free."""
import json,sys,tempfile,unittest,hashlib,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))
from offline_relay import ROOM,THREAD,Dispatcher
from offline_relay_state import State

class ReviewRevisionTests(unittest.TestCase):
 def event(self,body):return {'event_id':'$review','sender':'@claude:hearth.radekal.me','type':'m.room.message','content':{'body':body,'m.relates_to':{'rel_type':'m.thread','event_id':THREAD}}}
 def test_refusing_review_quoting_activation_json_is_refused(self):
  import relay_live as live
  packet=json.dumps({'hearth_relay_activation_review':{'verdict':'pass','mode':'intake_capacity_only','manifest_sha256':'a'*64}})
  for body in ['[REVIEW] HOLD. Do not activate.\n```json\n'+packet+'\n```','[REVIEW] ```json\n'+packet+'\n```\nFAIL','[REVIEW] '+packet+' trailing prose']:
   class Client:
    def event(inner,ident):return self.event(body)
   with self.assertRaises(live.LiveUnavailable):live.verify_activation_review(Client(),'$review','a'*64)
 def test_entire_activation_packet_plain_or_single_fence_passes(self):
  import relay_live as live
  packet=json.dumps({'hearth_relay_activation_review':{'verdict':'pass','mode':'intake_capacity_only','manifest_sha256':'a'*64}})
  for body in ['[REVIEW] '+packet,'[REVIEW]\n```json\n'+packet+'\n```']:
   class Client:
    def event(inner,ident):return self.event(body)
   self.assertTrue(live.verify_activation_review(Client(),'$review','a'*64))
 def test_arbitrary_or_wrong_work_review_does_not_qualify(self):
  import relay_matrix as m
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'s.db');work={'work_id':'x','generation':1,'base_commit':'a'*40,'paths':['test/test_hearth2_x.py'],'aliases':[],'scope':'hearth2-offline','review_event':'$review'}
   approval=self.event('[APPROVED] '+json.dumps({'hearth_relay_work':work}));approval.update(sender=m.RAD,event_id='$approval')
   review_packet={'hearth_relay_work_review':{'verdict':'pass','work':{k:v for k,v in work.items() if k!='review_event'}}}
   for body in ['[REVIEW] HOLD','[REVIEW] '+json.dumps({'hearth_relay_work_review':{'verdict':'fail','work':work}}),'[REVIEW] '+json.dumps({'hearth_relay_work_review':{'verdict':'pass','work':{**work,'work_id':'other'}}})]:
    class Client:
     def event(inner,ident):return self.event(body)
    with self.assertRaises(ValueError):m.MatrixIntake(state,Client()).parse(approval)
   class Good:
    def event(inner,ident):return self.event('[REVIEW] '+json.dumps(review_packet))
   self.assertEqual(m.MatrixIntake(state,Good()).parse(approval)[0],work)
 def test_intake_failure_and_pending_posts_never_write_to_room(self):
  from datetime import datetime,timezone
  with tempfile.TemporaryDirectory() as td:
   state=State(Path(td)/'s.db')
   with state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
   state.notice('old','old pending post');sent=[]
   class Ports:
    allow_posting=False
    def host_ok(self):return True
    def poll(self):raise RuntimeError('gap')
    def post(self,*args):sent.append(args)
   result=Dispatcher(state,Ports(),clock=lambda:datetime(2026,11,13,20,tzinfo=timezone.utc)).check()
   self.assertEqual(sent,[]);self.assertEqual(len(state.outbox()),1);self.assertEqual(state.outbox()[0]['state'],'pending')
   self.assertEqual(result['state'],'intake_unavailable_or_gap')
 def test_generator_reproduces_exact_bytes_without_reading_credentials(self):
  import relay_install as install
  source=Path(__file__).parents[1]/'ops/hearth2'
  config,manifest=install.build_artifacts(source,source,'C:/Users/rslabinski/AppData/Local/Hearth/OfflineRelay','21HM000SUS')
  self.assertEqual((config,manifest),install.build_artifacts(source,source,'C:/Users/rslabinski/AppData/Local/Hearth/OfflineRelay','21HM000SUS'))
  c=json.loads(config);m=json.loads(manifest)
  self.assertEqual(m['live_config_sha256'],hashlib.sha256(config).hexdigest())
  self.assertEqual(m['live_coordination'],'authenticated_fixed_thread');self.assertEqual(c['mode'],'intake_capacity_only')
  self.assertIn('activate-offline-relay.ps1',m['source_hashes']);self.assertIn('relay_install.py',m['source_hashes'])
  self.assertEqual(set(c),{'version','mode','host','repo','matrix_env','auth','binary','binary_sha256','seed_event'})
 def test_generator_refuses_links_and_unknown_config_changes(self):
  import relay_install as install
  source=Path(__file__).parents[1]/'ops/hearth2'
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'live-config.json').write_text('{"secret":"do-not-copy"}')
   with self.assertRaises(install.InstallRefused):install.write_artifacts(root,'21HM000SUS')
   self.assertEqual((root/'live-config.json').read_text(),'{"secret":"do-not-copy"}')
if __name__=='__main__':unittest.main()
