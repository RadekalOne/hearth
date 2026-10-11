import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('inbox_ack', Path(__file__).parents[1]/'mcp/memory/inbox_ack.py')
ack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ack)


class AcknowledgementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ack.Acknowledgements(Path(self.temp.name)/'ack.sqlite3')
        self.item = {'kind':'overdue_work','id':'relay_fixture','state':'queued','revision':1}

    def test_acknowledge_reopen_idempotence_and_audit(self):
        key = ack.state_key(self.item)
        self.store.set(self.item,key,'rad',True)
        self.store.set(self.item,key,'rad',True)
        self.assertTrue(self.store.project([self.item])[0]['acknowledged'])
        self.assertEqual(len(self.store.audit()),1)
        self.store.set(self.item,key,'rad',False)
        self.assertFalse(self.store.project([self.item])[0]['acknowledged'])
        self.assertEqual(len(self.store.audit()),2)

    def test_round_trip_without_inbox_read_reopens(self):
        self.store.set(self.item,ack.state_key(self.item),'rad',True)
        self.item.update(state='queued',revision=3)
        self.assertFalse(self.store.project([self.item])[0]['acknowledged'])

    def test_new_receipt_and_thread_event_reopen(self):
        for item,field in [({'kind':'failed_watcher','id':'watcher','receipt_source':'checkpoint_1','checkpoint_at':'a'},'checkpoint_at'),
                           ({'kind':'blocked','event_id':'$block','latest_qualifying_event':'$old'},'latest_qualifying_event')]:
            self.store.set(item,ack.state_key(item),'rad',True)
            item[field]='new'
            self.assertFalse(self.store.project([item])[0]['acknowledged'])

    def test_stale_key_stores_nothing_and_survives_restart(self):
        old = ack.state_key(self.item)
        self.item['revision']=2
        with self.assertRaises(ack.StaleAcknowledgement):
            self.store.set(self.item,old,'rad',True)
        self.assertEqual(self.store.audit(),[])
        self.store.set(self.item,ack.state_key(self.item),'rad',True)
        self.assertTrue(ack.Acknowledgements(self.store.path).project([self.item])[0]['acknowledged'])
