"""Wing consolidation (one wing per agent brain), Agent Card chaining/retirement, and diary
compaction.

Run with:
    python -m unittest discover -s test -p "test_*.py"
"""

import gc
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import httpx

REPO = Path(__file__).parents[1]


class ConsolidationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.TemporaryDirectory(prefix="hearth-consolidation-test-")
        os.environ["HEARTH_DATA_DIR"] = cls.data_dir.name
        os.environ["HEARTH_MEMORY_ADMIN_TOKEN"] = "admin-test-token"
        os.environ["HEARTH_HOMESERVER_URL"] = "http://matrix.test"
        os.environ["HEARTH_WING_ALIASES"] = "wing_agent=agents, wing_hearth=hearth"
        os.environ["HEARTH_RETIRED_AGENTS"] = "claude-desktop,claude-laptop,codex-desktop,@mavis-desktop:hearth.test"
        os.environ.pop("HEARTH_CONSOLIDATE_AGENT_WINGS", None)
        Path(cls.data_dir.name, "memory-tokens.json").write_text(
            json.dumps({"claude": "claude-test-token", "codex": "codex-test-token",
                        "mavis": "mavis-test-token"}),
            encoding="utf-8",
        )
        spec = importlib.util.spec_from_file_location(
            "hearth_memory_consolidation_test_app", REPO / "mcp" / "memory" / "app.py"
        )
        cls.memory = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.memory)

    @classmethod
    def tearDownClass(cls):
        for key in ("HEARTH_WING_ALIASES", "HEARTH_RETIRED_AGENTS"):
            os.environ.pop(key, None)
        cls.memory.chroma._system.stop()
        cls.memory.chroma.clear_system_cache()
        cls.memory.drawers = cls.memory.checkpoints = cls.memory.relays = None
        cls.memory.chroma = None
        gc.collect()
        for attempt in range(10):
            try:
                cls.data_dir.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)

    def setUp(self):
        m = self.memory
        got = m.drawers.get()
        if got["ids"]:
            m.drawers.delete(ids=got["ids"])
        m._invalidate_metadata_cache()
        self.principal_token = m.CURRENT_PRINCIPAL.set("claude")

    def tearDown(self):
        self.memory.CURRENT_PRINCIPAL.reset(self.principal_token)

    async def asyncSetUp(self):
        self.memory.SESSIONS.clear()
        transport = httpx.ASGITransport(app=self.memory.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="https://hearth-memory.test",
                                        headers={"Authorization": "Bearer admin-test-token"})

    async def asyncTearDown(self):
        await self.client.aclose()

    # --- helpers ------------------------------------------------------------------

    def _seed(self, drawer_id, wing, room, content, added_by="claude", created="2026-08-01T00:00:00+00:00",
              **extra):
        meta = {"wing": wing, "room": room, "added_by": added_by, "source": "", "surface": "",
                "record_class": self.memory._record_class(room), "created_at": created, **extra}
        self.memory.drawers.add(ids=[drawer_id], documents=[content], metadatas=[meta])
        self.memory._invalidate_metadata_cache()

    def _card(self, name, matrix, updated):
        return f"AGENT CARD: {name}\nmatrix: @{matrix}:hearth.test\nplatform/model: x\ncard updated: {updated}"

    def _seed_hub(self):
        s = self._seed
        # claude's diary fragments across per-machine wings
        s("d1", "agent_claude", "diary", "desktop session 1")
        s("d2", "agent_claude @ laptop (hourly executor)", "diary", "hourly tick")
        s("d3", "agent_claude-desktop", "diary", "old desktop account diary", added_by="claude-desktop")
        s("d4", "wing_claude-cowork", "diary", "cowork session")
        s("c1", "agent_codex-desktop", "diary", "codex desktop diary", added_by="codex-desktop",
          surface="codex @ desktop")
        s("n1", "wing_mavis", "notes-between-agents", "note for claude", added_by="mavis")
        s("x1", "wing_collab", "diary", "collab diary stays")
        s("h1", "wing_hearth", "decisions", "old hearth decision")
        # registry cards
        s("card-claude-old", "wing_agent", "registry", self._card("claude", "claude", "2026-07-08"),
          created="2026-07-08T10:08:36+00:00")
        s("card-claude-new", "agents", "registry", self._card("claude", "claude", "2026-07-25"),
          created="2026-07-25T04:56:18+00:00")
        s("card-claude-laptop", "agents", "registry", self._card("claude-laptop", "claude-laptop", "2026-07-15"),
          added_by="claude-laptop", created="2026-07-15T12:33:57+00:00")
        s("card-claude-desktop", "agents", "registry", self._card("claude-desktop", "claude-desktop", "2026-07-14"),
          added_by="claude-desktop", created="2026-07-14T16:02:39+00:00")
        s("card-codex-desktop", "agents", "registry", self._card("codex-desktop", "codex-desktop", "2026-07-14"),
          added_by="codex-desktop", created="2026-07-14T22:12:41+00:00")
        s("card-mavis-desktop", "agents", "registry", self._card("Mavis (Desktop)", "mavis-desktop", "2026-07-14"),
          added_by="mavis-desktop", created="2026-07-14T15:11:28+00:00")
        s("card-mavis-1", "agents", "registry", self._card("mavis", "mavis", "2026-07-15"),
          added_by="mavis", created="2026-07-15T21:34:50+00:00")
        s("card-mavis-2", "agents", "registry", self._card("mavis (Desktop surface)", "mavis", "2026-07-15b"),
          added_by="mavis", created="2026-07-15T21:44:05+00:00", superseded_by="card-mavis-3")
        s("card-mavis-3", "agents", "registry", self._card("mavis (Desktop surface)", "mavis", "2026-08-04"),
          added_by="mavis", created="2026-08-04T20:04:46+00:00", supersedes="card-mavis-2")

    def _meta(self, drawer_id):
        return self.memory.drawers.get(ids=[drawer_id], include=["metadatas"])["metadatas"][0]

    # --- wing target derivation -------------------------------------------------------

    def test_agent_wing_target_derivation(self):
        target = self.memory._agent_wing_target
        roster = {"claude", "codex", "mavis"}
        self.assertIsNone(target("agent_claude", roster))
        self.assertEqual(target("agent_claude-desktop", roster), ("agent_claude", "desktop"))
        self.assertEqual(target("agent_claude @ laptop (hourly executor)", roster),
                         ("agent_claude", "laptop (hourly executor)"))
        self.assertEqual(target("wing_mavis", roster), ("agent_mavis", ""))
        self.assertEqual(target("wing_claude-cowork", roster), ("agent_claude", "cowork"))
        self.assertEqual(target("agent_codex-desktop", roster), ("agent_codex", "desktop"))
        self.assertEqual(target("wing_agent", roster), ("agents", ""), "explicit alias from env")
        self.assertEqual(target("wing_hearth", roster), ("hearth", ""))
        self.assertIsNone(target("wing_collab", roster))
        self.assertIsNone(target("hearth", roster))
        self.assertIsNone(target("projects", roster))

    # --- consolidation ----------------------------------------------------------------------

    def test_consolidation_moves_wings_preserving_surface_and_origin(self):
        self._seed_hub()
        report = self.memory.run_consolidation({"claude", "codex", "mavis"})
        self.assertEqual(report["wings"]["moved"], 7)
        self.assertEqual(self._meta("d2")["wing"], "agent_claude")
        self.assertEqual(self._meta("d2")["surface"], "laptop (hourly executor)")
        self.assertEqual(self._meta("d2")["original_wing"], "agent_claude @ laptop (hourly executor)")
        self.assertEqual(self._meta("d3")["surface"], "desktop")
        self.assertEqual(self._meta("d4")["surface"], "cowork")
        self.assertEqual(self._meta("c1")["wing"], "agent_codex")
        self.assertEqual(self._meta("c1")["surface"], "codex @ desktop", "an existing surface is kept")
        self.assertEqual(self._meta("n1")["wing"], "agent_mavis")
        self.assertEqual(self._meta("n1")["room"], "notes-between-agents", "rooms are untouched")
        self.assertEqual(self._meta("x1")["wing"], "wing_collab", "non-agent wings stay")
        self.assertEqual(self._meta("h1")["wing"], "hearth")
        self.assertEqual(self._meta("card-claude-old")["wing"], "agents")
        self.assertNotIn("original_wing", self._meta("d1"), "already-home drawers are not touched")

        # The agent's continuity is now one stream.
        diary = self.memory.diary_read("claude", limit=50)
        self.assertEqual({e["drawer_id"] for e in diary["entries"]}, {"d1", "d2", "d3", "d4"})

        # Idempotent: a second run changes nothing.
        again = self.memory.run_consolidation({"claude", "codex", "mavis"})
        self.assertEqual(again["wings"]["moved"], 0)
        self.assertEqual(again["retired_cards"]["retired"], 0)
        self.assertEqual(again["card_chains"]["linked"], 0)
        self.assertEqual(self._meta("d2")["original_wing"], "agent_claude @ laptop (hourly executor)")

    def test_consolidation_retires_and_chains_agent_cards(self):
        self._seed_hub()
        report = self.memory.run_consolidation({"claude", "codex", "mavis"})
        self.assertEqual(report["retired_cards"]["retired"], 4)
        for card in ("card-claude-laptop", "card-claude-desktop", "card-codex-desktop", "card-mavis-desktop"):
            meta = self._meta(card)
            self.assertTrue(meta["retracted"], card)
            self.assertEqual(meta["retracted_by"], "consolidation")
            self.assertIn("deactivated", meta["retraction_reason"])
        self.assertNotIn("retracted", self._meta("card-mavis-1"))

        # claude: the old wing_agent card (moved into agents) is chained under the newer one.
        self.assertEqual(report["card_chains"]["agents"], ["claude", "mavis"])
        self.assertEqual(report["card_chains"]["linked"], 2)
        old = self.memory.memory_get("card-claude-old")
        self.assertFalse(old["supersession"]["is_current"])
        self.assertEqual(old["supersession"]["current"], "card-claude-new")
        # mavis: the existing structural link 2->3 is respected; only 1->2 is added.
        chain = self.memory.memory_get("card-mavis-1")["supersession"]["chain"]
        self.assertEqual(chain, ["card-mavis-1", "card-mavis-2", "card-mavis-3"])
        self.assertEqual(self._meta("card-mavis-3")["supersedes"], "card-mavis-2")

        # Default registry search now shows exactly one current card per agent.
        results = self.memory.search_drawers("AGENT CARD matrix platform", None, "registry", 20, 1.5)
        current = sorted(r["drawer_id"] for r in results["results"])
        self.assertEqual(current, ["card-claude-new", "card-mavis-3"])

    async def test_consolidate_endpoint_is_admin_only(self):
        self._seed_hub()
        denied = await self.client.post("/api/consolidate",
                                        headers={"Authorization": "Bearer codex-test-token"})
        self.assertEqual(denied.status_code, 403)
        ok = await self.client.post("/api/consolidate")
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertEqual(body["wings"]["moved"], 7)
        self.assertEqual(body["retired_cards"]["retired"], 4)
        self.assertIn("ran_at", body)

    # --- diary compaction -----------------------------------------------------------------------

    def test_diary_compact_rolls_entries_into_a_summary(self):
        m = self.memory
        token = m.CURRENT_PRINCIPAL.set("codex")
        try:
            ids = [m.diary_write("codex", f"heartbeat {i}: quiet tick, nothing actionable zebra")["drawer_id"]
                   for i in range(3)]
            keep = m.diary_write("codex", "material session: shipped the export endpoint")["drawer_id"]
            result = m.diary_compact("codex", ids, "Week of quiet ticks; nothing actionable.", period="2026-W35")
            self.assertEqual(result["compacted"], 3)
            summary = m.memory_get(result["summary_id"])
            self.assertEqual(summary["kind"], "summary")
            self.assertEqual(summary["compacts"], 3)
            self.assertEqual(summary["record_class"], "diary")
            self.assertEqual(summary["period"], "2026-W35")

            diary = m.diary_read("codex", limit=20)
            self.assertEqual({e["drawer_id"] for e in diary["entries"]}, {result["summary_id"], keep})
            self.assertEqual(diary["compacted_hidden"], 3)
            kinds = {e["drawer_id"]: e["kind"] for e in diary["entries"]}
            self.assertEqual(kinds[result["summary_id"]], "summary")
            self.assertEqual(kinds[keep], "entry")
            everything = m.diary_read("codex", limit=20, include_compacted=True)
            self.assertEqual(everything["count"], 5)

            original = m.memory_get(ids[0])
            self.assertEqual(original["record_class"], "archive")
            self.assertEqual(original["compacted_into"], result["summary_id"])
            # Hidden from history search too, while the summary is found.
            found = m.search_drawers("quiet tick zebra nothing actionable", None, None, 10, 1.5,
                                     include_diaries=True)
            found_ids = {r["drawer_id"] for r in found["results"]}
            self.assertNotIn(ids[0], found_ids)
            self.assertIn(result["summary_id"], found_ids)
            # The startup migration must not un-archive compacted entries.
            m.migrate_legacy_metadata()
            self.assertEqual(m.memory_get(ids[0])["record_class"], "archive")

            with self.assertRaisesRegex(ValueError, "already compacted"):
                m.diary_compact("codex", [ids[0]], "again")
            with self.assertRaisesRegex(ValueError, "unknown diary drawers"):
                m.diary_compact("codex", ["drawer_nope"], "x")
            with self.assertRaisesRegex(ValueError, "summary is required"):
                m.diary_compact("codex", [keep], "  ")
        finally:
            m.CURRENT_PRINCIPAL.reset(token)

    def test_diary_compact_is_own_agent_only_and_diary_only(self):
        m = self.memory
        token = m.CURRENT_PRINCIPAL.set("codex")
        try:
            entry = m.diary_write("codex", "a codex entry")["drawer_id"]
        finally:
            m.CURRENT_PRINCIPAL.reset(token)
        with self.assertRaisesRegex(ValueError, "cannot write continuity"):
            m.diary_compact("codex", [entry], "claude summarising codex")
        lesson = m.memory_add("agent_claude", "lessons", "not a diary", source="s")["drawer_id"]
        with self.assertRaisesRegex(ValueError, "is not in agent_claude/diary"):
            m.diary_compact("claude", [lesson], "wrong room")


if __name__ == "__main__":
    unittest.main()
