"""Hearth Memory v2 tests: import class, retract, duplicate guard, exact lane, filters,
export/import round-trip, and the dashboard aggregates (inbox / surfaces / timeline).

Run with:
    python -m unittest discover -s test -p "test_*.py"
"""

import gc
import importlib.util
import json
import os
import re
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

REPO = Path(__file__).parents[1]
NOW_MS = int(time.time() * 1000)
H = 3600 * 1000


def _load_memory(data_dir: str, admin_token: str = "admin-test-token"):
    os.environ["HEARTH_DATA_DIR"] = data_dir
    os.environ["HEARTH_MEMORY_ADMIN_TOKEN"] = admin_token
    os.environ["HEARTH_HOMESERVER_URL"] = "http://matrix.test"
    os.environ["HEARTH_MATRIX_TOKEN"] = "observer-token"
    os.environ.pop("HEARTH_HUMAN_IDS", None)
    Path(data_dir, "memory-tokens.json").write_text(
        json.dumps({"claude": "claude-test-token", "codex": "codex-test-token",
                    "mavis": "mavis-test-token"}),
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(
        f"hearth_memory_v2_{Path(data_dir).name}", REPO / "mcp" / "memory" / "app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _teardown_memory(module, data_dir):
    module.chroma._system.stop()
    module.chroma.clear_system_cache()
    module.drawers = module.checkpoints = module.relays = None
    module.chroma = None
    gc.collect()
    for attempt in range(10):
        try:
            data_dir.cleanup()
            break
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.1)


def _msg(room_id, event_id, sender, body, ts, mentions=None, reply_to=None):
    content = {"msgtype": "m.text", "body": body}
    if mentions:
        content["m.mentions"] = {"user_ids": mentions}
    if reply_to:
        content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
    return {"type": "m.room.message", "event_id": event_id, "sender": sender,
            "origin_server_ts": ts, "content": content, "room_id": room_id}


def _reaction(room_id, event_id, sender, target, key, ts):
    return {"type": "m.reaction", "event_id": event_id, "sender": sender,
            "origin_server_ts": ts, "room_id": room_id,
            "content": {"m.relates_to": {"rel_type": "m.annotation",
                                         "event_id": target, "key": key}}}


RAD, CLAUDE, CODEX, MAVIS = ("@rad:hearth.test", "@claude:hearth.test",
                             "@codex:hearth.test", "@mavis:hearth.test")
ROOMS = {"!tasks": "Agent Tasks", "!decisions": "Agent Decisions", "!logs": "Agent Logs"}
EVENTS = {
    "!tasks": [
        _msg("!tasks", "$e1", CLAUDE, "[TASK] Export memory to JSONL nightly.", NOW_MS - 10 * H),
        _msg("!tasks", "$e2", CODEX, "[PLAN] Nightly export\n1. cron\n-- codex @ laptop (executor)", NOW_MS - 9 * H),
        _msg("!tasks", "$e3", RAD, "[APPROVED]", NOW_MS - 8 * H),
        _msg("!tasks", "$e14", CODEX, "[BLOCKED] cannot run the export unattended\n-- codex @ laptop (auto)", NOW_MS - int(7.8 * H)),
        _msg("!tasks", "$e15", CODEX, "[PLAN] Export design\n-- codex @ laptop (executor)", NOW_MS - int(7.5 * H)),
        _msg("!tasks", "$e11", CODEX, "[PLAN] Rotate observer token\n-- codex @ laptop (executor)", NOW_MS - 7 * H),
        _reaction("!tasks", "$r1", RAD, "$e11", "👍️", NOW_MS - int(6.8 * H)),
        _msg("!tasks", "$e12", CODEX, "[OUTCOME] Nightly export shipped.\n-- codex @ laptop (executor)", NOW_MS - int(6.5 * H)),
        _msg("!tasks", "$e17", CODEX, "[BLOCKED] need VPS reach for the rebuild\n-- codex @ laptop (auto)", NOW_MS - 6 * H),
        _msg("!tasks", "$e18", CLAUDE, "[STATUS] Rebuilt from the desktop; resolves codex's [BLOCKED] $e17.\n-- claude @ desktop", NOW_MS - int(5.5 * H)),
        _msg("!tasks", "$e16", CLAUDE, "[TASK] Old idea nobody wants.", NOW_MS - 5 * H),
        _reaction("!tasks", "$r2", RAD, "$e16", "✅", NOW_MS - int(4.9 * H)),
        _msg("!tasks", "$e10", CLAUDE, "[TASK] Write the dashboard guide.", NOW_MS - 4 * H),
        _msg("!tasks", "$e4", CLAUDE, "[PLAN] Dashboard v2\n1. endpoints\n-- claude @ desktop", NOW_MS - 3 * H),
        _msg("!tasks", "$e13", CLAUDE, "[TASK] Rotate the observer token monthly.", NOW_MS - int(2.5 * H)),
        _msg("!tasks", "$e5", MAVIS, "[BLOCKED-NEEDS-RAD] need the VPS password reset\n- mavis @ laptop (auto)", NOW_MS - 2 * H),
        _msg("!tasks", "$e6", CODEX, "rad: should I proceed with the rotation?", NOW_MS - 1 * H, mentions=[RAD]),
    ],
    "!decisions": [
        _msg("!decisions", "$e9", RAD, "reduce cadence to once per hour", NOW_MS - 6 * H),
        _msg("!decisions", "$e8", CLAUDE, "[DECISION] Hourly cadence adopted.\n-- claude @ desktop", NOW_MS - 5 * H),
    ],
    "!logs": [
        _msg("!logs", "$e19", CODEX, "[STATUS] weekly upgrade check: nothing to do\n-- codex @ vps (executor)", NOW_MS - 3 * H),
        _msg("!logs", "$e7", MAVIS, "[tick 12:00 ET 9/3] [HB] quiet\n- mavis @ laptop (auto)", NOW_MS - 30 * 60 * 1000),
    ],
}


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _MatrixObserver:
    """Fake httpx.AsyncClient serving the observer's rooms."""

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url, headers=None, params=None):
        if url.endswith("/joined_rooms"):
            return _Response(200, {"joined_rooms": list(ROOMS)})
        m = re.search(r"/rooms/([^/]+)/state/m.room.name", url)
        if m:
            return _Response(200, {"name": ROOMS[m.group(1)]})
        m = re.search(r"/rooms/([^/]+)/messages", url)
        if m:
            chunk = sorted(EVENTS[m.group(1)], key=lambda e: -e["origin_server_ts"])
            return _Response(200, {"chunk": chunk, "start": "t0", "end": None})
        return _Response(404, {})

    async def post(self, url, json=None, headers=None):
        return _Response(200, {})


class MemoryV2Tests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.TemporaryDirectory(prefix="hearth-memory-v2-test-")
        cls.memory = _load_memory(cls.data_dir.name)

    @classmethod
    def tearDownClass(cls):
        _teardown_memory(cls.memory, cls.data_dir)

    def setUp(self):
        m = self.memory
        for collection in (m.drawers, m.checkpoints, m.relays):
            got = collection.get()
            if got["ids"]:
                collection.delete(ids=got["ids"])
        m._invalidate_metadata_cache()
        m._ROOM_CACHE["at"] = 0.0
        m._ROOM_CACHE["value"] = None
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

    # --- helpers -----------------------------------------------------------

    def _seed_import(self, drawer_id="legacy-noise", wing=".claude", added_by="mempalace",
                     source="mempalace:C:\\Users\\rad\\.claude\\changelog.md",
                     content="Fixed memory growth in long sessions from render caches"):
        self.memory.drawers.add(ids=[drawer_id], documents=[content], metadatas=[{
            "wing": wing, "room": "technical", "added_by": added_by, "source": source,
            "created_at": "2026-06-09T14:29:03.899162", "imported": True,
        }])
        self.memory._invalidate_metadata_cache()

    # --- spec version guard --------------------------------------------------

    def test_agent_spec_version_matches_docs_header(self):
        header = (REPO / "docs" / "AGENT-SPEC.md").read_text(encoding="utf-8").splitlines()[0]
        doc_version = re.search(r"\(v(\d+\.\d+)\)", header).group(1)
        self.assertEqual(self.memory.AGENT_SPEC_VERSION, doc_version,
                         "bump AGENT_SPEC_VERSION in app.py when docs/AGENT-SPEC.md bumps")

    # --- import class ----------------------------------------------------------

    def test_migration_classifies_mined_imports_and_normalises_timestamps(self):
        self._seed_import()
        # A migrated agent note keeps its class even though it was imported.
        self.memory.drawers.add(ids=["migrated-note"], documents=["Note for mavis from claude"],
                                metadatas=[{"wing": "wing_mavis", "room": "notes-between-agents",
                                            "added_by": "claude", "source": "mempalace",
                                            "created_at": "2026-06-14T21:54:26.944992",
                                            "imported": True}])
        first = self.memory.migrate_legacy_metadata()
        self.assertEqual(first["updated"], 2)
        noise = self.memory.drawers.get(ids=["legacy-noise"], include=["metadatas"])["metadatas"][0]
        note = self.memory.drawers.get(ids=["migrated-note"], include=["metadatas"])["metadatas"][0]
        self.assertEqual(noise["record_class"], "import")
        self.assertEqual(note["record_class"], "knowledge")
        self.assertEqual(noise["created_at"], "2026-06-09T14:29:03.899162+00:00")
        second = self.memory.migrate_legacy_metadata()
        self.assertEqual(second["updated"], 0, "migration must be idempotent")

    def test_default_search_hides_imports_unless_requested(self):
        self._seed_import()
        self.memory.migrate_legacy_metadata()
        phrase = "memory growth long sessions render caches"
        self.memory.memory_add("hearth", "lessons", "Real lesson about render caches and memory growth",
                               source="drawer_abc")
        default = self.memory.search_drawers(phrase, None, None, 10, 1.5)
        self.assertNotIn("legacy-noise", [r["drawer_id"] for r in default["results"]])
        self.assertIn("import", default["excluded_by_default"])
        with_imports = self.memory.search_drawers(phrase, None, None, 10, 1.5, include_imports=True)
        self.assertIn("legacy-noise", [r["drawer_id"] for r in with_imports["results"]])
        self.assertEqual(with_imports["mode"], "history")

    def test_status_reports_classes_and_taxonomy_counts_per_class(self):
        self._seed_import()
        self.memory.migrate_legacy_metadata()
        self.memory.memory_add("hearth", "lessons", "A lesson", source="s1")
        snapshot = self.memory.status()
        self.assertEqual(snapshot["classes"], {"import": 1, "knowledge": 1})
        tax = self.memory.taxonomy()
        wings = {w["wing"]: w for w in tax["wings"]}
        self.assertEqual(wings[".claude"]["classes"], {"import": 1})
        self.assertEqual(wings["hearth"]["rooms"][0]["room"], "lessons")

    # --- superseded / retracted filtering ------------------------------------------

    def test_superseded_hidden_by_default_and_flagged_when_requested(self):
        old = self.memory.memory_add("hearth", "decisions", "Desktop mavis has no chat access",
                                     source="event $a")
        new = self.memory.memory_add("hearth", "decisions", "Desktop mavis has full chat access",
                                     source="event $b", supersedes=old["drawer_id"])
        default = self.memory.search_drawers("mavis chat access", None, None, 10, 1.5)
        ids = [r["drawer_id"] for r in default["results"]]
        self.assertIn(new["drawer_id"], ids)
        self.assertNotIn(old["drawer_id"], ids)
        self.assertTrue(all(r["is_current"] for r in default["results"]))
        history = self.memory.search_drawers("mavis chat access", None, None, 10, 1.5,
                                             include_superseded=True)
        rows = {r["drawer_id"]: r for r in history["results"]}
        self.assertFalse(rows[old["drawer_id"]]["is_current"])
        self.assertEqual(rows[old["drawer_id"]]["superseded_by"], new["drawer_id"])

    def test_retract_hides_from_search_but_keeps_for_audit(self):
        d = self.memory.memory_add("hearth", "lessons", "The stall was caused by DNS", source="run 42")
        result = self.memory.memory_retract(d["drawer_id"], "mechanism unverified; retracted")
        self.assertTrue(result["retracted"])
        self.assertFalse(result["already_retracted"])
        again = self.memory.memory_retract(d["drawer_id"], "different reason")
        self.assertTrue(again["already_retracted"])
        self.assertEqual(again["retraction_reason"], "mechanism unverified; retracted")
        search = self.memory.search_drawers("stall caused by DNS", None, None, 10, 1.5)
        self.assertEqual(search["results"], [])
        shown = self.memory.search_drawers("stall caused by DNS", None, None, 10, 1.5,
                                           include_retracted=True)
        self.assertTrue(shown["results"][0]["retracted"])
        got = self.memory.memory_get(d["drawer_id"])
        self.assertTrue(got["retracted"])
        self.assertEqual(got["retracted_by"], "claude")

    def test_only_author_or_admin_can_retract(self):
        d = self.memory.memory_add("hearth", "lessons", "Claude's lesson", source="s")
        token = self.memory.CURRENT_PRINCIPAL.set("codex")
        try:
            with self.assertRaisesRegex(ValueError, "only the author"):
                self.memory.memory_retract(d["drawer_id"], "not mine")
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(token)
        token = self.memory.CURRENT_PRINCIPAL.set("admin")
        try:
            self.assertTrue(self.memory.memory_retract(d["drawer_id"], "admin cleanup")["retracted"])
        finally:
            self.memory.CURRENT_PRINCIPAL.reset(token)
        with self.assertRaisesRegex(ValueError, "reason is required"):
            self.memory.memory_retract(d["drawer_id"], "")

    # --- exact lane -----------------------------------------------------------------

    def test_exact_lane_finds_ids_and_event_ids_first(self):
        target = self.memory.memory_add(
            "hearth", "lessons",
            "Relay tools were missing; see event $ToljHQeOBH3mF4mo7ls8KcvnAu5qJ7l1BWi6geKilJE",
            source="room read")
        for i in range(6):
            self.memory.memory_add("hearth", "lessons", f"Unrelated lesson number {i} about deploys",
                                   source=f"s{i}", on_duplicate="ignore")
        by_drawer = self.memory.search_drawers(f"what is {target['drawer_id']}", None, None, 3, 1.5)
        self.assertEqual(by_drawer["results"][0]["drawer_id"], target["drawer_id"])
        self.assertEqual(by_drawer["results"][0]["match"], "exact")
        self.assertEqual(by_drawer["exact_matches"], 1)
        by_event = self.memory.search_drawers(
            "deploy $ToljHQeOBH3mF4mo7ls8KcvnAu5qJ7l1BWi6geKilJE", None, None, 3, 1.5)
        self.assertEqual(by_event["results"][0]["drawer_id"], target["drawer_id"])
        self.assertEqual(by_event["results"][0]["matched_token"],
                         "$ToljHQeOBH3mF4mo7ls8KcvnAu5qJ7l1BWi6geKilJE")
        plain = self.memory.search_drawers("lesson about deploys", None, None, 3, 1.5)
        self.assertTrue(all(r["match"] == "semantic" for r in plain["results"]))

    # --- duplicate guard -----------------------------------------------------------

    def test_memory_add_reports_near_duplicates_and_can_reject(self):
        text = "When the notifier restarts, resume from the saved sync cursor because otherwise mentions are lost"
        first = self.memory.memory_add("hearth", "lessons", text, source="notify.test")
        self.assertNotIn("similar", first)
        # Superseding the only near-copy is the intended path: the target is excluded from
        # the check, so even on_duplicate="reject" lets the replacement through.
        v2 = self.memory.memory_add("hearth", "lessons", text + " (v2)", source="v2",
                                    supersedes=first["drawer_id"], on_duplicate="reject")
        self.assertEqual(v2["supersedes"], first["drawer_id"])
        self.assertNotIn("similar", v2)
        # A parallel copy is reported against the current head, never the superseded one.
        second = self.memory.memory_add("hearth", "lessons", text + ".", source="notify.test again")
        self.assertEqual([s["drawer_id"] for s in second["similar"]], [v2["drawer_id"]])
        self.assertLessEqual(second["similar"][0]["distance"], self.memory.DUP_DISTANCE)
        self.assertIn("hint", second)
        with self.assertRaisesRegex(ValueError, "near-duplicate.*Pass supersedes"):
            self.memory.memory_add("hearth", "lessons", text, source="third", on_duplicate="reject")
        different = self.memory.memory_add("hearth", "lessons",
                                           "Use worktrees so two agents never share one checkout",
                                           source="plan", on_duplicate="reject")
        self.assertIn("drawer_id", different)
        self.assertNotIn("similar", different)
        ignored = self.memory.memory_add("hearth", "lessons", text + "!", source="s", on_duplicate="ignore")
        self.assertNotIn("similar", ignored, "ignore skips the check entirely")
        with self.assertRaisesRegex(ValueError, "on_duplicate must be"):
            self.memory.memory_add("hearth", "lessons", "x", source="s", on_duplicate="maybe")

    # --- batch get + date filters ------------------------------------------------------

    def test_get_many_preserves_order_and_reports_missing(self):
        a = self.memory.memory_add("hearth", "lessons", "A", source="s")["drawer_id"]
        b = self.memory.memory_add("hearth", "lessons", "B", source="s", on_duplicate="ignore")["drawer_id"]
        got = self.memory.memory_get_many([b, "drawer_missing", a])
        self.assertEqual([d["drawer_id"] for d in got["drawers"]], [b, a])
        self.assertEqual(got["missing"], ["drawer_missing"])
        self.assertTrue(all(d["is_current"] for d in got["drawers"]))
        with self.assertRaisesRegex(ValueError, "at most 50"):
            self.memory.memory_get_many([a] * 51)

    def test_since_until_filters_search_and_diary(self):
        old_id = "drawer_old_lesson"
        self.memory.drawers.add(ids=[old_id], documents=["Old lesson about cadence"], metadatas=[{
            "wing": "hearth", "room": "lessons", "added_by": "claude", "source": "s",
            "surface": "", "record_class": "knowledge",
            "created_at": "2026-01-01T00:00:00+00:00",
        }])
        self.memory.memory_add("hearth", "lessons", "New lesson about cadence", source="s")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent = self.memory.search_drawers("lesson about cadence", None, None, 10, 1.5, since=yesterday)
        self.assertNotIn(old_id, [r["drawer_id"] for r in recent["results"]])
        older = self.memory.search_drawers("lesson about cadence", None, None, 10, 1.5,
                                           until="2026-02-01T00:00:00+00:00")
        self.assertEqual([r["drawer_id"] for r in older["results"]], [old_id])
        self.memory.diary_write("claude", "today's session")
        self.assertEqual(self.memory.diary_read("claude", since=yesterday)["count"], 1)
        self.assertEqual(self.memory.diary_read("claude", until=yesterday)["count"], 0)

    # --- bootstrap / cache -----------------------------------------------------------------

    def test_compact_bootstrap_drops_prose_but_keeps_continuity(self):
        full = self.memory.bootstrap(agent="claude", surface="desktop")
        compact = self.memory.bootstrap(agent="claude", surface="desktop", compact=True)
        self.assertIn("protocol", full)
        self.assertNotIn("protocol", compact)
        self.assertNotIn("projects", compact["palace"])
        self.assertIn("checkpoints", compact)
        self.assertIn("relay_inbox", compact)
        self.assertIn("now", compact)
        self.assertIn("import", full["default_search"]["excludes"])

    def test_metadata_scan_is_cached_and_invalidated_on_write(self):
        self.memory.memory_add("hearth", "lessons", "first", source="s")
        rows = self.memory._all_metadata()
        self.assertIs(rows, self.memory._all_metadata(), "second call within TTL reuses the scan")
        self.memory.memory_add("hearth", "lessons", "second", source="s", on_duplicate="ignore")
        self.assertEqual(len(self.memory._all_metadata()), 2)

    # --- REST: export / import round trip -----------------------------------------------

    async def test_export_round_trips_through_import(self):
        payload = {"drawers": [
            {"drawer_id": "d-know", "wing": "hearth", "room": "lessons", "content": "keep me",
             "added_by": "claude", "source": "s", "created_at": "2026-08-01T00:00:00+00:00"},
            {"drawer_id": "d-noise", "wing": ".claude", "room": "technical", "content": "changelog chunk",
             "added_by": "mempalace", "source": "mempalace:C:\\x\\changelog.md",
             "created_at": "2026-06-09T14:29:03.899162"},
            {"drawer_id": "d-old", "wing": "hearth", "room": "decisions", "content": "old decision",
             "added_by": "codex", "source": "s", "superseded_by": "d-know"},
        ]}
        imported = await self.client.post("/api/import", json=payload)
        self.assertEqual(imported.json()["imported"], 3)
        export = await self.client.get("/api/export")
        self.assertEqual(export.status_code, 200)
        self.assertIn("x-ndjson", export.headers["content-type"])
        lines = [json.loads(line) for line in export.text.strip().splitlines()]
        rows = {r["drawer_id"]: r for r in lines}
        self.assertEqual(set(rows), {"d-know", "d-noise", "d-old"})
        self.assertEqual(rows["d-noise"]["record_class"], "import")
        self.assertEqual(rows["d-noise"]["created_at"], "2026-06-09T14:29:03.899162+00:00")
        self.assertEqual(rows["d-old"]["superseded_by"], "d-know")
        only_imports = await self.client.get("/api/export", params={"record_class": "import"})
        self.assertEqual(len(only_imports.text.strip().splitlines()), 1)

        # Wipe and re-import from the export: identical ids and metadata.
        self.memory.drawers.delete(ids=list(rows))
        again = await self.client.post("/api/import", json={"drawers": lines})
        self.assertEqual(again.json()["imported"], 3)
        second = {json.loads(l)["drawer_id"]: json.loads(l)
                  for l in (await self.client.get("/api/export")).text.strip().splitlines()}
        for key in ("content", "wing", "room", "added_by", "source", "created_at", "record_class"):
            self.assertEqual({k: v[key] for k, v in rows.items()},
                             {k: v[key] for k, v in second.items()}, key)
        self.assertEqual(second["d-old"]["superseded_by"], "d-know")

    async def test_export_requires_admin(self):
        response = await self.client.get("/api/export", headers={"Authorization": "Bearer claude-test-token"})
        self.assertEqual(response.status_code, 403)

    async def test_recent_hides_imports_and_supports_filters(self):
        self._seed_import()
        self.memory.migrate_legacy_metadata()
        self.memory.memory_add("hearth", "lessons", "fresh", source="s")
        recent = (await self.client.get("/api/recent")).json()["entries"]
        self.assertEqual([e["wing"] for e in recent], ["hearth"])
        with_imports = (await self.client.get("/api/recent", params={"include_imports": "true"})).json()
        self.assertEqual(len(with_imports["entries"]), 2)
        by_class = (await self.client.get("/api/recent", params={"record_class": "import"})).json()
        self.assertEqual([e["drawer_id"] for e in by_class["entries"]], ["legacy-noise"])

    async def test_drawer_taxonomy_relays_checkpoints_endpoints(self):
        d = self.memory.memory_add("hearth", "lessons", "one", source="s")
        self.memory.write_checkpoint("claude", "desktop", "hearth-room-sweep", "tick ok")
        self.memory.create_relay("claude", "finish the docs", source_surface="chat")
        detail = (await self.client.get(f"/api/drawer/{d['drawer_id']}")).json()
        self.assertEqual(detail["content"], "one")
        self.assertTrue(detail["is_current"])
        self.assertEqual((await self.client.get("/api/drawer/nope")).status_code, 404)
        tax = (await self.client.get("/api/taxonomy")).json()
        self.assertEqual(tax["wings"][0]["wing"], "hearth")
        relays = (await self.client.get("/api/relays")).json()
        self.assertEqual(relays["counts"], {"queued": 1})
        self.assertEqual(relays["entries"][0]["request"], "finish the docs")
        cps = (await self.client.get("/api/checkpoints")).json()
        self.assertEqual(cps["entries"][0]["monitor"], "hearth-room-sweep")
        self.assertIsNotNone(cps["entries"][0]["age_hours"])

    async def test_static_assets_served_and_csp_has_no_unsafe_inline(self):
        js = await self.client.get("/static/app.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["content-type"])
        self.assertEqual((await self.client.get("/static/evil.txt")).status_code, 404)
        self.assertNotIn("unsafe-inline", js.headers["content-security-policy"])

    # --- dashboard aggregates ------------------------------------------------------------------

    async def test_inbox_surfaces_timeline_agents(self):
        m = self.memory
        m.memory_add("hearth", "decisions", "Hourly cadence adopted.", source="$e8")
        m.write_checkpoint("claude", "desktop", "hearth-room-sweep", "sweep ok")
        with patch.object(m.httpx, "AsyncClient", _MatrixObserver):
            inbox = (await self.client.get("/api/inbox")).json()
            surfaces = (await self.client.get("/api/surfaces")).json()
            timeline = (await self.client.get("/api/timeline", params={"days": 7})).json()
            agents = (await self.client.get("/api/agents")).json()

        by_kind = {}
        for item in inbox["items"]:
            by_kind.setdefault(item["kind"], []).append(item["event_id"])
        self.assertEqual(by_kind.get("approval"), ["$e4"],
                         "e2 approved by text, e11 by 👍, e15 executed via codex's own [OUTCOME] e12, e4 open")
        self.assertEqual(by_kind.get("blocked"), ["$e5"],
                         "codex's e14 was cleared by codex's own later [PLAN], e17 by claude's [STATUS] citing "
                         "its event id; mavis's e5 has no follow-up")
        self.assertEqual(by_kind.get("question"), ["$e6"])
        self.assertEqual(by_kind.get("unclaimed_task"), ["$e13"],
                         "e1 was picked up by plan e2, e10 by plan e4, e16 dismissed by rad's check mark; "
                         "a later [BLOCKED] does not claim")
        self.assertEqual(inbox["total"], 4)
        blocked = next(i for i in inbox["items"] if i["kind"] == "blocked")
        self.assertEqual(blocked["surface"], "laptop")
        self.assertEqual(blocked["label"], "Agent is blocked and needs you")
        self.assertEqual(inbox["items"][0]["kind"], "blocked", "blocked sorts first")

        rows = {s["key"]: s for s in surfaces["surfaces"]}
        self.assertIn("mavis@laptop", rows)
        self.assertEqual(rows["mavis@laptop"]["state"], "ok")
        self.assertEqual(rows["mavis@laptop"]["expected_every_minutes"], m.SURFACE_CADENCE_MINUTES)
        self.assertEqual(rows["codex@laptop"]["roles"], ["auto", "executor"])
        self.assertEqual(rows["claude@desktop"]["monitors"], ["hearth-room-sweep"])
        self.assertEqual(rows["claude@desktop"]["state"], "ok", "fresh checkpoint keeps it alive")
        self.assertIsNotNone(rows["claude@desktop"]["checkpoint_at"])
        self.assertEqual(rows["claude@unsigned"]["state"], "on-demand")
        self.assertEqual(rows["codex@vps"]["roles"], ["executor"])
        self.assertEqual(rows["codex@vps"]["state"], "on-demand", "an idle executor is not stalled")
        self.assertIsNone(m._cadence_for("executor"))
        self.assertEqual(m._cadence_for("auto"), m.SURFACE_CADENCE_MINUTES)
        self.assertNotIn("rad@unsigned", rows, "humans are not surfaces")

        kinds = [(i["kind"], i.get("event_id") or i.get("drawer_id")) for i in timeline["items"]]
        self.assertIn(("Decision", "$e8"), kinds)
        self.assertIn(("Decision", "$e9"), kinds, "a human post in the decisions room counts")
        self.assertIn(("Outcome", "$e12"), kinds)
        self.assertTrue(any(i["source"] == "memory" and i["kind"] == "Decision" for i in timeline["items"]))
        self.assertEqual([i["ts"] for i in timeline["items"]],
                         sorted((i["ts"] for i in timeline["items"]), reverse=True))

        cards = {a["name"]: a for a in agents["agents"]}
        self.assertEqual(cards["rad"]["kind"], "human")
        self.assertEqual(cards["claude"]["kind"], "agent")
        self.assertTrue(cards["claude"]["awaiting_approval"])
        self.assertEqual(cards["claude"]["current_task"]["event_id"], "$e4")
        self.assertEqual(cards["mavis"]["blocked"]["event_id"], "$e5")
        self.assertEqual(cards["mavis"]["last_heartbeat"]["event_id"], "$e7")
        self.assertNotIn("usage", cards["mavis"], "empty usage is omitted, not rendered as noise")
        self.assertFalse(cards["codex"]["awaiting_approval"], "codex's plans were approved/executed")
        self.assertEqual(sorted(s["surface"] for s in cards["claude"]["surfaces"]), ["desktop", "unsigned"])

    async def test_human_ids_override_replaces_token_roster(self):
        m = self.memory
        original = m.HUMAN_IDS
        m.HUMAN_IDS = {"rad"}
        try:
            with patch.object(m.httpx, "AsyncClient", _MatrixObserver):
                inbox = (await self.client.get("/api/inbox")).json()
        finally:
            m.HUMAN_IDS = original
        self.assertEqual(inbox["total"], 4)

    def test_tag_and_signature_parsers(self):
        m = self.memory
        self.assertEqual(m._tag_of("[BLOCKED-NEEDS-RAD] x"), ("BLOCKED-NEEDS-RAD", "BLOCKED"))
        self.assertEqual(m._tag_of("[tick 12:00 ET 9/3] [HB] quiet"), ("TICK 12:00 ET 9/3", "TICK"))
        self.assertEqual(m._tag_of("[STATUS/CORRECTION] y"), ("STATUS/CORRECTION", "STATUS"))
        self.assertEqual(m._tag_of("[TASK codex-20260901-090029] z")[1], "TASK")
        self.assertEqual(m._tag_of("plain text"), ("", ""))
        self.assertEqual(m._signature_of("body\n\n-- claude @ laptop (executor)"), ("claude", "laptop", "executor"))
        self.assertEqual(m._signature_of("body\n— codex @ desktop"), ("codex", "desktop", ""))
        self.assertEqual(m._signature_of("body\n- mavis @ laptop (auto)"), ("mavis", "laptop", "auto"))
        self.assertEqual(m._signature_of("body\n— Codex"), ("codex", "", ""))
        self.assertEqual(m._signature_of("no signature here"), ("", "", ""))
        self.assertEqual(m._signature_of("body\n-- claude @ laptop (hourly executor)"), ("claude", "laptop", "hourly executor"))
        long_tail = ("body\n-- claude @ desktop (all five rooms read 20:53:49Z-20:54:14Z and re-read "
                     "immediately before this post; all five newest event ids identical across both batches)")
        self.assertEqual(m._signature_of(long_tail), ("claude", "desktop", ""),
                         "a parenthetical sentence after the surface is not a role")
        self.assertEqual(m._norm_reaction("👍️"), "👍")
        self.assertEqual(m._norm_reaction("👍🏽"), "👍")


if __name__ == "__main__":
    unittest.main()
