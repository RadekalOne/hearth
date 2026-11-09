"""Human workflow acceptance against the real authenticated, isolated HTTP app.

Characterizes existing behavior; no native runner, room message or provider call.
Delivery acknowledgement and automatic stale detection are not implemented here.
"""
from datetime import datetime,timedelta,timezone
import unittest
from unittest.mock import patch
from test import test_hearth2_api as api


class DeliveryHealthAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        api.Hearth2APITests.setUpClass.__func__(cls)
        # A separate fixture identity, still a controller principal. This does
        # not implement or prove a distinct observer authority class.
        cls.memory.h2_runtime.controllers.add('supervisor')
        tokens=cls.memory.load_tokens();tokens['supervisor']='supervisor-fixture-token';cls.memory.save_tokens(tokens)

    @classmethod
    def tearDownClass(cls):api.Hearth2APITests.tearDownClass.__func__(cls)

    asyncSetUp=api.Hearth2APITests.asyncSetUp
    asyncTearDown=api.Hearth2APITests.asyncTearDown
    post=api.Hearth2APITests.post

    async def get(self,path):
        response=await self.client.get('/api/hearth2'+path,headers={'Authorization':'Bearer admin-test-token'})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def save(self,path,data,token='admin-test-token'):
        response=await self.post(path,data,token)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def test_assign_inspect_progress_and_return_result_preserving_delivery_unknown(self):
        project=await self.save('/projects',{'title':'Prepare a project handoff','goal':'A new teammate can find the next step.'})
        handoff={'recipient':'codex','ask':'Draft the onboarding handoff','done_means':'Handoff includes the next step',
                 'inputs':['synthetic-project-brief'],'return':'Independent review, then human acceptance'}
        plan=await self.save('/projects/'+project['id']+'/plans',{'content_ref':'synthetic-approved-handoff',
            'actions':{'draft':{**handoff,'requires':{}}}})
        decision=await self.save('/decisions',{'plan_id':plan['id'],'intended_subject':'admin',
            'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
        await self.save('/decisions/'+decision['id']+'/actions',{'expected_revision':1,'action':'approve','source':'synthetic-human-approval'})
        for agent,model,family in [('codex','gpt-6.1-sol','openai'),('claude','claude','anthropic')]:
            await self.save('/roles/'+agent,{'model':model,'family':family,'role':'senior'})
        task=await self.save('/tasks',{'project_id':project['id'],'plan_id':plan['id'],'action_id':'draft',**handoff})
        async def current():
            snapshot=await self.get('?project_id='+project['id'])
            return next(t for t in snapshot['tasks'] if t['id']==task['id']),snapshot
        self.assertEqual((await current())[0]['state'],'ready')
        claim=await self.save('/tasks/'+task['id']+'/claim',{'expected_revision':task['revision'],
            'request_id':'acceptance-handoff'},'controller-fixture-token')
        self.assertEqual((await current())[0]['state'],'running')
        # A stored notice is visible to the human; it is not a delivery receipt.
        notice=await self.save('/notices',{'claim':claim,'notice':{'task_id':task['id'],
            'recipient':'admin','kind':'interface_changed','reference':'synthetic-progress-note'}},'controller-fixture-token')
        snapshot=(await current())[1]
        saved=next(n for n in snapshot['notices'] if n['id']==notice['id'])
        self.assertEqual((saved['sender'],saved['recipient'],saved['kind']),('controller','admin','interface_changed'))
        self.assertNotIn('delivered_at',saved)
        self.assertNotIn('acknowledged_at',saved)
        # Opening this human record must not secretly mark the notice delivered.
        again=(await current())[1]
        self.assertEqual(next(n for n in again['notices'] if n['id']==notice['id']),saved)
        result=await self.save('/runs/'+claim['run_id']+'/receipt',{'claim':claim,'receipt':{
            'ended_at':datetime.now(timezone.utc).isoformat(),'exit_status':0,
            'closeout':{'task':task['id'],'attempt':1,'status':'done','produced':'synthetic-handoff-result',
                'changed':'Drafted handoff','unblocked':'none','memory-used':['synthetic-project-brief'],
                'checks-run':[{'name':'Next step included','passed':True,'evidence':'synthetic-content-check'}],
                'next':'Independent review'},'containment_state':'verified_empty',
            'termination_evidence':['synthetic-controller-stop-observation'],'usage':{'state':'unknown','units':None}}},
            'controller-fixture-token')
        self.assertEqual(result['closeout_validation'],'valid')
        waiting,snapshot=await current()
        self.assertEqual(waiting['state'],'review')
        reviewed=await self.save('/tasks/'+task['id']+'/reviews',{'expected_revision':waiting['revision'],
            'verdict':'pass','evidence':['synthetic-independent-check']},'claude-fixture-token')
        self.assertEqual(reviewed['state'],'reviewed')
        accepted=await self.save('/tasks/'+task['id']+'/acceptance',{'expected_revision':reviewed['revision'],
            'evidence':['synthetic-human-result-acceptance']})
        self.assertEqual(accepted['state'],'accepted')
        final,snapshot=await current()
        self.assertEqual(final['state'],'accepted')
        self.assertEqual(next(r for r in snapshot['runs'] if r['id']==claim['run_id'])['usage_state'],'unknown')

    async def test_silent_controller_old_tick_and_explicit_failure_recovery_remain_distinct(self):
        store=self.memory.h2_runtime.store
        start=datetime(2026,11,8,12,tzinfo=timezone.utc)
        with patch.object(store,'now',return_value=start):
            initial=await self.get('/control')
            epoch=initial['restore_epoch']
            prior=next((t['seq'] for t in initial['ticks'] if t['runner']=='controller'),0)
            tick={'request_id':'acceptance-first-poll','expected_seq':prior,'expected_epoch':epoch,
                  'evidence':['synthetic-completed-poll']}
            completed=await self.save('/control/ticks',tick,'controller-fixture-token')
        with patch.object(store,'now',return_value=start+timedelta(minutes=10)):
            replay=await self.save('/control/ticks',tick,'controller-fixture-token')
            self.assertEqual(replay,completed)
            quiet=await self.get('/control')
            self.assertEqual(next(t for t in quiet['ticks'] if t['runner']=='controller')['at'],start.isoformat())
            self.assertEqual(quiet['observed_at'],(start+timedelta(minutes=10)).isoformat())
            # Time passage alone currently creates no automatic diagnosis.
            self.assertFalse(any(f['key']=='acceptance-silence' for f in quiet['failures']))
            failure=dict(kind='runner_stale',target='controller',key='acceptance-silence',expected_seq=0,
                expected_epoch=epoch,state='open',evidence=['synthetic-outside-staleness-observation'])
            opened=await self.save('/control/failures',failure,'supervisor-fixture-token')
            # A new successful poll does not erase an unresolved failure.
            await self.save('/control/ticks',{**tick,'request_id':'acceptance-resumed-poll',
                'expected_seq':completed['seq']},'controller-fixture-token')
            visible=await self.get('/control')
            self.assertEqual(next(f for f in visible['failures'] if f['key']=='acceptance-silence')['state'],'open')
            recovered=await self.save('/control/failures',
                {**failure,'expected_seq':opened['seq'],'state':'recovered','evidence':['synthetic-outside-recovery-check']},
                'supervisor-fixture-token')
            self.assertEqual(recovered['state'],'recovered')
            self.assertEqual(recovered['actor'],'supervisor')
            after=await self.get('/control')
            self.assertEqual(next(f for f in after['failures'] if f['key']=='acceptance-silence')['state'],'recovered')


if __name__=='__main__':unittest.main()
