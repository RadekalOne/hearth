from test.test_glossary_api import GlossaryAPITests
from datetime import date

class JournalAPITests(GlossaryAPITests):
    async def test_self_correction_route_preserves_original(self):
        headers={'Authorization':'Bearer codex-test-token'}
        created=await self.client.post('/api/commons/journal/predictions',headers=headers,json=self.journal_payload())
        parent=created.json()['entry_id']
        data=dict(entry_id=parent,status='superseded',explanation='Later evidence changed the premise.',source_refs=['fixture:correction'],request_id='api-correction')
        correction=await self.client.post('/api/commons/journal/corrections',headers=headers,json=data)
        self.assertEqual(correction.status_code,200,correction.text)
        read=await self.client.get('/api/commons/journal/entries/'+correction.json()['entry_id'],headers=headers)
        self.assertEqual(read.json()['data']['record_type'],'correction')
        original=await self.client.get('/api/commons/journal/entries/'+parent,headers=headers)
        self.assertEqual(original.json()['data']['record_type'],'prediction')
    def journal_payload(self):
        return dict(title='Fixture',decision='Check twice',reasoning='One reading can be noise.',prediction='They will disagree.',falsifier='They agree on an observed fault.',confidence='medium',check_date=date.today().isoformat(),tradeoffs='',source_refs=['fixture:before'],request_id='journal-api')
    async def test_journal_roundtrip_identity_and_independent_outcome(self):
        headers={'Authorization':'Bearer codex-test-token'}
        response=await self.client.post('/api/commons/journal/predictions',headers=headers,json=self.journal_payload())
        self.assertEqual(response.status_code,200,response.text);entry=response.json()['entry_id']
        read=await self.client.get('/api/commons/journal/entries/'+entry,headers=headers)
        self.assertEqual(read.json()['author'],'codex')
        outcome=dict(entry_id=entry,observed_result='They agreed.',comparison='Prediction failed.',verdict='falsified',cause_unknown=True,cause='',source_refs=['fixture:after'],request_id='journal-result')
        denied=await self.client.post('/api/commons/journal/outcomes',headers=headers,json=outcome)
        self.assertEqual(denied.status_code,400)
        self.assertEqual((await self.client.get('/api/commons/journal',headers=headers)).status_code,200)
        spoof=await self.client.post('/api/commons/journal/predictions',headers=headers,json={**self.journal_payload(),'author':'mavis'})
        self.assertEqual(spoof.status_code,400)
    async def test_journal_uses_existing_auth_enrollment_origin_and_reviewer_denial(self):
        from unittest.mock import patch
        headers={'Authorization':'Bearer codex-test-token'}
        self.assertEqual((await self.client.get('/api/commons/journal')).status_code,401)
        with patch.object(self.memory,'COMMONS_ENABLED',False):self.assertEqual((await self.client.get('/api/commons/journal',headers=headers)).status_code,403)
        denied=await self.client.post('/api/commons/journal/predictions',headers={**headers,'Origin':'https://evil.test'},json=self.journal_payload())
        self.assertEqual(denied.status_code,403)
        self.assertFalse(self.memory._reviewers.rest_allowed('GET','/api/commons/journal'))
        self.assertFalse(self.memory._reviewers.mcp_allowed('tools/call',{'name':'journal_prediction_create'}))
