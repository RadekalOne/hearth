import json,unittest
from pathlib import Path
class EntitlementCloseout(unittest.TestCase):
    def test_synthetic_memory_closeout(self):
        result=json.loads(Path('result.json').read_text())
        self.assertIsInstance(result['text'],str)
        self.assertLessEqual(len(result['text'].encode()),16384)
        self.assertIn(result['expected'],result['text'])
