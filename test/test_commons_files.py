"""Behavioral contracts for the file-backed Commons contribution store."""
import importlib.util
import json
import multiprocessing
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).parents[1] / 'mcp/memory/commons_files.py'


def load_store():
    spec = importlib.util.spec_from_file_location('commons_store_test', MODULE)
    if spec is None or spec.loader is None or not MODULE.exists():
        raise AssertionError('Commons file store has not been implemented')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contribute_process(root):
    return load_store().CommonsStore(root).create(**contribution())['entry_id']


def contribution(**overrides):
    return dict(author='kimi3', collection='glossary', kind='distinction',
                content='Distinction: chore / standard\nExample: knife / house\nOpen edge: credit',
                source_refs=['event:commons-example'], links=[], request_id='first', **overrides)


class CommonsFilesTests(unittest.TestCase):
    def history_count(self):
        if not (self.root / 'history.git').exists():
            return 0
        result = subprocess.run(['git', '--git-dir', str(self.root / 'history.git'),
                                 'rev-list', '--count', '--all'], capture_output=True, text=True, check=True)
        return int(result.stdout.strip() or '0')
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'commons'
        self.module = load_store()
        self.store = self.module.CommonsStore(self.root)

    def create(self, **overrides):
        args = contribution()
        args.update(overrides)
        return self.store.create(**args)

    def test_create_retry_and_conflicting_retry(self):
        first = self.create()
        second = self.create()
        self.assertEqual(first['entry_id'], second['entry_id'])
        self.assertEqual(first['author'], 'kimi3')
        self.assertRegex(first['created_at'], r'^\d{4}-\d\d-\d\dT.*\+00:00$')
        self.assertFalse(first['replayed'])
        self.assertTrue(second['replayed'])
        self.assertEqual(len(self.store.list('glossary')['entries']), 1)
        with self.assertRaisesRegex(ValueError, 'different payload'):
            self.create(content='changed original')
        self.assertEqual(self.store.read(first['entry_id'])['content'], contribution()['content'])

    def test_linked_result_keeps_original_and_trusted_authors_separate(self):
        original = self.create(collection='journal', kind='prediction')
        result = self.create(author='mavis', collection='journal', kind='outcome',
                             request_id='review', content='Prediction failed; cause unknown.',
                             links=[original['entry_id']])
        self.assertEqual(self.store.read(result['entry_id'])['links'], [original['entry_id']])
        self.assertEqual(self.store.read(original['entry_id'])['content'], contribution()['content'])
        self.assertNotEqual(original['entry_id'], result['entry_id'])

    def test_concurrent_threads_publish_once(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            receipts = list(pool.map(lambda _: self.create(), range(12)))
        self.assertEqual(len({r['entry_id'] for r in receipts}), 1)
        self.assertEqual(sum(not r['replayed'] for r in receipts), 1)
        self.assertEqual(self.history_count(), 1)

    def test_concurrent_processes_publish_once(self):
        with multiprocessing.get_context('spawn').Pool(3) as pool:
            ids = pool.map(contribute_process, [str(self.root)] * 6)
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.history_count(), 1)

    def test_failed_commit_is_not_visible_and_retry_recovers(self):
        with patch.object(self.store, '_publish', side_effect=RuntimeError('git unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'git unavailable'):
                self.create()
        self.assertEqual(self.store.list('glossary')['entries'], [])
        receipt = self.create()
        self.assertEqual(self.store.read(receipt['entry_id'])['content'], contribution()['content'])
        self.assertEqual(self.history_count(), 1)

    def test_failed_write_does_not_leave_a_partially_created_final_record(self):
        with patch.object(self.module.os, 'fsync', side_effect=OSError('disk flush failed')):
            with self.assertRaises(OSError):
                self.create()
        self.assertEqual(list(self.root.glob('files/*/*.json')), [])
        self.assertEqual(self.create()['author'], 'kimi3')

    def test_uncommitted_retry_cannot_change_collection(self):
        with patch.object(self.store, '_publish', side_effect=RuntimeError('git unavailable')):
            with self.assertRaises(RuntimeError):
                self.create()
        with self.assertRaisesRegex(ValueError, 'different payload'):
            self.create(collection='journal', kind='prediction')
        self.assertEqual(self.history_count(), 0)

    def test_pagination_uses_one_snapshot_and_read_is_bounded(self):
        ids = {self.create(request_id=f'item-{i}')['entry_id'] for i in range(27)}
        page = self.store.list('glossary')
        self.assertEqual(len(page['entries']), 25)
        self.assertIsNotNone(page['next_cursor'])
        self.create(request_id='after-snapshot')
        last = self.store.list('glossary', cursor=page['next_cursor'])
        self.assertEqual({r['entry_id'] for r in page['entries'] + last['entries']}, ids)
        self.assertIsNone(last['next_cursor'])
        long = self.create(request_id='long', content='a' * 4000 + 'end')
        first = self.store.read(long['entry_id'])
        self.assertEqual(first['content'], 'a' * 4000)
        self.assertEqual(first['next_offset'], 4000)
        self.assertEqual(self.store.read(long['entry_id'], 4000)['content'], 'end')

    def test_invalid_inputs_and_foreign_paths_are_rejected(self):
        for fields in [dict(collection='../secrets'), dict(kind='outcome'),
                       dict(author='../rad'), dict(request_id='../x'), dict(content=''),
                       dict(content='é' * 32769), dict(source_refs=[]),
                       dict(source_refs=[' ']), dict(links=['../../outside'])]:
            with self.subTest(fields=str(fields)[:120]):
                with self.assertRaises(ValueError):
                    self.create(**fields)
        self.assertFalse(self.root.exists(), 'validation must precede store initialization')
        for value in ['../../outside', 'HEAD:config', 'entry_' + 'f' * 32]:
            with self.assertRaises(ValueError):
                self.store.read(value)
        with self.assertRaises(ValueError):
            self.store.list('glossary', cursor='HEAD:../../outside')
        record = self.create()
        for offset in [-1, True, '0', 1.5, 99999999]:
            with self.assertRaises(ValueError):
                self.store.read(record['entry_id'], offset)

    def test_missing_link_and_collection_kind_mismatch_do_not_publish(self):
        with self.assertRaisesRegex(ValueError, 'linked entry'):
            self.create(links=['entry_' + 'a' * 32])
        self.assertEqual(self.history_count(), 0)
        with self.assertRaises(ValueError):
            self.create(collection='journal', kind='distinction')

    def test_existing_symlink_is_never_followed(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        try:
            self.root.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation requires Windows privilege')
        with self.assertRaisesRegex(ValueError, 'link'):
            self.create()
        self.assertEqual(list(outside.iterdir()), [])

    def test_files_and_reflog_record_the_real_commit(self):
        receipt = self.create()
        files = list((self.root / 'files/glossary').glob('*.json'))
        self.assertEqual(len(files), 1)
        record = json.loads(files[0].read_text(encoding='utf-8'))
        self.assertEqual(record['author'], 'kimi3')
        self.assertEqual(record['entry_id'], receipt['entry_id'])
        reflog = subprocess.run(['git', '--git-dir', str(self.root / 'history.git'),
                                 'reflog', 'show', 'HEAD'], capture_output=True, text=True, check=True)
        self.assertIn('Create glossary/distinction', reflog.stdout)
        files[0].write_text('uncommitted corruption', encoding='utf-8')
        self.assertEqual(self.store.read(receipt['entry_id'])['content'], contribution()['content'])


if __name__ == '__main__':
    unittest.main()
