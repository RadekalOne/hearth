"""Human-readable obligations and real responsibility transition contracts."""
import importlib.util
import tempfile
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'mcp/memory' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value
c = module('coordination'); d = module('dashboard')
ACTION = {'steps':['Open the task and choose Approve or Request changes.'],
          'after':'Codex will continue after your choice.', 'ask':'Ask Codex in the task thread.'}

class HumanActionTests(unittest.TestCase):
    def test_human_wait_requires_useful_instructions(self):
        base = {'kind':'human', 'id':'rad', 'required_surface':'interactive'}
        for action in [None, {}, {'steps':[]}, {**ACTION,'steps':['']}, {**ACTION,'steps':['a']*4}, {**ACTION,'ask':''}]:
            with self.subTest(action=action), self.assertRaises(c.CoordinationError):
                c.party({**base, 'human_action':action})
        self.assertEqual(c.party({**base,'human_action':ACTION})['human_action'], ACTION)
        self.assertNotIn('human_action', c.party({'kind':'agent','id':'codex','required_surface':'interactive'}))

    def test_pass_to_human_requires_authored_steps_and_preserves_them(self):
        with tempfile.TemporaryDirectory() as temp:
            store = c.CoordinationStore(Path(temp)/'c.sqlite', enabled=True); store.initialize()
            ids = dict(work_kind='thread_plan', work_id='plan', room_id='!tasks:test', thread_id='$task')
            store.set_wait('codex',False,owner='codex',parties=[{'kind':'agent','id':'claude','required_surface':'interactive'}],source_event='$wait',since='2026-10-11T12:00:00Z',**ids)
            answer = dict(expected_generation=1,party_id='claude',answer_kind='pass_needing_human',source_event='$pass',since='2026-10-11T13:00:00Z',summary='Reviewed',evidence=['commit'],approval_party='rad',**ids)
            with self.assertRaises(c.CoordinationError):store.answer('claude',False,**answer)
            self.assertEqual(store.read(**ids)['generation'],1)
            result=store.answer('claude',False,human_action=ACTION,**answer)
            self.assertEqual(result['coordination_waiting_on'][0]['human_action'],ACTION)
    def test_change_list_can_return_to_a_human_owner_with_authored_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            store=c.CoordinationStore(Path(temp)/'c.sqlite',enabled=True);store.initialize()
            ids=dict(work_kind='thread_plan',work_id='human-plan',room_id='!tasks:test',thread_id='$human')
            store.set_wait('rad',True,owner='rad',owner_kind='human',parties=[{'kind':'agent','id':'codex','required_surface':'interactive'}],
                source_event='$ask',since='2026-10-11T12:00:00Z',**ids)
            result=store.answer('codex',False,expected_generation=1,party_id='codex',answer_kind='change_list',source_event='$review',
                since='2026-10-11T13:00:00Z',summary='Please choose the next option.',evidence=['diff'],human_action=ACTION,**ids)
            self.assertEqual(result['coordination_waiting_on'][0]['human_action'],ACTION)

class RecoveryProjectionTests(unittest.TestCase):
    def test_successful_receipt_with_recovery_notes_stays_healthy(self):
        for fields in [
            {'process_exit':0,'notes':'Recovered from the OAuth session expired outage'},
            {'process_exit':'0','error':'OAuth session expired','reason':'auth_expired'},
            {'process_exit':0,'closeout_verified':True,'reason':'auth_expired'},
        ]:
            with self.subTest(fields=fields):
                receipt=d.receipt(json.dumps(fields))
                self.assertNotIn('reason',receipt)
                self.assertEqual(d.watcher_state(1,60,receipt),'ok')
                self.assertEqual(d.attention_inbox({'items':[]},[{'id':'healthy','state':'ok','receipt':receipt}],[])['items'],[])

    def test_failed_receipt_uses_error_not_notes_for_auth_classification(self):
        for content in [
            json.dumps({'process_exit':1,'error':'Network unavailable','notes':'OAuth session expired last week'}),
            'process_exit: 1\nnotes: OAuth session expired last week\nerror: Network unavailable',
        ]:
            with self.subTest(content=content):
                receipt=d.receipt(content)
                self.assertNotIn('reason',receipt)
                self.assertEqual(d.watcher_state(1,60,receipt),'failed')

    def test_auth_recovery_requires_failure_evidence_and_preserves_true_positives(self):
        for fields in [
            {'process_exit':1,'error':'OAuth session expired'},
            {'process_exit':'1','reason':'auth_expired'},
            {'process_exit':0,'closeout_verified':False,'error':'Authentication expired'},
        ]:
            with self.subTest(fields=fields):
                receipt=d.receipt(json.dumps(fields))
                self.assertEqual(receipt['reason'],'auth_expired')
                self.assertEqual(d.watcher_state(1,60,receipt),'failed')
        self.assertNotIn('reason',d.receipt('{"error":"OAuth session expired"}'))
        self.assertEqual(d.watcher_state(1,60,{'reason':'auth_expired','process_exit':0}),'ok')

    def test_existing_acknowledgement_key_survives_unrelated_upgrade(self):
        import hashlib,json
        ack=module('inbox_ack')
        item={'kind':'blocked','event_id':'$old','state':None,'action_generation':0}
        original=hashlib.sha256(json.dumps(['blocked','$old',(0,None,None,None,None,'$old')],sort_keys=True).encode()).hexdigest()
        self.assertEqual(ack.state_key(item),original)
        self.assertNotEqual(ack.state_key({**item,'action_generation':1}),original)
    def test_auth_expiry_is_one_actionable_item_with_evidence(self):
        receipt=d.receipt('{"process_exit":1,"error":"OAuth session expired. Please log in."}')
        self.assertEqual(receipt.get('reason'),'auth_expired')
        monitors=[{'id':'watcher1','state':'failed','agent':'claude','surface':'desktop (auto)','monitor':'sweep','receipt':receipt,'source_refs':['cp1']},
                  {'id':'watcher2','state':'failed','agent':'claude','surface':'desktop (reflection)','monitor':'reflection','receipt':receipt,'source_refs':['cp2']}]
        result=d.attention_inbox({'items':[]},monitors,[])
        self.assertEqual(len(result['items']),1)
        item=result['items'][0];self.assertEqual(item['kind'],'auth_expired')
        self.assertEqual(set(item['source_refs']),{'cp1','cp2'})
        self.assertIn('/login',' '.join(item['human_action']['steps']))
        self.assertNotIn('error',item['receipt'])

    def test_claim_expiry_keeps_last_state_and_returns_attention(self):
        work=d.work_items({'tasks':[{'id':'task1','state':'running','claim_expired':True,'claim_until':1,'title':'Review inbox','assignee':'codex'}]},[],1000)
        self.assertEqual(work[0]['state'],'claim_expired')
        self.assertEqual(work[0]['last_state'],'running')
        item=d.attention_inbox({'items':[]},[],work)['items'][0]
        self.assertEqual(item['kind'],'claim_expired');self.assertIn('human_action',item)

    def test_legacy_items_get_steps_not_evidence_as_instruction(self):
        items=[{'kind':kind,'event_id':'$'+kind,'sender':'codex','room_id':'!tasks:test','source_refs':['$'+kind]} for kind in ['blocked','unclaimed_task','approval','question']]
        result=d.attention_inbox({'items':items},[],[])
        for item in result['items']:
            self.assertTrue(1<=len(item['human_action']['steps'])<=3)
            self.assertTrue(item['human_action']['after']);self.assertTrue(item['human_action']['ask'])
            self.assertNotIn(item['event_id'],' '.join(item['human_action']['steps']))

class AttentionActionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=c.CoordinationStore(Path(self.temp.name)/'c.sqlite',enabled=True);self.store.initialize()
        self.ids=dict(work_kind='thread_plan',work_id='plan',room_id='!tasks:test',thread_id='$task')
        self.store.set_wait('codex',False,owner='codex',parties=[{'kind':'agent','id':'claude','required_surface':'interactive'},
            {'kind':'agent','id':'mavis','required_surface':'background'}],source_event='$wait',since='2026-10-11T12:00:00Z',**self.ids)
        self.item={'kind':'coordination_wait','id':'wait1','state':'pending','revision':1,'generation':1,
                   'party_id':'claude','party_kind':'agent',**self.ids}
        self.target={'kind':'agent','id':'codex','required_surface':'interactive'}
    def tearDown(self):self.temp.cleanup()
    def act(self,**extra):
        return self.store.attention_action('rad',True,self.item,'source-key','reassign',self.target,'Codex can handle this.',0,**extra)
    def test_reassign_fences_old_answer_preserves_peer_and_audits(self):
        result=self.act();self.assertEqual(result['action_generation'],1)
        state=self.store.read(**self.ids)
        self.assertEqual(state['generation'],2)
        self.assertEqual({p['id'] for p in state['coordination_waiting_on']},{'codex','mavis'})
        with self.assertRaises(c.CoordinationError):
            self.store.answer('claude',False,expected_generation=1,party_id='claude',answer_kind='final_completion',
                source_event='$late',since='2026-10-11T13:00:00Z',summary='Late review',evidence=['commit'],**self.ids)
        self.assertEqual(self.store.attention_audit()[0]['reason'],'Codex can handle this.')
        with self.assertRaises(c.CoordinationError):self.act()
    def test_nonhuman_cannot_reassign_and_dispatch_persists_priority(self):
        with self.assertRaises(c.CoordinationError):
            self.store.attention_action('codex',False,self.item,'key','dispatch',self.target,'Start this.',0)
        generic={'kind':'overdue_work','id':'relay1','state':'queued'}
        self.store.attention_action('rad',True,generic,'key','dispatch',self.target,'Start this.',0)
        reopened=c.CoordinationStore(self.store.path,enabled=True);reopened.initialize()
        saved=reopened.attention_state('overdue_work','relay1','key')
        self.assertEqual(saved['priority'],'high')
        self.assertEqual({k:saved['party'][k] for k in self.target},self.target)
        self.assertNotIn('action',reopened.attention_state('overdue_work','relay1','changed'))
    def test_missing_reason_or_invalid_target_cannot_change_state(self):
        for reason,target in [('',self.target),('Reassign',{'kind':'human','id':'rad','required_surface':'interactive'})]:
            with self.assertRaises(c.CoordinationError):
                self.store.attention_action('rad',True,self.item,'key','reassign',target,reason,0)
        self.assertEqual(self.store.read(**self.ids)['generation'],1)
