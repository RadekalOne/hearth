"""Capability boundaries exercised without provider calls or real credentials."""
import json
import unittest
from datetime import timedelta
import test_hearth2_receipts as fixtures
from hearth2.store import Principal
from hearth2.broker import Broker, BrokerError
from hearth2.backup import export_record, restore_record
from hearth2.store import Store
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from hearth2.store import timestamp


class BrokerTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReceiptTests.setUp(self)
        self.calls=[]
        def upstream(tool,args):
            self.calls.append((tool,args))
            row={'drawer_id':'drawer_fixture','wing':'trial','room':'project','content':'existing answer'}
            return {'results':[row]} if tool=='memory_search' else row
        self.upstream=upstream
        self.broker=Broker(self.store,self.controller,self.upstream)

    def grant(self,**changes):
        fields=dict(wing='trial',room='project');fields.update(changes)
        return self.broker.mint(self.controller,self.claim,**fields)

    def test_scoped_reads_and_no_bearer_persistence(self):
        token=self.grant()
        result=self.broker.read(token,'memory_search',{'query':'existing answer','limit':2})
        self.assertEqual(result['results'][0]['content'],'existing answer')
        self.assertEqual(self.calls,[('memory_search',{'query':'existing answer','limit':2,'wing':'trial','room':'project'})])
        self.assertEqual(self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})['drawer_id'],'drawer_fixture')
        self.assertNotIn(token,json.dumps(self.store.snapshot()))
        self.assertNotIn(token,repr(self.broker))

    def test_worker_cannot_mint_or_broaden_scope_or_select_writes(self):
        with self.assertRaises(BrokerError):self.broker.mint(self.worker,self.claim,wing='trial',room='project')
        token=self.grant()
        for tool,args in [('memory_add',{'content':'injected'}),('work_claim',{}),
                          ('memory_search',{'query':'answer','wing':'production'}),
                          ('memory_get',{'drawer_id':'drawer_fixture','room':'other'}),
                          ('memory_search',{'query':'answer','limit':True})]:
            with self.subTest(tool=tool,args=args),self.assertRaises(BrokerError):self.broker.read(token,tool,args)
        self.assertEqual(self.calls,[])

    def test_only_one_active_grant_and_unknown_grant_denied(self):
        first=self.grant()
        with self.assertRaises(BrokerError):self.grant()
        with self.assertRaises(BrokerError):self.broker.read('not-a-grant','memory_get',{'drawer_id':'drawer_fixture'})
        self.broker.revoke(self.controller,first)
        with self.assertRaises(BrokerError):self.broker.read(first,'memory_get',{'drawer_id':'drawer_fixture'})
        self.assertNotEqual(self.grant(),first)

    def test_expired_lease_is_denied_before_upstream_read(self):
        token=self.grant();self.time+=timedelta(minutes=16)
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        self.assertEqual(self.calls,[])

    def test_closed_claim_and_new_attempt_invalidate_old_grant(self):
        token=self.grant()
        self.store.reconcile(self.controller,self.claim['run_id'],outcome='failed',termination_evidence=['empty'])
        task=self.store.snapshot()['tasks'][0]
        self.claim=self.store.claim(self.controller,task['id'],expected_revision=task['revision'],request_id='retry')
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        fresh=self.grant();self.assertNotEqual(fresh,token)

    def test_broker_restart_revokes_all_capabilities(self):
        token=self.grant()
        restarted=Broker(self.store,self.controller,self.upstream)
        with self.assertRaises(BrokerError):restarted.read(token,'memory_get',{'drawer_id':'drawer_fixture'})

    def test_expiry_during_upstream_call_withholds_response(self):
        def slow(tool,args):
            self.time+=timedelta(minutes=16)
            return self.upstream(tool,args)
        self.broker=Broker(self.store,self.controller,slow);token=self.grant()
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        self.assertEqual(len(self.calls),1)

    def test_revocation_during_upstream_call_withholds_response(self):
        def revoked(tool,args):
            self.broker.revoke(self.controller,token)
            return self.upstream(tool,args)
        self.broker=Broker(self.store,self.controller,revoked);token=self.grant()
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})

    def test_bad_upstream_scope_secrets_and_errors_never_escape(self):
        for response in [{'drawer_id':'drawer_fixture','wing':'other','room':'project','content':'private'},
                         {'drawer_id':'drawer_fixture','wing':'trial','room':'project','access_token':'fixture-secret'},
                         {'error':'root credential fixture-secret'}]:
            self.broker=Broker(self.store,self.controller,lambda tool,args:response)
            token=self.grant()
            with self.assertRaises(BrokerError) as caught:self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
            self.assertNotIn('fixture-secret',str(caught.exception))

    def test_unconfirmed_termination_never_authorizes_broker(self):
        token=self.grant()
        self.store.record_run(self.controller,self.claim,{**self.receipt,'containment_state':'unconfirmed','termination_evidence':[]})
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        with self.assertRaises(BrokerError):self.grant()

    def test_restore_epoch_invalidates_existing_capability(self):
        token=self.grant()
        bundle,target=Path(self.tmp.name)/'broker.json',Path(self.tmp.name)/'restored.db'
        export_record(self.path,bundle);restore_record(bundle,target,controller_stopped=True)
        self.broker.store=Store(target,clock=lambda:self.time)
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        self.assertEqual(self.calls,[])

    def test_read_scope_is_checked_on_search_results_too(self):
        self.broker=Broker(self.store,self.controller,lambda tool,args:{'results':[
            {'drawer_id':'drawer_other','wing':'other','room':'private','content':'outside'}]})
        token=self.grant()
        with self.assertRaises(BrokerError):self.broker.read(token,'memory_search',{'query':'answer'})

    def test_database_lock_wait_cannot_extend_a_grants_fixed_expiry(self):
        token=self.grant();expiry=timestamp(self.claim['lease_until'])
        self.store.renew(self.controller,self.claim,lease_until=(self.time+timedelta(minutes=30)).isoformat())
        self.time=expiry-timedelta(seconds=1)
        transaction=self.store.transaction;entries=0
        @contextmanager
        def delayed_transaction():
            nonlocal entries
            entries+=1
            if entries==2:self.time+=timedelta(seconds=2)
            with transaction() as db:yield db
        with patch.object(self.store,'transaction',delayed_transaction):
            with self.assertRaises(BrokerError):self.broker.read(token,'memory_get',{'drawer_id':'drawer_fixture'})
        self.assertGreater(self.time,expiry)
