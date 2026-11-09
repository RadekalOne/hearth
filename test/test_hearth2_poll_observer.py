"""Independent observer journal behavior, using only temporary fixture stores."""
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import test_hearth2_receipts as fixtures
from hearth2.store import Principal, RecordError, Store
from hearth2.backup import export_record, restore_record


class PollObserverTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)
        self.observer=Principal('watcher','observer')
        self.policy={'controller':{'cadence_seconds':60,'grace_seconds':10}}

    def tick(self,request_id='poll',expected_seq=0):
        return self.store.runner_tick(self.controller,request_id=request_id,expected_seq=expected_seq,
            expected_epoch=self.store.control_snapshot()['restore_epoch'],evidence=['controller-supplied-ref'])

    def check(self,request_id='check',expected_seq=0,actor=None,**changes):
        from hearth2.poll_observer import observe_polls
        fields=dict(controllers={'controller'},expectations=self.policy,request_id=request_id,
            expected_seq=expected_seq,expected_epoch=self.store.control_snapshot()['restore_epoch'])
        fields.update(changes)
        return observe_polls(self.store,actor or self.observer,**fields)

    def test_stopped_poller_and_recovery_require_separate_observer_checks(self):
        tick=self.tick();before=self.store.snapshot()
        first=self.check();self.assertEqual(first['observations'][0]['incident_state'],'none')
        self.time+=timedelta(seconds=71)
        opened=self.check('stopped',first['seq']);row=opened['observations'][0]
        self.assertEqual((row['poll_state'],row['incident_state'],row['stale_tick_sequence']),('stale','open',tick['seq']))
        self.assertEqual(row['last_completed_at'],tick['at'])
        # Arbitrary controller reports are in a different record space.
        failure=self.store.control_failure(self.controller,kind='runner_stale',target='controller',key='controller-claim',
            expected_seq=0,expected_epoch=opened['restore_epoch'],state='open',evidence=['I am fine'])
        self.store.control_failure(Principal('supervisor','controller'),kind='runner_stale',target='controller',key='controller-claim',
            expected_seq=failure['seq'],expected_epoch=opened['restore_epoch'],state='recovered',evidence=['claim only'])
        self.assertEqual(self.store.control_snapshot()['observations'][0],opened)
        resumed=self.tick('resumed',tick['seq'])
        self.assertEqual(self.store.control_snapshot()['observations'][0],opened)
        recovered=self.check('checked-resumption',opened['seq'])['observations'][0]
        self.assertEqual((recovered['incident_state'],recovered['recovery_tick_sequence']),('recovered',resumed['seq']))
        for table in ['tasks','runs','claims','incidents','incident_attempts']:
            self.assertEqual(self.store.snapshot()[table],before[table])

    def test_threshold_and_replayed_checks_do_not_refresh_either_clock(self):
        tick=self.tick();self.time+=timedelta(seconds=70)
        first=self.check();self.assertEqual(first['observations'][0]['poll_state'],'recent')
        self.time+=timedelta(seconds=1)
        self.assertEqual(self.check(),first)
        self.assertEqual(self.tick(),tick)
        stale=self.check('new-check',first['seq'])
        self.assertEqual(stale['observations'][0]['incident_state'],'open')
        with self.assertRaises(RecordError):self.check('conflicting-check')
        self.assertEqual(self.store.control_snapshot()['observations'][0],stale)
        self.assertEqual(self.check(),first)  # Older request stays original after a newer check.
        with self.assertRaises(RecordError):self.check(expectations={})
        self.assertEqual(self.store.control_snapshot()['observations'][0],stale)

    def test_unknown_never_closes_open_and_same_tick_cannot_recover_after_policy_change(self):
        tick=self.tick();self.time+=timedelta(seconds=71)
        opened=self.check();self.assertEqual(opened['observations'][0]['incident_state'],'open')
        unknown=self.check('no-policy',opened['seq'],expectations={})
        self.assertEqual((unknown['observations'][0]['poll_state'],unknown['observations'][0]['incident_state']),('unknown','open'))
        recent=self.check('longer-policy',unknown['seq'],expectations={'controller':{'cadence_seconds':120,'grace_seconds':0}})
        self.assertEqual((recent['observations'][0]['poll_state'],recent['observations'][0]['incident_state']),('recent','open'))
        for stamp,reason in [('bad','poll_time_unusable'),((self.time+timedelta(hours=1)).isoformat(),'poll_time_in_future')]:
            with self.store.transaction() as db:db.execute('UPDATE audit_events SET at=? WHERE seq=?',(stamp,tick['seq']))
            current=self.check(reason,recent['seq']);recent=current
            self.assertEqual((current['observations'][0]['reason'],current['observations'][0]['incident_state']),(reason,'open'))

    def test_newer_but_already_overdue_tick_is_not_recovery_after_policy_relaxation(self):
        first=self.tick();self.time+=timedelta(seconds=71);opened=self.check()
        newer=self.tick('also-stopped',first['seq']);self.time+=timedelta(seconds=71)
        still_stale=self.check('still-stopped',opened['seq'])
        self.assertEqual(still_stale['observations'][0]['stale_tick_sequence'],newer['seq'])
        relaxed=self.check('relaxed',still_stale['seq'],expectations={'controller':{'cadence_seconds':120,'grace_seconds':0}})
        self.assertEqual((relaxed['observations'][0]['poll_state'],relaxed['observations'][0]['incident_state']),('recent','open'))

    def test_missing_poll_is_unknown_and_authority_or_bad_config_never_writes(self):
        unknown=self.check();self.assertEqual((unknown['observations'][0]['reason'],unknown['observations'][0]['incident_state']),('no_completed_poll','none'))
        for actor in [self.controller,self.rad,self.worker,Principal('controller','observer')]:
            before=self.store.snapshot()
            with self.assertRaises(RecordError):self.check('forged',unknown['seq'],actor)
            self.assertEqual(self.store.snapshot(),before)
        for changes in [dict(expected_epoch='old'),dict(expected_seq=True),dict(controllers={str(i) for i in range(129)}),
                dict(expectations={'controller':{'cadence_seconds':True,'grace_seconds':0}})]:
            before=self.store.snapshot()
            with self.assertRaises(RecordError):self.check('bad',**{'expected_seq':unknown['seq'],**changes})
            self.assertEqual(self.store.snapshot(),before)

    def test_restore_requires_new_epoch_and_does_not_inherit_recovery(self):
        self.tick();first=self.check()
        bundle=Path(self.tmp.name)/'observer.json';target=Path(self.tmp.name)/'restored-observer.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        self.store=Store(target,clock=lambda:self.time)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.check(expected_epoch=first['restore_epoch'])
        self.assertEqual(self.store.snapshot(),before)
        new=self.check()
        self.assertEqual((new['observations'][0]['poll_state'],new['observations'][0]['incident_state']),('unknown','none'))
        self.assertNotEqual(new['restore_epoch'],first['restore_epoch'])

    def test_restart_and_other_observer_do_not_reassign_open_incident(self):
        tick=self.tick();self.time+=timedelta(seconds=71);opened=self.check()
        self.store=Store(self.path,clock=lambda:self.time)
        self.assertEqual(self.store.control_snapshot()['observations'][0],opened)
        self.tick('resumption',tick['seq'])
        other=self.check('other-check',actor=Principal('other-watcher','observer'))
        self.assertEqual(other['observations'][0]['incident_state'],'none')
        self.assertIn(opened,self.store.control_snapshot()['observations'])
        recovered=self.check('original-observer-check',opened['seq'])
        self.assertEqual(recovered['observations'][0]['incident_state'],'recovered')
        self.time+=timedelta(seconds=71)
        reopened=self.check('second-outage',recovered['seq'])
        self.assertEqual((reopened['observations'][0]['incident_state'],reopened['observations'][0]['recovery_tick_sequence']),('open',None))

    def test_failed_append_rolls_back_entire_observation(self):
        self.tick();before=self.store.snapshot()
        with patch.object(self.store,'audit',side_effect=RuntimeError('fixture append failure')):
            with self.assertRaises(RuntimeError):self.check()
        self.assertEqual(self.store.snapshot(),before)
