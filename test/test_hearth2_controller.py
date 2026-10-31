"""Account observation to atomic dispatch, using real record transactions."""
import importlib
from datetime import timedelta
import unittest
from unittest.mock import patch
import test_hearth2_claims as fixtures
from hearth2.store import RecordError


class ControllerTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.controller'),
                             'preflight controller is not implemented')
        self.kind=importlib.import_module('hearth2.controller').PreflightController
        self.observations=[]
        self.response={
            'observed_at':self.time.isoformat(),
            'account':{'account':{'type':'chatgpt'},'requiresOpenaiAuth':True},
            'limits':{'rateLimits':{'credits':{'hasCredits':False,'unlimited':False},
                      'primary':{'usedPercent':12},'secondary':None}},
            'route':{'configured_provider':'openai','api_key_present':False,
                     'unexpected_environment':False,'other_credentials_present':False,
                     'native_login_present':True}}
        def observe(role):
            self.observations.append(role)
            return self.response
        self.observe=observe
        self.runner=self.kind(self.store,self.controller,self.observe,policy_sha256='a'*64)

    def prepare(self, **changes):
        fields=dict(expected_revision=1,request_id='controller-one');fields.update(changes)
        return self.runner.prepare(self.task['id'],**fields)

    def test_success_observes_first_then_claims_and_reserves_without_launching(self):
        result=self.prepare()
        self.assertEqual(result['state'],'prepared')
        self.assertEqual(result['account_check']['provider'],'openai')
        self.assertEqual(result['registration']['phase'],'reserved')
        self.assertEqual(len(self.observations),1)
        self.assertEqual(self.observations[0]['revision'],1)
        self.assertEqual(len(self.store.snapshot()['runs']),1)

    def test_rejected_account_keeps_ready_work_and_zero_attempts(self):
        self.response['route']['api_key_present']=True
        result=self.prepare()
        self.assertEqual(result['state'],'blocked')
        snapshot=self.store.snapshot()
        self.assertEqual(snapshot['tasks'][0]['state'],'ready')
        self.assertEqual(snapshot['tasks'][0]['attempts'],0)
        self.assertEqual(snapshot['runs'],[])
        self.assertEqual(self.runner.registry.pending(),[])
        failures=self.store.control_snapshot()['failures']
        self.assertEqual(len(failures),1)
        self.assertEqual(failures[0]['kind'],'dispatch_blocked')

    def test_repeated_blocked_observations_use_one_incident_and_success_recovers_it(self):
        self.response['limits']['rateLimits']['primary']['usedPercent']=100
        self.prepare();self.prepare(request_id='controller-two')
        self.assertEqual(len(self.store.control_snapshot()['failures']),1)
        self.response['limits']['rateLimits']['primary']['usedPercent']=12
        result=self.prepare(request_id='controller-three')
        self.assertEqual(result['state'],'prepared')
        self.assertEqual(self.store.control_snapshot()['failures'][0]['state'],'recovered')
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)

    def test_role_change_during_native_check_is_fenced_without_consuming_an_attempt(self):
        def changed(role):
            self.store.set_role(self.rad,'codex',{**self.role,'model':'replacement'})
            return self.response
        self.runner=self.kind(self.store,self.controller,changed,policy_sha256='a'*64)
        with self.assertRaises(RecordError):self.prepare()
        self.assertEqual(self.store.snapshot()['runs'],[])
        self.assertEqual(self.runner.registry.pending(),[])

    def test_stale_task_is_refused_before_account_probe(self):
        with self.assertRaises(RecordError):self.prepare(expected_revision=99)
        self.assertEqual(self.observations,[])

    def test_observer_errors_are_recorded_without_copying_exception_or_credentials(self):
        def broken(role):raise RuntimeError('private-upstream-secret')
        self.runner=self.kind(self.store,self.controller,broken,policy_sha256='a'*64)
        result=self.prepare()
        self.assertEqual(result['state'],'blocked')
        self.assertNotIn('private-upstream-secret',str(result)+str(self.store.snapshot()))
        self.assertEqual(self.store.snapshot()['runs'],[])

    def test_expired_account_snapshot_is_not_reused_for_launch(self):
        self.time+=timedelta(seconds=61)
        result=self.prepare()
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(self.store.snapshot()['runs'],[])

    def test_retry_after_post_claim_failure_returns_same_reservation_once(self):
        with patch.object(self.runner, '_failure', side_effect=RecordError('injected CAS conflict')):
            with self.assertRaises(RecordError):self.prepare()
        reserved=self.runner.registry.pending()[0]
        result=self.prepare()
        self.assertEqual(result['state'],'prepared')
        self.assertTrue(result['replayed'])
        self.assertIsNone(result['account_check'])
        self.assertEqual(result['registration'],reserved)
        self.assertEqual(len(self.observations),1)
        self.assertEqual(len(self.store.snapshot()['runs']),1)
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)

    def test_replay_checks_original_task_revision_owner_policy_and_current_role(self):
        result=self.prepare()
        before=self.store.snapshot()
        for revision in [2, True, '1']:
            with self.subTest(revision=revision), self.assertRaises(RecordError):
                self.prepare(expected_revision=revision)
        other=self.store.create_task(self.controller,{**self.payload,'action_id':'parallel'})
        with self.assertRaises(RecordError):
            self.runner.prepare(other['id'],expected_revision=1,request_id='controller-one')
        other_owner=self.kind(self.store,fixtures.Principal('other-controller','controller'),
                              self.observe,policy_sha256='a'*64)
        with self.assertRaises(RecordError):
            other_owner.prepare(self.task['id'],expected_revision=1,request_id='controller-one')
        changed=self.kind(self.store,self.controller,self.observe,policy_sha256='b'*64)
        with self.assertRaises(RecordError):
            changed.prepare(self.task['id'],expected_revision=1,request_id='controller-one')
        self.store.set_role(self.rad,'codex',{**self.role,'model':'replacement'})
        with self.assertRaises(RecordError):self.prepare()
        self.assertEqual(len(self.observations),1)
        self.assertEqual(len(self.store.snapshot()['runs']),1)

    def test_consumed_replay_never_issues_another_launch_permission(self):
        result=self.prepare();self.runner.registry.consume(result['claim'])
        replay=self.prepare()
        self.assertEqual(replay['state'],'already_consumed')
        self.assertEqual(replay['registration']['phase'],'launching')
        with self.assertRaises(RecordError):self.runner.registry.consume(replay['claim'])
        self.assertEqual(self.store.snapshot()['tasks'][0]['attempts'],1)

    def test_expired_replay_never_reobserves_or_reopens_a_reservation(self):
        self.prepare();self.time+=timedelta(hours=1)
        with self.assertRaises(RecordError):self.prepare()
        self.assertEqual(len(self.observations),1)
        self.assertEqual(self.runner.registry.pending()[0]['phase'],'reserved')

    def test_unregistered_claim_cannot_skip_native_account_preflight(self):
        self.store.claim(self.controller,self.task['id'],expected_revision=1,
                         request_id='controller-one')
        with self.assertRaises(RecordError):self.prepare()
        self.assertEqual(self.observations,[])
        self.assertEqual(self.runner.registry.pending(),[])


if __name__ == '__main__':
    unittest.main()
