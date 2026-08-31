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
        for collection in (self.memory.drawers, self.memory.checkpoints, self.memory.relays):
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
        self.assertEqual(result["service"]["agent_spec_version"], "1.2")
        self.assertEqual(result["default_search"]["mode"], "current")
        self.assertIn("diary", result["default_search"]["excludes"])
        self.assertIn("memory_checkpoint", result["write_policy"])
        self.assertIn("chat", result["relay_policy"]["use_when"])
        self.assertIn("not a wake signal", result["relay_policy"]["delivery_semantics"])

    def test_relay_is_delivered_claimed_and_resolved_by_interactive_self(self):
        queued = self.memory.create_relay(
            "codex",
            "Implement dashboard authentication",
            requested_by="codex @ chat",
            source_surface="chat",
            source="matrix:$event",
            priority="high",
        )
        bootstrap = self.memory.bootstrap(agent="codex", surface="laptop")
        self.assertEqual(bootstrap["relay_inbox"]["count"], 1)
        entry = bootstrap["relay_inbox"]["entries"][0]
        self.assertEqual(entry["relay_id"], queued["relay_id"])
        self.assertEqual(entry["requested_by"], "codex")
        self.assertEqual(entry["source_surface"], "chat")

        claimed = self.memory.claim_relay(queued["relay_id"], "codex", "laptop")
        self.assertEqual(claimed["state"], "claimed")
        with self.assertRaisesRegex(ValueError, "already claimed"):
            self.memory.claim_relay(queued["relay_id"], "codex", "desktop")
        resolved = self.memory.resolve_relay(
            queued["relay_id"], "codex", "Implemented and verified"
        )
        self.assertEqual(resolved["state"], "resolved")
        self.assertEqual(self.memory.relay_inbox_for("codex", "open")["count"], 0)
        history = self.memory.relay_inbox_for("codex", "resolved")
        self.assertEqual(history["entries"][0]["outcome"], "Implemented and verified")

    def test_agent_cannot_relay_to_or_claim_for_another_agent(self):
        with self.assertRaisesRegex(ValueError, "cannot write continuity"):
            self.memory.create_relay("claude", "Handle this")

    def test_relay_priority_is_validated(self):
        with self.assertRaisesRegex(ValueError, "priority must be"):
            self.memory.create_relay("codex", "Handle this", priority="eventually")

    def test_relay_must_be_claimed_before_resolution(self):
        queued = self.memory.create_relay("codex", "Handle this")
        with self.assertRaisesRegex(ValueError, "must be claimed"):
            self.memory.resolve_relay(queued["relay_id"], "codex", "Done")

    # --- Phase 1: provenance requirement + supersession (LL Wiki borrow) ---

    def test_memory_add_rejects_placeholder_source_for_knowledge(self):
        for bad in ("", "  ", "n/a", "TODO", "none", "-", "test"):
            with self.assertRaisesRegex(ValueError, "real source/provenance"):
                self.memory.memory_add("hearth", "lessons", "A durable lesson",
                                       source=bad)

    def test_memory_add_accepts_real_source_for_knowledge(self):
        res = self.memory.memory_add("hearth", "lessons", "A durable lesson",
                                     source="drawer_abc123 / commit 311556a")
        self.assertIn("drawer_id", res)

    def test_placeholder_gate_exempts_non_knowledge_records(self):
        # Diaries and archives legitimately carry an empty source.
        diary = self.memory.memory_add("agent_codex", "diary", "session note",
                                       source="")
        self.assertIn("drawer_id", diary)
        archive = self.memory.memory_add("hearth", "archive-agent-logs", "old log",
                                         source="")
        self.assertIn("drawer_id", archive)

    def test_supersession_links_both_directions(self):
        old = self.memory.memory_add("hearth", "decisions", "Old decision",
                                     source="room brainstorm 8/29")
        new = self.memory.memory_add("hearth", "decisions", "Revised decision",
                                     source="live session 8/30",
                                     supersedes=old["drawer_id"])
        self.assertEqual(new["supersedes"], old["drawer_id"])
        old_got = self.memory.memory_get(old["drawer_id"])
        self.assertEqual(old_got["superseded_by"], new["drawer_id"])
        new_got = self.memory.memory_get(new["drawer_id"])
        self.assertEqual(new_got["supersedes"], old["drawer_id"])

    def test_memory_get_traverses_chain_to_current_head(self):
        d1 = self.memory.memory_add("hearth", "decisions", "v1", source="s1")
        d2 = self.memory.memory_add("hearth", "decisions", "v2", source="s2",
                                    supersedes=d1["drawer_id"])
        d3 = self.memory.memory_add("hearth", "decisions", "v3", source="s3",
                                    supersedes=d2["drawer_id"])
        stale = self.memory.memory_get(d1["drawer_id"])
        self.assertFalse(stale["supersession"]["is_current"])
        self.assertEqual(stale["supersession"]["current"], d3["drawer_id"])
        self.assertEqual(stale["supersession"]["chain"],
                         [d1["drawer_id"], d2["drawer_id"], d3["drawer_id"]])
        middle = self.memory.memory_get(d2["drawer_id"])
        self.assertEqual(middle["supersession"]["chain"],
                         [d1["drawer_id"], d2["drawer_id"], d3["drawer_id"]])
        head = self.memory.memory_get(d3["drawer_id"])
        self.assertTrue(head["supersession"]["is_current"])
        self.assertEqual(head["supersession"]["chain"],
                         [d1["drawer_id"], d2["drawer_id"], d3["drawer_id"]])

    def test_supersedes_unknown_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            self.memory.memory_add("hearth", "decisions", "orphan",
                                   source="s", supersedes="drawer_doesnotexist")

    def test_superseding_non_current_target_is_rejected(self):
        d1 = self.memory.memory_add("hearth", "decisions", "v1", source="event 1")
        d2 = self.memory.memory_add("hearth", "decisions", "v2", source="event 2",
                                    supersedes=d1["drawer_id"])
        with self.assertRaisesRegex(ValueError, "already has successor"):
            self.memory.memory_add("hearth", "decisions", "conflicting v2",
                                   source="event 3", supersedes=d1["drawer_id"])
        self.assertEqual(
            self.memory.memory_get(d1["drawer_id"])["superseded_by"],
            d2["drawer_id"],
        )

    def test_room_is_normalized_before_provenance_policy(self):
        diary = self.memory.memory_add("agent_codex", " diary ", "session note",
                                       source="")
        self.assertEqual(diary["room"], "diary")

    def test_get_without_supersession_omits_the_block(self):
        d = self.memory.memory_add("hearth", "lessons", "standalone", source="s")
        self.assertNotIn("supersession", self.memory.memory_get(d["drawer_id"]))


if __name__ == "__main__":
    unittest.main()
