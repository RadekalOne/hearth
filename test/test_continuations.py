import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test.test_coordination import c


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'coordination.sqlite3'
        self.store=c.CoordinationStore(self.path,enabled=True);self.store.initialize()
        self.identity=dict(work_kind='thread_plan',work_id='plan',room_id='!tasks:test',thread_id='$root')
    def wait(self,**extra):
        return self.store.set_wait('codex',False,owner='codex',parties=[{'kind':'agent','id':'claude','required_surface':'interactive','expected_deadline':'2026-10-10T14:00:00Z'}],
            source_event='$request',since='2026-10-10T12:00:00Z',**self.identity,**extra)
    def answer(self,**extra):
        return self.store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='final_completion',source_event='$reply',since='2026-10-10T13:00:00Z',summary='Reviewed',evidence=['commit'],**self.identity,**extra)
    def test_wait_is_not_ready_reply_is_once_and_duplicate_safe(self):
        self.wait();self.assertEqual(self.store.deliveries('codex'),[])
        self.answer();self.answer()
        jobs=self.store.deliveries('codex');self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['last_read_event'],'$request')
        self.assertEqual(jobs[0]['trigger_event'],'$reply')
        self.assertFalse(jobs[0]['grants_authority'])
    def test_deadline_and_reply_race_one_delivery_restart_before_ack(self):
        self.wait()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda action:action(),[self.answer,lambda:self.store.promote_due('2026-10-10T14:01:00Z')]))
        first=self.store.deliveries('codex')
        restart=c.CoordinationStore(self.path,enabled=True);restart.initialize()
        self.assertEqual(first,restart.deliveries('codex'))
        self.assertEqual(len(first),1)
        self.store.mark_delivered(first[0]['delivery_id'])
        self.assertEqual(restart.deliveries('codex'),[])
    def test_ack_no_promotion_cancel_invalidates_and_origin_does_not_recur(self):
        self.wait()
        self.store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='ack',source_event='',since='',**self.identity)
        self.assertEqual(self.store.deliveries('codex'),[])
        self.store.promote_due('2026-10-10T14:01:00Z')
        self.store.answer('codex',False,expected_generation=1,party_id='',answer_kind='cancel',source_event='$cancel',since='2026-10-10T15:00:00Z',summary='Cancelled',evidence=['cancel'],**self.identity)
        self.assertEqual(self.store.deliveries('codex'),[])
        self.wait(expected_generation=1,continuation_origin=True)
        self.store.promote_due('2026-10-10T16:00:00Z')
        self.assertEqual(self.store.deliveries('codex'),[])
    def test_new_generation_fences_old_reply_and_old_ready_delivery(self):
        self.wait();self.store.promote_due('2026-10-10T14:01:00Z')
        self.wait(expected_generation=1)
        with self.assertRaises(c.CoordinationError):self.answer()
        self.assertEqual(self.store.deliveries('codex'),[])
    def test_disabled_no_database(self):
        disabled=c.CoordinationStore(Path(self.temp.name)/'absent'/'off.sqlite3')
        disabled.promote_due('2026-10-10T14:00:00Z')
        self.assertEqual(disabled.deliveries('codex'),[])
        self.assertEqual(disabled.failed_deliveries(),[])
        self.assertFalse(Path(disabled.path).parent.exists())

    def test_continuation_origin_never_recurs_after_handoff(self):
        self.wait(continuation_origin=True)
        self.store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='handoff',source_event='$handoff',
            since='2026-10-10T13:00:00Z',summary='Next review',evidence=['commit'],next_parties=[{'kind':'agent','id':'claude','required_surface':'interactive','expected_deadline':'2026-10-10T14:00:00Z'}],**self.identity)
        self.store.promote_due('2026-10-10T15:00:00Z')
        self.assertEqual(self.store.deliveries('codex'),[])

    def test_deadline_delivered_then_change_list_remains_resumable_same_relay(self):
        self.wait();external={}
        self.store.drain('codex',lambda job:external.update({job['delivery_id']:job}),'2026-10-10T14:01:00Z')
        key=next(iter(external))
        self.store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='change_list',source_event='$changes',
            since='2026-10-10T15:00:00Z',summary='Fix validation',evidence=['commit'],**self.identity)
        self.assertTrue(self.store.delivery_valid(key))
        jobs=self.store.deliveries('codex');self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['delivery_id'],key)
        self.assertEqual(jobs[0]['current_generation'],2)
        self.assertEqual(jobs[0]['trigger_event'],'$changes')
        self.store.drain('codex',lambda job:external.update({job['delivery_id']:job}),'2026-10-10T15:01:00Z')
        self.assertEqual(len(external),1)

    def test_drain_crash_after_external_write_retries_without_duplicate(self):
        self.wait();self.answer();external={}
        def crash(job):
            external[job['delivery_id']]=job
            raise RuntimeError('crash after Chroma write before SQLite commit')
        with self.assertRaises(RuntimeError):self.store.drain('codex',crash,'2026-10-10T13:01:00Z')
        self.assertEqual(len(self.store.deliveries('codex')),1)
        writes=[]
        def deliver(job):
            if job['delivery_id'] not in external:writes.append(job)
            external.setdefault(job['delivery_id'],job)
        restart=c.CoordinationStore(self.path,enabled=True);restart.initialize()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:restart.drain('codex',deliver,'2026-10-10T13:02:00Z'),range(2)))
        self.assertEqual(writes,[]);self.assertEqual(len(external),1)
        key=next(iter(external));self.assertTrue(restart.delivery_valid(key))
        self.wait(expected_generation=1)
        self.assertFalse(restart.delivery_valid(key))
