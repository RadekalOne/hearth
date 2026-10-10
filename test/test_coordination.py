"""Real SQLite transition contracts; no transport, timers or production data."""
import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

spec = importlib.util.spec_from_file_location('coordination_test', Path(__file__).parents[1] / 'mcp/memory/coordination.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'coordination.sqlite3'
        self.store = c.CoordinationStore(self.path, enabled=True)
        self.store.initialize()
        self.identity = dict(work_kind='task', work_id='task_one', room_id='!tasks:test', thread_id='$root')
        self.party = dict(kind='agent', id='claude', required_surface='interactive')

    def tearDown(self):
        self.temp.cleanup()

    def wait(self, **extra):
        return self.store.set_wait('codex', False, owner='codex', owner_kind='agent',
            expected_generation=0, parties=[self.party], source_event='$request', since='2026-10-10T12:00:00Z',
            **self.identity, **extra)

    def answer(self, kind='final_completion', actor='claude', human=False, generation=1, party_id='claude', **extra):
        return self.store.answer(actor, human, expected_generation=generation, party_id=party_id,
            answer_kind=kind, source_event='$answer', since='2026-10-10T13:00:00Z', summary='Reviewed changes',
            evidence=['commit_fixture'], **self.identity, **extra)

    def test_disabled_reads_and_writes_never_create_database_or_directories(self):
        path = Path(self.temp.name) / 'absent' / 'store.sqlite3'
        disabled = c.CoordinationStore(path)
        disabled.initialize()
        self.assertEqual(disabled.read(**self.identity)['coordination_waiting_on'], [])
        with self.assertRaises(c.CoordinationError) as err:
            disabled.set_wait('codex', False, **self.identity)
        self.assertEqual(err.exception.status, 409)
        self.assertFalse(path.parent.exists())

    def test_migration_is_idempotent_preserves_existing_tables_and_requires_explicit_init(self):
        path = Path(self.temp.name) / 'existing.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE existing(data TEXT)')
            db.execute("INSERT INTO existing VALUES('preserve')")
            db.commit()
        fresh = c.CoordinationStore(path, enabled=True)
        with self.assertRaises(c.CoordinationError):
            fresh.read(**self.identity)
        fresh.initialize(); fresh.initialize()
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT data FROM existing').fetchall(), [('preserve',)])
        self.assertEqual(fresh.read(**self.identity)['generation'], 0)

    def test_task_relay_and_thread_plan_identity_do_not_collide_and_persist(self):
        for kind in ['task', 'relay', 'thread_plan']:
            identity = {**self.identity, 'work_kind': kind}
            self.store.set_wait('codex', False, owner='codex', owner_kind='agent', expected_generation=0,
                parties=[self.party], source_event='$request', since='2026-10-10T12:00:00Z', **identity)
        reopened = c.CoordinationStore(self.path, enabled=True); reopened.initialize()
        for kind in ['task', 'relay', 'thread_plan']:
            state = reopened.read(**{**self.identity, 'work_kind': kind})
            self.assertEqual(state['generation'], 1)
            self.assertEqual(state['coordination_waiting_on'][0]['since'], '2026-10-10T12:00:00+00:00')
            self.assertEqual(state['coordination_waiting_on'][0]['required_surface'], 'interactive')

    def test_two_parties_one_answer_does_not_erase_other_obligation(self):
        self.store.set_wait('codex', False, owner='codex', owner_kind='agent', expected_generation=0,
            parties=[self.party, {**self.party, 'id':'mavis', 'required_surface':'background',
                'expected_deadline':'2026-10-10T16:00:00Z', 'acknowledged_delay_until':'2026-10-11T12:00:00Z'}],
            source_event='$request', since='2026-10-10T12:00:00Z', **self.identity)
        result = self.answer()
        self.assertEqual([(p['id'],p['state']) for p in result['coordination_waiting_on']], [('mavis','pending')])
        self.assertEqual(result['coordination_waiting_on'][0]['acknowledged_delay_until'], '2026-10-11T12:00:00+00:00')
        self.assertFalse(result['grants_authority'])

    def test_ack_progress_reaction_and_unrelated_leave_generation_and_pending_state_unchanged(self):
        self.wait()
        for kind in ['ack', 'progress', 'reaction', 'unrelated']:
            result = self.answer(kind)
            self.assertFalse(result['changed'])
            self.assertEqual(result['generation'], 1)
            self.assertEqual(result['coordination_waiting_on'][0]['id'], 'claude')

    def test_reviewer_changes_return_ball_to_executor_and_pass_waits_on_human(self):
        self.wait()
        changes = self.answer('change_list')
        self.assertEqual([(p['kind'],p['id']) for p in changes['coordination_waiting_on']], [('agent','codex')])
        passed = self.store.answer('codex', False, expected_generation=changes['generation'], party_id='codex',
            answer_kind='pass_needing_human', approval_party='rad', source_event='$pass',
            since='2026-10-10T14:00:00Z', summary='Ready for deployment review', evidence=['commit_fixture'], **self.identity)
        self.assertEqual([(p['kind'],p['id']) for p in passed['coordination_waiting_on']], [('human','rad')])
        self.assertFalse(passed['grants_authority'])
        with self.assertRaises(c.CoordinationError):
            self.answer('approved', actor='codex', party_id='rad')
        approved = self.answer('approved', actor='rad', human=True, party_id='rad', generation=passed['generation'])
        self.assertEqual(approved['coordination_waiting_on'], [])
        self.assertFalse(approved['grants_authority'])

    def test_cross_agent_write_and_forged_party_are_rejected(self):
        with self.assertRaises(c.CoordinationError) as err:
            self.store.set_wait('mavis', False, owner='codex', owner_kind='agent', expected_generation=0,
                parties=[self.party], source_event='$request', since='2026-10-10T12:00:00Z', **self.identity)
        self.assertEqual(err.exception.status, 403)
        self.wait()
        with self.assertRaises(c.CoordinationError):
            self.answer(actor='mavis')
        with self.assertRaises(c.CoordinationError):
            self.answer(actor='claude', party_id='someone_else')

    def test_stale_generation_and_competing_writers_are_fenced(self):
        self.wait()
        def advance(_):
            try:
                return self.store.set_wait('codex', False, owner='codex', owner_kind='agent',
                    expected_generation=1, parties=[self.party], source_event='$next',
                    since='2026-10-10T14:00:00Z', **self.identity)['generation']
            except c.CoordinationError as err:
                return err.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(advance, range(2))), [2,409])
        with self.assertRaises(c.CoordinationError) as err:
            self.answer(generation=1)
        self.assertEqual(err.exception.status, 409)
        self.assertEqual(self.store.read(**self.identity)['generation'], 2)

    def test_answer_replay_is_idempotent_and_cancellation_keeps_history(self):
        self.wait()
        self.answer()
        self.assertFalse(self.answer()['changed'])
        self.store.set_wait('codex', False, owner='codex', owner_kind='agent', expected_generation=1,
            parties=[self.party], source_event='$next', since='2026-10-10T14:00:00Z', **self.identity)
        cancelled = self.answer('cancel', actor='codex', generation=2, party_id='')
        self.assertEqual(cancelled['coordination_waiting_on'], [])
        history = self.store.read(**self.identity, history=True)['history']
        self.assertEqual([(p['generation'],p['state']) for p in history], [(1,'resolved'),(2,'cancelled')])

    def test_handoff_is_scoped_to_answerer_and_requires_next_party_and_evidence(self):
        self.wait()
        with self.assertRaises(c.CoordinationError):
            self.answer('handoff')
        result = self.answer('handoff', next_parties=[{**self.party,'id':'mavis'}])
        self.assertEqual(result['coordination_waiting_on'][0]['id'], 'mavis')

    def test_invalid_inputs_roll_back_without_partial_rows(self):
        for invalid in [{**self.party,'required_surface':'desktop'}, {**self.party,'kind':'robot'},
                        {**self.party,'expected_deadline':'not-a-time'}]:
            with self.assertRaises(c.CoordinationError):
                self.store.set_wait('codex', False, owner='codex', owner_kind='agent', expected_generation=0,
                    parties=[self.party,invalid], source_event='$request', since='2026-10-10T12:00:00Z', **self.identity)
            self.assertEqual(self.store.read(**self.identity)['generation'], 0)

    def test_handoff_advances_generation_so_old_party_cannot_answer_a_new_obligation(self):
        self.wait()
        changes=self.answer('change_list')
        self.assertEqual(changes['generation'],2)
        handoff=self.store.answer('codex',False,expected_generation=2,party_id='codex',answer_kind='handoff',
            next_parties=[self.party],source_event='$handoff',since='2026-10-10T14:00:00Z',
            summary='Fixed, please review again',evidence=['commit_two'],**self.identity)
        self.assertEqual(handoff['generation'],3)
        with self.assertRaises(c.CoordinationError) as err:
            self.store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='final_completion',
                source_event='$late',since='2026-10-10T15:00:00Z',summary='Old review',evidence=['old_commit'],**self.identity)
        self.assertEqual(err.exception.status,409)
        replay=self.answer('change_list')
        self.assertFalse(replay['changed'])
        self.assertEqual(replay['coordination_waiting_on'][0]['id'],'claude')

    def test_human_cannot_answer_for_a_different_human(self):
        self.store.set_wait('codex',False,owner='codex',owner_kind='agent',expected_generation=0,
            parties=[{'kind':'human','id':'rad','required_surface':'interactive'}],
            source_event='$request',since='2026-10-10T12:00:00Z',**self.identity)
        with self.assertRaises(c.CoordinationError) as err:
            self.answer('approved',actor='other_human',human=True,party_id='rad')
        self.assertEqual(err.exception.status,403)


if __name__ == '__main__':
    unittest.main()
