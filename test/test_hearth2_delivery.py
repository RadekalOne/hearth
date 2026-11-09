"""Named-session receipt authority against temporary work-record fixtures."""
import json,unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import test_hearth2_receipts as fixtures
from hearth2.store import Principal,RecordError,Store
from hearth2.backup import export_record,restore_record


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)
        from hearth2.delivery import NoticeSession
        self.target=NoticeSession('claude-a','claude-session-a','claude')
        self.other=NoticeSession('claude-b','claude-session-b','claude')
        self.session=Principal(self.target.principal_id,'session')
        self.notice=self.store.append_notice(self.controller,dict(task_id=self.task['id'],recipient='claude',
            recipient_session='claude-a',kind='interface_changed',reference='exact-notice-body'),
            claim=self.claim,delivery_target=self.target)

    def epoch(self):return self.store.control_snapshot()['restore_epoch']

    def receive(self,request_id='read-one',actor=None,target=None,**changes):
        from hearth2.delivery import receive_notice
        fields=dict(request_id=request_id,expected_epoch=self.epoch());fields.update(changes)
        return receive_notice(self.store,actor or self.session,target or self.target,self.notice['id'],**fields)

    def ack(self,offer,actor=None,target=None,**changes):
        from hearth2.delivery import acknowledge_notice
        fields={key:offer[key] for key in ['delivery_id','notice_digest','restore_epoch']}
        fields['expected_epoch']=fields.pop('restore_epoch');fields.update(changes)
        return acknowledge_notice(self.store,actor or self.session,target or self.target,self.notice['id'],**fields)

    def status(self):
        from hearth2.human_status import human_status
        return human_status(self.store,{'controller'}, {})['notices'][0]

    def test_receive_then_ack_is_exact_durable_and_never_advances_work(self):
        from hearth2.delivery import session_inbox
        before=self.store.snapshot();self.assertEqual(self.status()['delivery_state'],'unconfirmed')
        self.assertEqual(session_inbox(self.store,self.session,self.target)['notices'][0]['id'],self.notice['id'])
        offer=self.receive()
        self.assertEqual((offer['notice']['reference'],offer['session_id']),('exact-notice-body','claude-a'))
        self.assertEqual(self.status()['delivery_state'],'unconfirmed')
        receipt=self.ack(offer);self.assertEqual(receipt['actor'],self.session.id)
        self.time+=timedelta(seconds=3)
        self.assertEqual(self.ack(offer),receipt)
        self.assertEqual(self.receive(),offer)
        newer=self.receive('read-two');self.assertEqual(self.ack(newer),receipt)
        self.store=Store(self.path,clock=lambda:self.time)
        view=self.status()
        self.assertEqual((view['delivery_state'],view['acknowledgement_state'],view['understanding_state']),('received','receipt_recorded','unknown'))
        self.assertEqual(view['acknowledged_at'],receipt['at'])
        self.assertEqual(view['receipt_actor'],self.session.id)
        self.assertEqual(session_inbox(self.store,self.session,self.target)['notices'],[])
        for table in ['tasks','runs','claims','incidents','incident_attempts','notices']:
            self.assertEqual(self.store.snapshot()[table],before[table])

    def test_other_session_same_agent_wrong_roles_and_rebinding_are_rejected_atomically(self):
        from hearth2.delivery import NoticeSession
        offer=self.receive()
        for actor,target in [(Principal(self.other.principal_id,'session'),self.other),
                (self.controller,self.target),(self.worker,self.target),(self.rad,self.target),
                (Principal('watcher','observer'),self.target),
                (Principal('new-session-principal','session'),NoticeSession('claude-a','new-session-principal','claude'))]:
            before=self.store.snapshot()
            with self.assertRaises(RecordError):self.receive('wrong',actor,target)
            with self.assertRaises(RecordError):self.ack(offer,actor,target)
            self.assertEqual(self.store.snapshot(),before)

    def test_no_offer_wrong_digest_or_id_and_stale_epoch_do_not_ack(self):
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.ack(dict(delivery_id='not-issued',notice_digest='0'*64,restore_epoch=self.epoch()))
        self.assertEqual(self.store.snapshot(),before)
        offer=self.receive()
        for changes in [dict(delivery_id='not-issued'),dict(notice_digest='0'*64),dict(expected_epoch='old')]:
            before=self.store.snapshot()
            with self.assertRaises(RecordError):self.ack(offer,**changes)
            self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(self.status()['delivery_state'],'unconfirmed')

    def test_changed_body_rejects_offer_ack_and_read_model_receipt(self):
        offer=self.receive();self.ack(offer)
        data=json.loads(self.notice['data']);data['reference']='changed after addressing'
        with self.store.transaction() as db:db.execute('UPDATE notices SET data=? WHERE id=?',(json.dumps(data),self.notice['id']))
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.receive('changed')
        with self.assertRaises(RecordError):self.ack(offer)
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(self.status()['delivery_state'],'unconfirmed')

    def test_restore_preserves_receipt_fact_but_refuses_old_in_flight_requests(self):
        offer=self.receive();receipt=self.ack(offer)
        bundle=Path(self.tmp.name)/'delivery.json';target=Path(self.tmp.name)/'delivery-restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        self.store=Store(target,clock=lambda:self.time)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):self.receive(expected_epoch=offer['restore_epoch'])
        with self.assertRaises(RecordError):self.ack(offer)
        self.assertEqual(self.store.snapshot(),before)
        current=self.receive();self.assertNotEqual(current['restore_epoch'],offer['restore_epoch'])
        self.assertEqual(self.ack(current),receipt)
        self.assertTrue(self.status()['receipt_historical'])
        self.assertEqual(self.status()['acknowledged_at'],receipt['at'])

    def test_delivery_offer_cannot_be_reused_for_another_notice(self):
        from hearth2.delivery import acknowledge_notice
        offer=self.receive()
        other=self.store.append_notice(self.controller,dict(task_id=self.task['id'],recipient='claude',
            recipient_session='claude-a',kind='interface_changed',reference='exact-notice-body'),
            claim=self.claim,delivery_target=self.target)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):acknowledge_notice(self.store,self.session,self.target,other['id'],
            delivery_id=offer['delivery_id'],notice_digest=offer['notice_digest'],expected_epoch=self.epoch())
        self.assertEqual(self.store.snapshot(),before)

    def test_failed_ack_append_has_no_receipt_or_state_change(self):
        offer=self.receive();before=self.store.snapshot()
        with patch.object(self.store,'audit',side_effect=RuntimeError('fixture append failure')):
            with self.assertRaises(RuntimeError):self.ack(offer)
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(self.status()['delivery_state'],'unconfirmed')

    def test_legacy_payload_metadata_cannot_create_addressing_or_receipt(self):
        from hearth2.delivery import receive_notice
        legacy=self.store.append_notice(self.controller,dict(task_id=self.task['id'],recipient='claude',kind='blocked',
            reference='legacy',delivery_target={'session_id':'claude-a'},acknowledged_at='FORGED',
            receipt_actor='FORGED',delivery_state='received',understanding_state='understood'),claim=self.claim)
        before=self.store.snapshot()
        with self.assertRaises(RecordError):receive_notice(self.store,self.session,self.target,legacy['id'],request_id='legacy',expected_epoch=self.epoch())
        self.assertEqual(self.store.snapshot(),before)
        from hearth2.human_status import human_status
        row=next(n for n in human_status(self.store,{'controller'}, {})['notices'] if n['id']==legacy['id'])
        self.assertEqual((row['delivery_state'],row['intended_session'],row['receipt_actor'],row['understanding_state']),('unconfirmed',None,None,'unknown'))
        with self.assertRaises(RecordError):self.store.append_notice(self.controller,dict(task_id=self.task['id'],recipient='claude',recipient_session='claude-a',kind='blocked',reference='no enrollment'),claim=self.claim)
