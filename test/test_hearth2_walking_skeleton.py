"""Piece 2 A4/A8/A9 composition controls; synthetic fixture, not live acceptance."""
import importlib.util
from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.dispatch import DispatchRegistry
from hearth2.broker import Broker
from hearth2.store import RecordError


class WalkingSkeletonTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        path=Path(__file__).parent/'fixtures/hearth2_walking_skeleton.py'
        self.assertTrue(path.exists(),'walking composition not implemented')
        spec=importlib.util.spec_from_file_location('walking_fixture',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.registry=DispatchRegistry(self.store,self.controller)

    def claim(self):
        return self.module.poll_once(self.store,self.controller,self.registry,'a'*64)

    def result(self,claim,closeout=True):
        text=json.dumps({'task':claim['task_id'],'attempt':claim['attempt'],'status':'done',
            'produced':'synthetic-plan','changed':'fixture only','unblocked':'none',
            'memory-used':['drawer_fixture'],'checks-run':[{'name':'synthetic','passed':True,'evidence':'fixture'}],
            'next':'independent review'}) if closeout else 'Missing structured closeout'
        return {'provider':'openai','state':'completed','text':text,'stop_reason':None,
                'pause_role':False,'usage_scope':'unknown','usage':{'state':'unknown','units':None,
                'estimated_cost':None,'actual_charge':None}}

    def test_a4_single_poll_claims_once_and_does_not_relaunch_running_task(self):
        first=self.claim();self.assertEqual(first['claim']['task_id'],self.task['id'])
        self.assertIsNone(self.claim())
        self.assertEqual(len(self.store.snapshot()['runs']),1)
        self.assertEqual(first['registration']['phase'],'launching')

    def test_memory_tool_is_declared_read_only_under_never_policy(self):
        tools=self.module.mcp_read_tools()
        self.assertEqual([t['name'] for t in tools],['memory_get'])
        self.assertEqual(tools[0]['annotations'],{'readOnlyHint':True,'destructiveHint':False,'idempotentHint':True})

    def test_a9_broker_read_then_verified_stop_receipt_reaches_review_only(self):
        bound=self.claim();claim=bound['claim'];calls=[]
        broker=Broker(self.store,self.controller,lambda tool,args:calls.append(tool) or
            {'drawer_id':'drawer_fixture','wing':'trial','room':'skeleton','content':'synthetic'})
        token=broker.mint(self.controller,claim,wing='trial',room='skeleton')
        broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        self.module.settle(self.registry,claim,self.result(claim),memory_reads=calls,
            ended_at=self.time.isoformat(),exit_status=0,verified_empty=True,evidence=['outside observer'])
        snap=self.store.snapshot();self.assertEqual(snap['tasks'][0]['state'],'review')
        self.assertEqual(snap['claims'][0]['state'],'closed')
        self.assertEqual(self.registry.pending(),[])
        self.assertIsNone(snap['runs'][0]['actual_charge'])

    def test_a8_missing_closeout_fails_even_with_clean_process_exit(self):
        claim=self.claim()['claim']
        out=self.module.settle(self.registry,claim,self.result(claim,False),memory_reads=['memory_get'],
            ended_at=self.time.isoformat(),exit_status=0,verified_empty=True,evidence=['outside observer'])
        self.assertEqual(out['run']['closeout_validation'],'missing')
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'ready')
        self.assertEqual(len(self.store.snapshot()['incidents']),1)

    def test_no_memory_or_unconfirmed_termination_cannot_promote_success(self):
        claim=self.claim()['claim']
        with self.assertRaises(RecordError):
            self.module.settle(self.registry,claim,self.result(claim),memory_reads=[],
                ended_at=self.time.isoformat(),exit_status=0,verified_empty=True,evidence=['observer'])
        self.module.settle(self.registry,claim,self.result(claim),memory_reads=['memory_get'],
            ended_at=self.time.isoformat(),exit_status=0,verified_empty=False,evidence=[])
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(self.registry.pending()[0]['phase'],'launching')

    def test_incomplete_native_turn_is_held_without_inventing_memory_or_closeout(self):
        claim=self.claim()['claim'];result=self.result(claim)
        result.update(state='unknown',text=None)
        out=self.module.settle(self.registry,claim,result,memory_reads=[],ended_at=self.time.isoformat(),
            exit_status=137,verified_empty=True,evidence=['outside observer'])
        self.assertEqual(out['run']['exit_status'],137)
        self.assertEqual(self.store.snapshot()['tasks'][0]['state'],'held')
        self.assertEqual(self.registry.pending()[0]['phase'],'launching')

    def test_wrong_host_or_nonroot_is_refused_without_assert_authority(self):
        for host,uid in [('other-host',0),('srv2065995',1000)]:
            with self.subTest(host=host,uid=uid),self.assertRaises(RuntimeError):
                self.module.require_trial_host(host,uid)
        self.module.require_trial_host('srv2065995',0)

    def test_cleanup_attempts_revocation_and_server_close_after_docker_timeout(self):
        calls=[]
        class Broker:
            def revoke(self,*args):calls.append('revoke')
        class Server:
            def shutdown(self):calls.append('shutdown');raise RuntimeError('injected shutdown failure')
            def server_close(self):calls.append('close')
        state={'directory':Path(self.tmp.name),'cid':'a'*64,'broker':Broker(),'cap':'fixture',
               'controller':self.controller,'server':Server()}
        receipt={'errors':[]}
        with patch.object(self.module,'command',side_effect=RuntimeError('injected Docker timeout')):
            self.module.cleanup(state,receipt)
        self.assertEqual(calls,['revoke','shutdown','close'])
        self.assertFalse(receipt['verified_empty'])
        self.assertGreaterEqual(len(receipt['errors']),2)

    def test_setup_failure_persists_unknown_receipt_and_held_claim(self):
        directory=Path(self.tmp.name)/'failed-setup'
        def failed(directory,mode,state):
            directory.mkdir();claim=self.claim()['claim']
            state.update(store=self.store,controller=self.controller,registry=self.registry,claim=claim)
            raise RuntimeError('injected setup failure')
        with patch.object(self.module,'_run_case',side_effect=failed):
            receipt=self.module.run_case(directory,'positive')
        self.assertEqual(receipt['task_state'],'held')
        self.assertEqual(receipt['status'],'failed_closed')
        self.assertTrue((directory/'receipt.json').is_file())
        self.assertIsNone(self.store.snapshot()['runs'][0]['exit_status'])

    def test_setup_failure_after_expiry_holds_through_reconciliation(self):
        directory=Path(self.tmp.name)/'expired-setup'
        def failed(directory,mode,state):
            directory.mkdir();claim=self.claim()['claim']
            state.update(store=self.store,controller=self.controller,registry=self.registry,claim=claim)
            self.time+=timedelta(hours=3)
            raise RuntimeError('injected expired setup')
        with patch.object(self.module,'_run_case',side_effect=failed):
            receipt=self.module.run_case(directory,'positive')
        self.assertEqual(receipt['task_state'],'held')
        self.assertEqual(self.registry.pending()[0]['phase'],'launching')


if __name__=='__main__':unittest.main()
