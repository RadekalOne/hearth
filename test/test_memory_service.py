"""Phase 1 behavioral tests for the Hearth Memory service.

Run with:
    python -m unittest test/test_memory_service.py
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


class MemoryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.TemporaryDirectory(prefix="hearth-memory-test-")
        os.environ["HEARTH_DATA_DIR"] = cls.data_dir.name
        os.environ.pop("HEARTH_MEMORY_ADMIN_TOKEN", None)
        app_path = Path(__file__).parents[1] / "mcp" / "memory" / "app.py"
        spec = importlib.util.spec_from_file_location("hearth_memory_test_app", app_path)
        cls.memory = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.memory)

    @classmethod
    def tearDownClass(cls):
        cls.memory.chroma._system.stop()
        cls.memory.chroma.clear_system_cache()
        cls.data_dir.cleanup()

    def setUp(self):
        for collection in (self.memory.drawers, self.memory.checkpoints):
            got = collection.get()
            if got["ids"]:
                collection.delete(ids=got["ids"])
        self.principal_token = self.memory.CURRENT_PRINCIPAL.set("codex")

    def tearDown(self):
        self.memory.CURRENT_PRINCIPAL.reset(self.principal_token)

    def test_authenticated_principal_controls_author(self):
        author, surface = self.memory._author("codex @ laptop")
        self.assertEqual(author, "codex")
        self.assertEqual(surface, "codex @ laptop")

    def test_agent_cannot_write_another_agents_continuity(self):
        with self.assertRaisesRegex(ValueError, "cannot write continuity"):
            self.memory.write_checkpoint("claude", "laptop", "heartbeat", "quiet")

    def test_checkpoint_replaces_instead_of_growing(self):
        first = self.memory.write_checkpoint("codex", "laptop", "heartbeat", "checked event A")
        second = self.memory.write_checkpoint("codex", "laptop", "heartbeat", "checked event B")
        self.assertEqual(first["checkpoint_id"], second["checkpoint_id"])
        self.assertFalse(first["replaced_previous"])
        self.assertTrue(second["replaced_previous"])
        self.assertEqual(self.memory.checkpoints.count(), 1)
        read = self.memory.read_checkpoints("codex", "laptop", "heartbeat")
        self.assertEqual(read["entries"][0]["content"], "checked event B")

    def test_default_search_excludes_diaries_and_archives(self):
        phrase = "Hearth bootstrap protocol durable memory retrieval"
        self.memory.add_drawer("hearth", "decisions", phrase + " current", "codex", "")
        self.memory.add_drawer("agent_codex", "diary", phrase + " diary", "codex", "")
        self.memory.add_drawer("hearth", "archive-agent-logs", phrase + " archive", "import", "")

        current = self.memory.search_drawers(
            phrase, None, None, 10, 1.5,
            include_diaries=False, include_archives=False,
        )
        self.assertTrue(current["results"])
        self.assertEqual({row["record_class"] for row in current["results"]}, {"knowledge"})

        history = self.memory.search_drawers(
            phrase, None, None, 10, 1.5,
            include_diaries=True, include_archives=True,
        )
        self.assertEqual(
            {row["record_class"] for row in history["results"]},
            {"knowledge", "diary", "archive"},
        )

    def test_legacy_metadata_is_enriched_without_losing_provenance(self):
        self.memory.drawers.add(
            ids=["legacy-drawer"],
            documents=["A preserved legacy memory"],
            metadatas=[{
                "wing": "hearth",
                "room": "archive-agent-logs",
                "added_by": "import",
                "source": "matrix-event-1",
                "created_at": "2026-01-01T00:00:00+00:00",
                "imported": True,
            }],
        )
        migration = self.memory.migrate_legacy_metadata()
        self.assertEqual(migration["updated"], 1)
        got = self.memory.drawers.get(ids=["legacy-drawer"], include=["metadatas"])
        meta = got["metadatas"][0]
        self.assertEqual(meta["record_class"], "archive")
        self.assertEqual(meta["source"], "matrix-event-1")
        self.assertEqual(meta["created_at"], "2026-01-01T00:00:00+00:00")

    def test_status_exposes_nested_taxonomy(self):
        self.memory.add_drawer("hearth", "lessons", "A durable lesson", "codex", "")
        snapshot = self.memory.status()
        self.assertEqual(snapshot["hierarchy"]["hearth"]["lessons"], 1)
        self.assertFalse(snapshot["counts_truncated"])

    def test_bootstrap_explains_default_retrieval_and_write_policy(self):
        result = self.memory.bootstrap(agent="codex", surface="laptop", project="hearth")
        self.assertEqual(result["authenticated_as"], "codex")
        self.assertEqual(result["default_search"]["mode"], "current")
        self.assertIn("diary", result["default_search"]["excludes"])
        self.assertIn("memory_checkpoint", result["write_policy"])


if __name__ == "__main__":
    unittest.main()
