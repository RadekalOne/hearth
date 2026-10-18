import importlib.util
from pathlib import Path
import tempfile
import unittest
from datetime import date,timedelta

ROOT=Path(__file__).parents[1]/'mcp/memory'
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=module('commons_files').CommonsStore(Path(self.temp.name).resolve()/'commons')
        self.journal=module('journal').Journal(self.store)
    def prediction(self,**changes):
        args=dict(author='mavis',title='Synthetic test',decision='Use a second sensor',reasoning='Independent readings may separate noise.',
            prediction='The second sensor will disagree.',falsifier='Both agree on a verified fault.',confidence='medium',
            check_date=(date.today()+timedelta(days=2)).isoformat(),tradeoffs='',source_refs=['fixture:before'],request_id='prediction')
        return self.journal.predict(**{**args,**changes})
    def outcome(self,parent,**changes):
        args=dict(author='glm53',entry_id=parent,observed_result='Both sensors agreed.',comparison='Prediction failed.',verdict='falsified',cause_unknown=True,cause='',source_refs=['fixture:after'],request_id='outcome')
        return self.journal.outcome(**{**args,**changes})
    def test_separate_outcome_preserves_original_authorship_and_failed_result(self):
        parent=self.prediction()['entry_id'];before=self.journal.read(parent)
        result=self.outcome(parent);after=self.journal.read(result['entry_id'])
        self.assertEqual(self.journal.read(parent),before)
        self.assertEqual(after['author'],'glm53');self.assertEqual(after['links'],[parent])
        self.assertEqual(after['data']['verdict'],'falsified');self.assertTrue(after['data']['cause_unknown'])
        self.assertGreaterEqual(after['created_at'],before['created_at'])
        self.assertTrue(self.outcome(parent)['replayed']);self.assertTrue(self.prediction()['replayed'])
        self.assertEqual(len(self.journal.list()['entries']),2)
    def test_self_review_wrong_parent_and_invalid_fields_are_rejected(self):
        parent=self.prediction()['entry_id']
        for change in [dict(author='mavis'),dict(author='@mavis:hearth.radekal.me'),dict(cause_unknown=True,cause='An invented cause'),dict(cause_unknown=False,cause=''),dict(cause_unknown='yes'),dict(verdict='certain')]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.outcome(parent,**change)
        review=self.outcome(parent)['entry_id']
        with self.assertRaises(ValueError):self.outcome(review,request_id='other')
        for change in [dict(reasoning=' '),dict(falsifier=''),dict(confidence='certain'),dict(check_date='not a date')]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.prediction(**change)
    def test_known_cause_pagination_and_conflicting_retry(self):
        parent=self.prediction(reasoning='界'*4000)['entry_id']
        self.assertEqual(len(self.journal.read(parent)['data']['reasoning']),4000)
        self.outcome(parent,cause_unknown=False,cause='Second observation verified the fault.')
        with self.assertRaises(ValueError):self.outcome(parent,observed_result='Changed')

if __name__=='__main__':unittest.main()
