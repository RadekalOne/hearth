import sys,unittest,tempfile,json,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).parents[1]/'ops/hearth2'))
sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
class ExecutionTests(unittest.TestCase):
 def test_financial_manual_zero_fresh_subject_bound(self):
  from relay_financial import check
  now=datetime(2026,11,16,20,tzinfo=timezone.utc)
  record=dict(observed_at=now.isoformat(),workspace='cc',seat='rad',override_credits=0,workspace_credits_spent=0,period='2026-11',usage_percent=10,screenshot_sha256='a'*64)
  self.assertEqual(check(record,now,workspace='cc',seat='rad',supervised=True)['usage_percent'],10)
  for field,value in [('override_credits',True),('override_credits',1),('workspace_credits_spent',1),('workspace_credits_spent',float('nan')),('seat','other'),('observed_at',(now-timedelta(minutes=16)).isoformat())]:
   with self.subTest(field=field,value=value),self.assertRaises(ValueError):check({**record,field:value},now,workspace='cc',seat='rad',supervised=True)
  with self.assertRaises(ValueError):check(record,now,workspace='cc',seat='rad',supervised=False)
 def test_journal_exclusive_fsynced_per_run(self):
  from relay_entitlement import Journal
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'one.jsonl';j=Journal(p);j.write(kind='thread_dispatch_intent',send_state='possibly_sent');j.close()
   self.assertEqual(json.loads(p.read_text())['send_state'],'possibly_sent')
   with self.assertRaises(FileExistsError):Journal(p)
 def test_candidate_command_is_fixed_isolated_and_pinned(self):
  from relay_candidate_tests import command
  c=command('sha256:'+'a'*64,Path('.').resolve(),'hearth-entitlement-test')
  for x in ['--network=none','--read-only','--cap-drop=ALL','--user=1000:1000']:self.assertIn(x,c)
  with self.assertRaises(ValueError):command('latest',Path('.'),'x')
 def test_disabled_driver_never_constructs_session(self):
  from relay_entitlement import execute
  with self.assertRaises(ValueError):execute({},enabled=False)
 def test_outside_supervisor_kills_hanging_group(self):
  from relay_candidate_tests import supervised_process
  result=supervised_process([sys.executable,'-c','import time;time.sleep(20)'],timeout=.2)
  self.assertEqual(result['state'],'timeout');self.assertTrue(result['empty'])
if __name__=='__main__':unittest.main()

class ComposedTests(unittest.TestCase):
 def test_composed_order_and_post_send_failure_cleanup(self):
  from relay_entitlement import execute
  from unittest.mock import patch
  from types import SimpleNamespace
  now=datetime.now(timezone.utc)
  record=dict(observed_at=(now-timedelta(seconds=2)).isoformat(),workspace='cc',seat='rad',override_credits=0,workspace_credits_spent=0,period=now.strftime('%Y-%m'),usage_percent=10,screenshot_sha256='a'*64)
  package=dict(approval_event='$approval',disabled=True,workspace='cc',seat='rad',run_id='test',binary_path='/fixture',binary_sha256='b'*64,catalog_sha256='c'*64,prompt='Synthetic challenge')
  for fail in (False,True):
   events=[]
   class Client:
    def turn_start(self,request,**kw):
     events.append('turn');self.assertion=kw['before_send']();kw['record_event']({'kind':'turn_ack'})
     if fail:raise RuntimeError('fixture transport failed')
     return SimpleNamespace(turn_id='turn-1',native_result={'state':'completed','usage':{'state':'unknown'}})
   class Workload:
    outside_deadline_seconds=90
    monotonic=staticmethod(time.monotonic);armed_at=monotonic()
    def client(self,**kw):events.append('client');return Client()
    def active(self):return True
    def memory_read_verified(self):return True
    def stop(self):events.append('stop');record.update(observed_at=datetime.now(timezone.utc).isoformat(),screenshot_sha256='d'*64);return True
   class Launcher:
    def __init__(self,*a,**kw):self.fence=kw['pre_thread_fence']
    def launch_thread(self,request):
     self.fence();events.append('thread');return {'thread':{'id':'thread-1'},'approvalPolicy':'never'}
   with tempfile.TemporaryDirectory() as td,patch('hearth2.native_thread_launcher.CodexThreadLauncher',Launcher):
    p=Path(td)/'run.jsonl'
    if fail:
     with self.assertRaises(RuntimeError):execute(package,enabled=True,approval='$approval',read_financial=lambda:record,workload=Workload(),journal_path=p)
    else:
     result=execute(package,enabled=True,approval='$approval',read_financial=lambda:record,workload=Workload(),journal_path=p)
     self.assertIn('10%',result['status'])
    rows=[json.loads(x) for x in p.read_text().splitlines()]
    self.assertLess([x['kind'] for x in rows].index('thread_dispatch_intent'),[x['kind'] for x in rows].index('thread_started'))
    self.assertEqual(events,['client','thread','turn','stop'])
    self.assertTrue(rows[-1]['confirmed_empty'])
    if fail:self.assertEqual(rows[-1]['send_state'],'turn_may_be_sent')

class ReviewFixTests(unittest.TestCase):
 def test_post_turn_evidence_must_be_after_send_and_new_screenshot(self):
  from relay_financial import check_after
  send=datetime(2026,11,17,13,tzinfo=timezone.utc)
  before={'observed_at':send.isoformat(),'period':'2026-11','screenshot_sha256':'a'*64}
  for after in [before,{**before,'observed_at':(send+timedelta(seconds=1)).isoformat()}]:
   with self.assertRaises(ValueError):check_after(before,after,send)
  after={**before,'observed_at':(send+timedelta(seconds=1)).isoformat(),'screenshot_sha256':'b'*64}
  check_after(before,after,send)
 def test_candidate_remove_attempted_even_if_kill_hangs(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  import subprocess
  import relay_candidate_tests as m
  calls=[]
  def run(argv,**kw):
   calls.append(argv[1])
   if argv[1]=='kill':raise subprocess.TimeoutExpired(argv,5)
   return SimpleNamespace(returncode=0)
  with tempfile.TemporaryDirectory() as td,patch.object(m,'supervised_process',return_value={'state':'exited','exit_code':0,'empty':True}),patch.object(m.subprocess,'run',run):
   result=m.run('sha256:'+'a'*64,Path(td),'hearth-entitlement-fixture')
  self.assertEqual(calls,['kill','rm']);self.assertTrue(result['container_removed'])
 def test_expired_shared_workload_clock_refuses_before_client(self):
  from relay_entitlement import execute
  class W:
   outside_deadline_seconds=90;armed_at=0
   monotonic=staticmethod(lambda:71)
   def stop(self):return True
   def active(self):return True
   def client(self,**kw):raise AssertionError('expired workload opened client')
  with tempfile.TemporaryDirectory() as td,self.assertRaisesRegex(ValueError,'workload_deadline'):
   execute({'approval_event':'a','disabled':True},enabled=True,approval='a',read_financial=lambda:None,
       workload=W(),journal_path=Path(td)/'j')
 def test_missing_clock_origin_never_grants_fresh_budget(self):
  from relay_entitlement import execute
  calls=[]
  class W:
   outside_deadline_seconds=90
   def active(self):calls.append('active');return True
   def client(self,**kw):calls.append('client');raise AssertionError('client opened')
   def stop(self):calls.append('stop');return True
  with tempfile.TemporaryDirectory() as td:
   journal=Path(td)/'journal'
   with self.assertRaisesRegex(ValueError,'workload_clock_origin_required'):
    execute({'approval_event':'a','disabled':True},enabled=True,approval='a',
       workload=W(),read_financial=lambda:calls.append('financial'),journal_path=journal)
   self.assertEqual(calls,[]);self.assertFalse(journal.exists())
 def test_driver_uses_the_workloads_own_clock_domain(self):
  from relay_entitlement import execute
  from unittest.mock import patch
  class W:
   outside_deadline_seconds=90;armed_at=0
   monotonic=staticmethod(lambda:1)
   def active(self):return True
   def stop(self):return True
  def financial():raise RuntimeError('valid_origin_reached_preflight')
  with tempfile.TemporaryDirectory() as td,patch('relay_entitlement.time.monotonic',side_effect=AssertionError('different clock used')):
   with self.assertRaisesRegex(RuntimeError,'valid_origin_reached_preflight'):
    execute({'approval_event':'a','disabled':True},enabled=True,approval='a',read_financial=financial,
        workload=W(),journal_path=Path(td)/'journal')
