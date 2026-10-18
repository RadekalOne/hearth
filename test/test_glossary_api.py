"""Typed glossary endpoints retain existing Commons auth and origin limits."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from test import test_dashboard_auth as auth

class GlossaryAPITests(auth.DashboardAuthTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.records = tempfile.TemporaryDirectory()
        self.patches = [patch.object(self.memory,'commons_store',self.memory._commons_module.CommonsStore(Path(self.records.name).resolve()/'commons')),
                        patch.object(self.memory,'COMMONS_ENABLED',True),
                        patch.object(self.memory,'COMMONS_PARTICIPANTS',{'codex'})]
        for item in self.patches: item.start()

    async def asyncTearDown(self):
        for item in self.patches[::-1]:item.stop()
        self.records.cleanup()
        await super().asyncTearDown()

    def payload(self):
        return dict(title='Synthetic fixture',distinction='Different explanations need discriminating evidence.',
                    discriminating_example='A second checked sensor separates noise from failure.',
                    unresolved_edge_case='The sensors may share a failure.',source_refs=['fixture:source'],request_id='api-glossary')

    async def test_create_read_list_and_spoof_rejection(self):
        headers={'Authorization':'Bearer codex-test-token'}
        response=await self.client.post('/api/commons/glossary/distinctions',headers=headers,json=self.payload())
        self.assertEqual(response.status_code,200,response.text)
        entry_id=response.json()['entry_id']
        read=await self.client.get('/api/commons/glossary/entries/'+entry_id,headers=headers)
        self.assertEqual(read.json()['author'],'codex')
        self.assertEqual(read.json()['data']['title'],'Synthetic fixture')
        listing=await self.client.get('/api/commons/glossary',headers=headers)
        self.assertTrue(listing.json()['can_create'])
        self.assertEqual(listing.json()['entries'][0]['entry_id'],entry_id)
        spoof=await self.client.post('/api/commons/glossary/distinctions',headers=headers,json={**self.payload(),'author':'kimi3'})
        self.assertEqual(spoof.status_code,400)

    async def test_default_deny_and_same_origin_for_all_writes(self):
        headers={'Authorization':'Bearer codex-test-token'}
        for enabled,participants in [(False,{'codex'}),(True,set())]:
            with patch.object(self.memory,'COMMONS_ENABLED',enabled),patch.object(self.memory,'COMMONS_PARTICIPANTS',participants):
                response=await self.client.get('/api/commons/glossary',headers=headers)
                self.assertEqual(response.status_code,403,response.text)
        response=await self.client.get('/api/commons/glossary')
        self.assertEqual(response.status_code,401)
        for route in ['distinctions','refinements','applications']:
            response=await self.client.post('/api/commons/glossary/'+route,headers={**headers,'Origin':'https://evil.test'},json=self.payload())
            self.assertEqual(response.status_code,403,response.text)

    async def test_direct_mcp_and_reviewer_deny(self):
        principal=self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            created=self.memory.glossary_distinction_create(**self.payload())
            self.assertEqual(self.memory.glossary_entry_read(created['entry_id'])['author'],'codex')
            reviewer=self.memory.CURRENT_AUTH.set(self.memory._reviewers.AuthContext('reviewer:fixture','reviewer','reviewer_bearer','full',1))
            try:
                for call in [lambda:self.memory.glossary_list(),lambda:self.memory.glossary_entry_read(created['entry_id']),lambda:self.memory.glossary_distinction_create(**self.payload())]:
                    with self.assertRaises(PermissionError):call()
            finally:self.memory.CURRENT_AUTH.reset(reviewer)
        finally:self.memory.CURRENT_PRINCIPAL.reset(principal)

    async def test_bounded_bad_json_and_structural_fields(self):
        headers={'Authorization':'Bearer codex-test-token'}
        invalid=await self.client.post('/api/commons/glossary/distinctions',headers=headers,json={**self.payload(),'unresolved_edge_case':' '})
        self.assertEqual(invalid.status_code,400,invalid.text)
        invalid=await self.client.post('/api/commons/glossary/distinctions',headers=headers,content=b'not json')
        self.assertEqual(invalid.status_code,400)
        oversized=await self.client.post('/api/commons/glossary/distinctions',headers=headers,content=b' '*524289)
        self.assertEqual(oversized.status_code,413)
