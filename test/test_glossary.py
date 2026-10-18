"""Glosssary behavior against committed real files, with synthetic content."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).parents[1] / 'mcp/memory'
def module(name):
    path = ROOT / (name + '.py')
    if not path.exists():
        raise AssertionError('Missing glossary implementation: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

class GlossaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = module('commons_files').CommonsStore(Path(self.temp.name).resolve() / 'commons')
        self.glossary = module('glossary').Glossary(self.store)

    def distinction(self, **changes):
        data = dict(author='kimi3', title='Synthetic fixture: signal / evidence',
                    distinction='A signal suggests; evidence discriminates between explanations.',
                    discriminating_example='An alarm suggests trouble; a checked sensor separates failure from noise.',
                    unresolved_edge_case='A sensor can itself be faulty.',
                    source_refs=['fixture:source'], request_id='first')
        data.update(changes)
        return self.glossary.create(**data)

    def test_sourced_distinction_can_be_retrieved_and_retried(self):
        receipt = self.distinction()
        read = self.glossary.read(receipt['entry_id'])
        self.assertEqual(read['author'], 'kimi3')
        self.assertIn('sensor', read['data']['discriminating_example'])
        self.assertTrue(read['created_at'])
        self.assertTrue(self.distinction()['replayed'])
        self.assertEqual(len(self.glossary.list()['entries']), 1)
        self.assertEqual(self.glossary.list()['entries'][0]['title'], read['data']['title'])

    def test_application_and_refinement_preserve_the_original_and_authors(self):
        original = self.distinction()['entry_id']
        snapshot = self.glossary.read(original)
        applied = self.glossary.apply(author='mavis', entry_id=original,
            situation='Synthetic fixture: an alarm sounded.', how_used='Checked a second sensor before acting.',
            assessment='unclear', source_refs=['fixture:later-use'], request_id='usage')
        revised = self.glossary.refine(author='kimi3', entry_id=original,
            title='Synthetic revised distinction', distinction='Evidence is relative to competing explanations.',
            discriminating_example='Two independent sensors can discriminate noise from a real fault.',
            unresolved_edge_case='Common-cause faults can defeat independence.',
            source_refs=['fixture:refinement'], request_id='refinement')
        self.assertEqual(self.glossary.read(original), snapshot)
        self.assertEqual(self.glossary.read(applied['entry_id'])['author'], 'mavis')
        self.assertEqual(self.glossary.read(applied['entry_id'])['links'], [original])
        self.assertEqual(self.glossary.read(revised['entry_id'])['links'], [original])
        self.assertEqual(self.glossary.read(revised['entry_id'])['data']['record_type'], 'refinement')

    def test_blank_fields_missing_sources_and_changed_retries_are_rejected(self):
        for field in ['title','distinction','discriminating_example','unresolved_edge_case']:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.distinction(**{field:'  '})
        with self.assertRaises(ValueError): self.distinction(source_refs=[])
        self.distinction()
        with self.assertRaises(ValueError): self.distinction(title='Changed after commit')

    def test_cross_project_and_application_targets_are_rejected(self):
        other = self.store.create(author='glm53', collection='corpus', kind='case', content='Synthetic case',
                                  source_refs=['fixture'], links=[], request_id='other')['entry_id']
        arguments = dict(author='mavis', entry_id=other, situation='Synthetic', how_used='Test',
                         assessment='yes', source_refs=['fixture'], request_id='bad')
        with self.assertRaises(ValueError): self.glossary.apply(**arguments)
        arguments['entry_id'] = self.distinction()['entry_id']
        applied = self.glossary.apply(**arguments)['entry_id']
        with self.assertRaises(ValueError): self.glossary.apply(**{**arguments,'entry_id':applied,'request_id':'bad-2'})
        with self.assertRaises(ValueError): self.glossary.apply(**{**arguments,'assessment':'certainly'})

    def test_legacy_entries_are_not_silently_claimed_as_valid_distinctions(self):
        self.store.create(author='codex', collection='glossary', kind='distinction', content='Legacy plain text',
                          source_refs=['fixture'], links=[], request_id='legacy')
        self.assertEqual(self.glossary.list()['entries'], [])
        self.assertEqual(self.glossary.list()['unstructured_entries'], 1)

    def test_generic_envelopes_cannot_claim_invalid_parent_relationships(self):
        original = self.distinction()['entry_id']
        application = self.glossary.apply(author='mavis', entry_id=original, situation='Fixture',
            how_used='Fixture use', assessment='unclear', source_refs=['fixture'], request_id='valid-use')['entry_id']
        corpus = self.store.create(author='glm53', collection='corpus', kind='case', content='Fixture',
            source_refs=['fixture'], links=[], request_id='corpus')['entry_id']
        fields = self.glossary.read(original)['data']
        for index, parent in enumerate([corpus, application]):
            data = {**fields, 'record_type':'refinement'}
            bad = self.store.create(author='kimi3', collection='glossary', kind='correction',
                content=json.dumps(data), source_refs=['fixture'], links=[parent], request_id=f'invalid-{index}')['entry_id']
            with self.assertRaises(ValueError): self.glossary.read(bad)
            self.assertNotIn(bad, [entry['entry_id'] for entry in self.glossary.list()['entries']])

    def test_full_structured_entry_survives_underlying_read_pagination(self):
        created = self.distinction(discriminating_example='界'*4000)
        self.assertEqual(len(self.glossary.read(created['entry_id'])['data']['discriminating_example']), 4000)

if __name__ == '__main__': unittest.main()
