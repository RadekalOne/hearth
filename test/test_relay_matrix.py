"""Concrete intake contract; fake server events are explicit test data."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))
from offline_relay_state import State
from offline_relay import ROOM,THREAD

class MatrixTests(unittest.TestCase):
 def setUp(self):
  import relay_matrix as m
  self.m=m;self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.state=State(Path(self.tmp.name)/'state.db')
  self.work={'work_id':'work','aliases':['relay-alias'],'generation':1,'review_event':'$review','base_commit':'a'*40,'paths':['mcp/memory/hearth2/broker.py'],'scope':'hearth2-offline'}
  def event(i,sender,body):return {'event_id':i,'sender':sender,'type':'m.room.message','content':{'body':body,'m.relates_to':{'rel_type':'m.thread','event_id':THREAD}}}
  self.old=event('$old',m.ACTOR,'[STATUS] seed');self.review=event('$review',m.CLAUDE,'[REVIEW] scoped work')
  self.approval=event('$approval',m.RAD,'[APPROVED]\n'+json.dumps({'hearth_relay_work':self.work}))
  owner=self
  class Client:
   def whoami(self):return {'user_id':m.ACTOR}
   def event(self,i):return copy.deepcopy({'$old':owner.old,'$review':owner.review,'$approval':owner.approval}[i])
   def page(self,token=None):return {'chunk':[owner.approval,owner.old],'end':'end'}
  self.client=Client();self.intake=m.MatrixIntake(self.state,self.client)
 def test_missing_cursor_refuses_without_replay(self):
  with self.assertRaises(self.m.IntakeUnavailable):self.intake.poll()
 def test_authenticated_approval_is_staged_durably_and_rechecked(self):
  self.intake.bootstrap('$old');self.assertEqual(self.intake.poll(),[self.work]);self.assertEqual(self.intake.verify(self.work).sender,self.m.RAD)
  self.assertEqual(self.m.MatrixIntake(self.state,self.client).poll(),[self.work])
 def test_cursor_gap_never_advances(self):
  self.intake.bootstrap('$old');self.client.page=lambda token=None:{'chunk':[self.approval],'end':None}
  with self.assertRaises(self.m.IntakeUnavailable):self.intake.poll()
  with self.state.connect() as db:self.assertEqual(db.execute('SELECT event_id FROM relay_cursor').fetchone()[0],'$old')
 def test_wrong_sender_thread_or_redaction_cannot_authorize(self):
  self.intake.bootstrap('$old')
  for mutate in [lambda e:e.update(sender=self.m.CLAUDE),lambda e:e['content']['m.relates_to'].update(event_id='$other'),lambda e:e.update(unsigned={'redacted_because':{'x':1}})]:

   with self.state.tx() as db:db.execute('UPDATE relay_cursor SET event_id=?',('$old',))
   saved=copy.deepcopy(self.approval);mutate(self.approval);self.assertEqual(self.intake.poll(),[]);self.approval=saved
 def test_transport_failure_before_stage_keeps_cursor(self):
  self.intake.bootstrap('$old');self.client.event=lambda i:(_ for _ in ()).throw(self.m.IntakeUnavailable('offline'))
  with self.assertRaises(self.m.IntakeUnavailable):self.intake.poll()
  with self.state.connect() as db:self.assertEqual(db.execute('SELECT event_id FROM relay_cursor').fetchone()[0],'$old')
 def test_live_constructor_refuses_other_origin_and_header_injection(self):
  for token,origin in [('secret','https://evil.test'),('secret\nX: bad',self.m.ORIGIN)]:
   with self.assertRaises(ValueError):self.m.MatrixClient(token,origin=origin)
 def test_claimed_generation_does_not_starve_new_pending_work(self):
  self.intake.bootstrap('$old');self.intake.poll()
  with self.state.tx() as db:db.execute('UPDATE control SET paused=0,enabled=1')
  self.state.claim(self.m.admit(self.work,self.intake.verify(self.work)))
  self.assertEqual(self.intake.poll(),[])
 def test_wrong_room_event_is_refused_even_when_thread_matches(self):
  self.approval['room_id']='!wrong'
  self.intake.bootstrap('$old');self.assertEqual(self.intake.poll(),[])
 def test_conflicting_generation_rolls_back_staging_and_cursor(self):
  self.intake.bootstrap('$old');self.intake.poll()
  with self.state.tx() as db:db.execute('UPDATE relay_cursor SET event_id=?',('$old',))
  self.work['paths']=['test/test_hearth2_other.py'];self.approval['content']['body']='[APPROVED] '+json.dumps({'hearth_relay_work':self.work})
  with self.assertRaises(self.m.IntakeUnavailable):self.intake.poll()
  with self.state.connect() as db:self.assertEqual(db.execute('SELECT event_id FROM relay_cursor').fetchone()[0],'$old')
 def test_duplicate_json_keys_never_authorize(self):
  self.intake.bootstrap('$old');self.approval['content']['body']='[APPROVED] {"hearth_relay_work":{},"hearth_relay_work":{}}'
  self.assertEqual(self.intake.poll(),[])

class MatrixHTTPTests(unittest.TestCase):
 def test_real_http_transport_fixture_refuses_redirects_and_wrong_identity(self):
  import relay_matrix as m,threading
  from http.server import HTTPServer,BaseHTTPRequestHandler
  class Handler(BaseHTTPRequestHandler):
   redirect=False;actor=m.ACTOR
   def log_message(self,*a):pass
   def do_GET(self):
    if self.redirect:self.send_response(302);self.send_header('Location','http://127.0.0.1:1/secret');self.end_headers();return
    self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'user_id':self.actor}).encode())
  server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   client=m.MatrixClient('synthetic-token',origin='http://127.0.0.1:'+str(server.server_port),fixture=True)
   self.assertTrue(client.whoami()['authenticated']);Handler.actor='@wrong:example'
   with self.assertRaises(m.IntakeUnavailable):client.whoami()
   Handler.redirect=True
   with self.assertRaises(m.IntakeUnavailable):client.whoami()
  finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
