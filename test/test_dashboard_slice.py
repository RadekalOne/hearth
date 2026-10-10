"""Dashboard projections exercise real inputs without a live database or credentials."""
import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).parents[1] / 'mcp/memory/dashboard.py'
spec = importlib.util.spec_from_file_location('dashboard_slice', path) if path.exists() else None
dashboard = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(dashboard)


class DashboardSliceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(dashboard, 'dashboard projections are not implemented')

    def test_exact_cadence_boundaries(self):
        self.assertEqual([dashboard.watcher_state(v, 60, {}) for v in (90, 90.01, 180, 180.01)],
                         ['ok', 'late', 'late', 'stalled'])

    def test_failed_receipt_wins_even_with_recent_activity(self):
        self.assertEqual(dashboard.watcher_state(0, 60, {'process_exit': 1}), 'failed')
        self.assertEqual(dashboard.watcher_state(0, 60, {'closeout_verified': False}), 'failed')
        self.assertEqual(dashboard.watcher_state(0, None, {'process_exit': 1}), 'failed')

    def test_event_driven_and_unknown(self):
        self.assertEqual(dashboard.watcher_state(9000, None, {}), 'on-demand')
        self.assertEqual(dashboard.watcher_state(None, 60, {}), 'unknown')
        self.assertEqual(dashboard.watcher_state(-1, 60, {}), 'unknown')

    def test_receipt_accepts_structured_runner_fields_only(self):
        self.assertEqual(dashboard.receipt('{"process_exit":1,"closeout_verified":false,"secret":"hidden"}'),
                         {'process_exit': 1, 'closeout_verified': False})
        self.assertEqual(dashboard.receipt('process_exit=1 closeout_verified=false'),
                         {'process_exit': 1, 'closeout_verified': False})
        self.assertEqual(dashboard.receipt('[FAILED] heartbeat'), {})

    def test_receipt_rejects_arbitrary_field_payloads(self):
        self.assertEqual(dashboard.receipt('{"process_exit":{"secret":"private"},"closeout_verified":"private"}'), {})

    def test_work_queue_claim_and_running_are_distinct(self):
        board = {'tasks': [{'id': 'task_a', 'state': 'ready', 'title': 'A', 'updated_at': '2026-10-09T00:00:00Z'},
                           {'id': 'task_b', 'state': 'running', 'title': 'B', 'updated_at': '2026-10-09T01:00:00Z'}]}
        relays = [{'relay_id': 'relay_a', 'state': 'claimed', 'updated_at': '2026-10-09T01:00:00Z'}]
        result = dashboard.work_items(board, relays, 1791507600)
        self.assertEqual([i['state'] for i in result], ['queued', 'claimed', 'claimed'])
        self.assertEqual(result[0]['age_minutes'], 60)
        self.assertEqual(result[0]['source_refs'], ['task_a'])

    def test_unverified_relay_identity_is_not_folded(self):
        board = {'tasks': [{'id': 'task_a', 'state': 'ready', 'title': 'Shared title'}]}
        result = dashboard.work_items(board, [{'relay_id': 'relay_a', 'state': 'queued', 'request': 'Shared title'}], 0)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0]['age_minutes'])

    def test_work_age_uses_transition_not_comment_timestamp(self):
        board = {'tasks': [{'id': 'task_a', 'state': 'ready', 'created_at': '2026-10-09T00:00:00Z',
                           'updated_at': '2026-10-09T01:00:00Z'}],
                 'activity': [{'task_id': 'task_a', 'kind': 'ready', 'at': '2026-10-09T00:00:00Z'}]}
        result = dashboard.work_items(board, [], 1791507600)
        self.assertEqual(result[0]['age_minutes'], 60)

    def test_health_knowledge_default_and_pair_deduplication(self):
        rows = [('drawer_a', {'record_class': 'knowledge', 'wing': 'h', 'room': 'r'}),
                ('drawer_b', {'record_class': 'knowledge', 'wing': 'h', 'room': 'r', 'superseded_by': 'drawer_a'}),
                ('drawer_c', {'record_class': 'diary', 'wing': 'h', 'room': 'r'})]
        result = dashboard.memory_health(rows, ['drawer_a', 'drawer_b'], [[1, 0], [1, 0]], .18)
        self.assertEqual(result['knowledge_count'], 2)
        self.assertAlmostEqual(result['noise_ratio'], 1 / 3)
        self.assertEqual(result['superseded_count'], 1)
        self.assertEqual(result['near_duplicate_pair_count'], 1)

    def test_unavailable_embeddings_are_not_zero_duplicates(self):
        result = dashboard.memory_health([('drawer_a', {'record_class': 'knowledge'})], [], None, .18)
        self.assertIsNone(result['near_duplicate_pair_count'])
        self.assertFalse(result['duplicate_coverage']['complete'])

    def test_empty_health(self):
        result = dashboard.memory_health([], [], [], .18)
        self.assertEqual(result['noise_ratio'], 0)
        self.assertEqual(result['near_duplicate_pair_count'], 0)
