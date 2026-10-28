from contextlib import closing
"""Authority, identity and relationship tests for the new record."""
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'mcp/memory'))
try:
    from hearth2.store import Store, Principal, RecordError
except ImportError:
    Store = None
    Principal = None
    RecordError = ValueError
from hearth2.schema import Schema


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Store, 'Hearth 2 store not implemented')
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'work.sqlite3'
        Schema.initialize(self.path, enabled=True)
        self.time = datetime(2026, 10, 28, 14, tzinfo=timezone.utc)
        self.store = Store(self.path, clock=lambda: self.time)
        self.rad = Principal('rad-subject', 'human')
        self.controller = Principal('controller', 'controller')
        self.worker = Principal('codex', 'worker')
        self.project = self.store.create_project(self.rad, {'title': 'Trial'})
        fields={'recipient':'codex','ask':'Build','done_means':'Evidence passes',
                'inputs':['drawer_fixture'],'return':'claude reviews'}
        self.action_manifest={'build':{**fields,'requires':{}},
            'parallel':{**fields,'requires':{}},
            'followup':{**fields,'requires':{'build':'accepted'}},
            'feasibility':{**fields,'requires':{'build':'output'}},
            'reviewed-child':{**fields,'requires':{'build':'reviewed'}}}
        self.plan = self.store.create_plan(self.rad, self.project['id'], {'content_ref': 'fixture-plan','actions':self.action_manifest})
        self.payload = {'project_id': self.project['id'], 'plan_id': self.plan['id'],
                        'action_id':'build', 'recipient': 'codex', 'ask': 'Build', 'done_means': 'Evidence passes',
                        'inputs': ['drawer_fixture'], 'return': 'claude reviews'}

    def decision(self, **extra):
        return self.store.create_decision(self.controller, self.plan['id'],
            intended_subject='rad-subject', expires_at='2026-10-29T14:00:00+00:00', **extra)

    def test_all_five_handoff_fields_required(self):
        for field in ['recipient','ask','done_means','inputs','return']:
            data = dict(self.payload); data.pop(field)
            with self.subTest(field=field), self.assertRaises(RecordError):
                self.store.create_task(self.controller, data)
        self.assertEqual(self.store.snapshot()['tasks'], [])

    def test_project_and_plan_relationship_cannot_be_spoofed(self):
        other = self.store.create_project(self.rad, {'title': 'Other'})
        with self.assertRaises(RecordError):
            self.store.create_task(self.rad, {**self.payload, 'project_id': other['id']})
        parent = self.store.create_task(self.rad, self.payload)
        op = self.store.create_plan(self.rad, other['id'], {'content_ref':'other'})
        with self.assertRaises(RecordError):
            self.store.create_task(self.rad, {**self.payload, 'project_id':other['id'],
                'plan_id':op['id'], 'dependencies':[parent['id']]})

    def test_dependency_repetition_refused(self):
        parent = self.store.create_task(self.rad, self.payload)
        with self.assertRaises(RecordError):
            self.store.create_task(self.rad, {**self.payload,'dependencies':[parent['id'],parent['id']]})

    def test_worker_cannot_create_management_state_or_consume_approval(self):
        for action in [lambda:self.store.create_project(self.worker, {'title':'Spoof'}),
                       lambda:self.store.create_task(self.worker,self.payload),
                       lambda:self.store.set_role(self.worker,'codex',{'model':'m','family':'openai','role':'senior'})]:
            with self.assertRaises(RecordError):action()
        d = self.decision()
        with self.assertRaises(RecordError):
            self.store.record_decision(self.worker,d['id'],1,'approve','event')
        self.assertEqual(self.store.snapshot()['plans'][0]['state'],'draft')

    def test_exact_human_revision_expiry_and_single_use(self):
        d = self.decision()
        for who,rev in [(Principal('other-human','human'),1),(self.rad,2)]:
            with self.assertRaises(RecordError):self.store.record_decision(who,d['id'],rev,'approve','event')
        self.store.record_decision(self.rad,d['id'],1,'approve','human-event')
        with self.assertRaises(RecordError):self.store.record_decision(self.rad,d['id'],1,'approve','replay')
        snap = self.store.snapshot()
        self.assertEqual(snap['plans'][0]['state'],'approved')
        self.assertEqual(snap['decisions'][0]['state'],'consumed')
        self.assertEqual(sum(x['action']=='decision_consumed' for x in snap['audit_events']),1)
        self.assertGreaterEqual(sum(x['action']=='decision_rejected' for x in snap['audit_events']),3)

    def test_expired_decision_refused_and_new_revision_fences_old(self):
        d = self.decision()
        self.time = datetime(2026,10,30,tzinfo=timezone.utc)
        with self.assertRaises(RecordError):self.store.record_decision(self.rad,d['id'],1,'approve','late')
        self.time = datetime(2026,10,28,tzinfo=timezone.utc)
        self.store.create_plan(self.rad,self.project['id'],{'content_ref':'revised'})
        with self.assertRaises(RecordError):self.store.record_decision(self.rad,d['id'],1,'approve','old-plan')
        self.assertTrue(all(p['state']=='draft' for p in self.store.snapshot()['plans']))

    def test_model_change_pauses_until_human_reconfirms(self):
        role = {'model':'original','family':'openai','role':'senior'}
        self.store.set_role(self.rad,'codex',role)
        changed = self.store.set_role(self.rad,'codex',{**role,'model':'new'})
        self.assertEqual(changed['state'],'paused')
        confirmed = self.store.set_role(self.rad,'codex',{**role,'model':'new','confirm':True})
        self.assertEqual(confirmed['state'],'active')

    def test_rejected_task_addition_is_atomic(self):
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.store.create_task(self.rad,{**self.payload,'dependencies':['missing']})
        after=self.store.snapshot()
        self.assertEqual(before['tasks'],after['tasks'])
        self.assertEqual(before['audit_events'],after['audit_events'])

    def test_no_secret_bearing_payloads_or_naive_expiry(self):
        with self.assertRaises(RecordError):
            self.store.create_plan(self.rad,self.project['id'],{'content_ref':'x','password':'do-not-store'})
        with self.assertRaises(RecordError):
            self.store.create_decision(self.controller,self.plan['id'],intended_subject='rad-subject',expires_at='2026-10-29T14:00:00')

if __name__ == '__main__':unittest.main()
