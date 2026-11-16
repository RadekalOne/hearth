import sys,unittest,tempfile,json
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
  record=dict(observed_at=now.isoformat(),workspace='cc',seat='rad',override_credits=0,workspace_credits_spent=0,period=now.strftime('%Y-%m'),usage_percent=10,screenshot_sha256='a'*64)
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
    def client(self,**kw):events.append('client');return Client()
    def active(self):return True
    def memory_read_verified(self):return True
    def stop(self):events.append('stop');return True
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
