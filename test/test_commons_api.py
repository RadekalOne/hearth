"""Commons HTTP/MCP identity and default-deny integration contracts."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from test import test_dashboard_auth as auth


class CommonsAPITests(auth.DashboardAuthTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.assertTrue(hasattr(self.memory, 'commons_store'), 'Commons service integration is missing')
        self.records = tempfile.TemporaryDirectory()
        self.root = Path(self.records.name) / 'files'
        self.patches = [
            patch.object(self.memory, 'commons_store', self.memory._commons_module.CommonsStore(self.root)),
            patch.object(self.memory, 'COMMONS_ENABLED', True),
            patch.object(self.memory, 'COMMONS_PARTICIPANTS', {'codex', 'kimi3', 'glm53', 'hy4', 'mavis'}),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in getattr(self, 'patches', [])[::-1]:
            item.stop()
        if hasattr(self, 'records'):
            self.records.cleanup()
        await super().asyncTearDown()

    @staticmethod
    def payload():
        return dict(collection='glossary', kind='distinction', content='Chore / standard',
                    source_refs=['event:real-source'], links=[], request_id='api-first')

    async def test_author_is_authenticated_and_model_fields_cannot_spoof_it(self):
        header = {'Authorization': 'Bearer codex-test-token'}
        bad = await self.client.post('/api/commons/entries', headers=header,
                                     json={**self.payload(), 'author': 'rad'})
        self.assertEqual(bad.status_code, 400, bad.text)
        created = await self.client.post('/api/commons/entries', headers=header, json=self.payload())
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()['author'], 'codex')
        repeated = await self.client.post('/api/commons/entries', headers=header, json=self.payload())
        self.assertTrue(repeated.json()['replayed'])
        entry_id = created.json()['entry_id']
        record = await self.client.get('/api/commons/entries/' + entry_id, headers=header)
        self.assertEqual(record.json()['author'], 'codex')
        listing = await self.client.get('/api/commons/entries?collection=glossary', headers=header)
        self.assertEqual([v['entry_id'] for v in listing.json()['entries']], [entry_id])

    async def test_disabled_unlisted_and_cross_site_mutations_are_denied(self):
        header = {'Authorization': 'Bearer codex-test-token'}
        with patch.object(self.memory, 'COMMONS_ENABLED', False):
            result = await self.client.post('/api/commons/entries', headers=header, json=self.payload())
            self.assertEqual(result.status_code, 403, result.text)
        self.assertFalse(self.root.exists())
        with patch.object(self.memory, 'COMMONS_PARTICIPANTS', set()):
            result = await self.client.get('/api/commons/entries?collection=glossary', headers=header)
            self.assertEqual(result.status_code, 403, result.text)
        result = await self.client.post('/api/commons/entries',
                                        headers={**header, 'Origin': 'https://evil.test'}, json=self.payload())
        self.assertEqual(result.status_code, 403, result.text)
        result = await self.client.get('/api/commons/entries?collection=glossary')
        self.assertEqual(result.status_code, 401, result.text)

    async def test_direct_mcp_functions_preserve_identity_and_reviewer_denial(self):
        principal = self.memory.CURRENT_PRINCIPAL.set('codex')
        try:
            result = self.memory.commons_entry_create(**self.payload())
            self.assertEqual(result['author'], 'codex')
            self.assertEqual(self.memory.commons_files_read(result['entry_id'])['content'], 'Chore / standard')
            self.assertEqual(len(self.memory.commons_files_list('glossary')['entries']), 1)
            reviewer = self.memory.CURRENT_AUTH.set(self.memory._reviewers.AuthContext(
                'reviewer:fixture', 'reviewer', 'reviewer_bearer', 'full', 1))
            try:
                for call in [lambda: self.memory.commons_files_list('glossary'),
                             lambda: self.memory.commons_files_read(result['entry_id']),
                             lambda: self.memory.commons_entry_create(**self.payload())]:
                    with self.assertRaises(PermissionError):
                        call()
            finally:
                self.memory.CURRENT_AUTH.reset(reviewer)
            for forbidden in ['anonymous', 'admin', 'unlisted', '@codex:evil.test']:
                token = self.memory.CURRENT_PRINCIPAL.set(forbidden)
                try:
                    with self.assertRaises(PermissionError):
                        self.memory.commons_files_list('glossary')
                finally:
                    self.memory.CURRENT_PRINCIPAL.reset(token)
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(principal)

    async def test_bad_payload_and_missing_record_return_bounded_errors(self):
        header = {'Authorization': 'Bearer codex-test-token'}
        for value in [[], {}, {**self.payload(), 'content': 'é' * 32769}]:
            result = await self.client.post('/api/commons/entries', headers=header, json=value)
            self.assertEqual(result.status_code, 400, result.text)
        missing = await self.client.get('/api/commons/entries/entry_' + 'a' * 32, headers=header)
        self.assertEqual(missing.status_code, 400)

    async def test_valid_escaped_text_fits_http_limit_but_excessive_body_does_not(self):
        header = {'Authorization': 'Bearer codex-test-token'}
        value = {**self.payload(), 'content': 'x' + '\x00' * 65535}
        created = await self.client.post('/api/commons/entries', headers=header, json=value)
        self.assertEqual(created.status_code, 200, created.text)
        result = await self.client.get('/api/commons/entries/' + created.json()['entry_id'], headers=header)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['content'], 'x' + '\x00' * 3999)
        oversized = await self.client.post('/api/commons/entries', headers=header,
                                           content=b' ' * 524289)
        self.assertEqual(oversized.status_code, 413)
