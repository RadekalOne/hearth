"""Coordination invariants, including competing processes and stale same-agent surfaces."""
import importlib.util
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

spec = importlib.util.spec_from_file_location("work_test", Path(__file__).parents[1] / "mcp/memory/work.py")
work = importlib.util.module_from_spec(spec)
spec.loader.exec_module(work)


class WorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "work.sqlite3"
        self.store = work.WorkStore(self.path)
        self.project = self.store.create_project("@rad:test", True, {"title": "Build something", "goal": "Useful verified output"})

    def tearDown(self):
        self.temp.cleanup()

    def task(self, **extra):
        return self.store.create_task("codex", self.project["id"],
            {"title": "Implement", "acceptance": "Tests pass", "assignee": "codex", **extra}, {"codex", "claude"})

    def profile(self, agent="codex", **extra):
        return self.store.set_profile("@rad:test", True, agent,
            {"strengths": ["coding"], "source": "Human assessment from reviewed implementation", **extra}, {"codex", "claude"})

    def test_profiles_persist_with_provenance_and_retired_agents_are_excluded(self):
        self.profile()
        fresh = work.WorkStore(self.path)
        directory = fresh.agent_directory({"codex", "claude"}, "coding")
        p = next(p for p in directory["profiles"] if p["id"] == "codex")
        self.assertEqual(p["updated_by"], "@rad:test")
        self.assertTrue(p["source"])
        self.assertIn("availability unconfirmed", directory["suggestions"][0]["reason"])
        self.assertEqual(fresh.agent_directory({"claude"}, "coding")["suggestions"], [])
        with fresh.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM activity WHERE kind='agent_profile_updated'").fetchone()[0], 1)

    def test_suggestions_use_fit_then_global_workload_and_exclude_paused_or_incompatible(self):
        self.profile()
        self.profile("claude")
        other = self.store.create_project("rad", True, {"title": "Other project", "goal": "Track global load"})
        busy = self.store.create_task("rad", other["id"], {"title": "Busy", "acceptance": "Reviewed", "assignee": "codex"}, {"codex"})
        self.ready(busy)
        suggestions = self.store.agent_directory({"codex", "claude"}, "coding")["suggestions"]
        self.assertEqual([s["agent"] for s in suggestions], ["claude", "codex"])
        self.profile("claude", strengths=[], supporting=["coding"])
        self.assertEqual(self.store.agent_directory({"codex", "claude"}, "coding")["suggestions"][0]["agent"], "codex")
        self.profile(availability="paused")
        self.profile("claude", work_mode="background")
        self.assertEqual(self.store.agent_directory({"codex", "claude"}, "coding", "interactive")["suggestions"], [])
        self.assertEqual(len(self.store.agent_directory({"codex", "claude"})["profiles"]), 2)

    def test_profiles_need_human_assessment_and_validate_categories(self):
        with self.assertRaises(work.WorkError):
            self.store.set_profile("codex", False, "codex", {}, {"codex"})
        for extra in ({"source": ""}, {"supporting": ["coding"]}, {"strengths": ["telepathy"]},
                      {"work_mode": "automatic"}, {"availability": "online"}, {"strengths": ["coding", "design", "planning", "writing"]}):
            with self.subTest(extra=extra), self.assertRaises(work.WorkError):
                self.profile(**extra)
        for extra in ({"capability": "telepathy"}, {"work_mode": "automatic"}):
            with self.assertRaises(work.WorkError):
                self.task(**extra)
        task = self.task(capability="review", work_mode="interactive")
        self.assertEqual(task["capability"], "review")

    def ready(self, task):
        return self.store.action("@rad:test", True, task["id"], {"action": "ready"})

    def claim(self, task, **extra):
        return self.store.action("codex", False, task["id"], {"action": "claim", **extra})

    def finish(self, task):
        claim = self.claim(task)
        self.store.action("codex", False, task["id"], {"action": "review", "claim_id": claim["claim_id"],
            "summary": "Implemented and tested", "evidence": ["test command and result"]})
        return self.store.action("@rad:test", True, task["id"], {"action": "accept"})

    def test_agent_cannot_authorize_or_accept_or_create_project(self):
        with self.assertRaises(work.WorkError):
            self.store.create_project("codex", False, {"title": "x", "goal": "y"})
        task = self.task()
        with self.assertRaises(work.WorkError):
            self.store.action("codex", False, task["id"], {"action": "ready"})
        self.ready(task)
        claim = self.claim(task)
        self.store.action("codex", False, task["id"], {"action": "review", "claim_id": claim["claim_id"], "summary": "x", "evidence": ["test"]})
        with self.assertRaises(work.WorkError):
            self.store.action("codex", False, task["id"], {"action": "accept"})

    def test_competing_connections_claim_exactly_once(self):
        task = self.task()
        self.ready(task)
        def attempt(surface):
            try:
                work.WorkStore(self.path).action("codex", False, task["id"], {"action": "claim", "surface": surface})
                return True
            except work.WorkError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, [str(i) for i in range(8)])), 1)

    def test_dependency_requires_human_review_before_child_claim(self):
        parent = self.task()
        child = self.task(dependencies=[parent["id"]])
        self.ready(parent); self.ready(child)
        with self.assertRaises(work.WorkError):
            self.claim(child)
        self.finish(parent)
        self.assertEqual(self.claim(child)["state"], "running")

    def test_foreign_assignee_cannot_claim(self):
        task = self.task(); self.ready(task)
        with self.assertRaises(work.WorkError):
            self.store.action("claude", False, task["id"], {"action": "claim"})

    def test_expired_claim_recovery_fences_old_same_agent_worker(self):
        task = self.task(); self.ready(task)
        old = self.claim(task)
        with self.store.transaction() as db:
            item = self.store.get(db, "tasks", task["id"])
            item["claim_until"] = time.time() - 1
            self.store.save(db, "tasks", item)
        fresh = self.claim(task)
        self.assertNotEqual(old["claim_id"], fresh["claim_id"])
        with self.assertRaises(work.WorkError):
            self.store.action("codex", False, task["id"], {"action": "heartbeat", "claim_id": old["claim_id"]})
        self.assertEqual(self.store.action("codex", False, task["id"], {"action": "heartbeat", "claim_id": fresh["claim_id"]})["state"], "running")

    def test_evidence_is_required_and_failed_mutation_has_no_audit_event(self):
        task = self.task(); self.ready(task); claim = self.claim(task)
        before = self.store.snapshot()
        with self.assertRaises(work.WorkError):
            self.store.action("codex", False, task["id"], {"action": "review", "claim_id": claim["claim_id"], "summary": "done", "evidence": []})
        after = self.store.snapshot()
        self.assertEqual(len(before["activity"]), len(after["activity"]))
        self.assertEqual(after["tasks"][0]["state"], "running")

    def test_restart_preserves_state_and_comments_attribution(self):
        task = self.task()
        self.store.comment("claude", task["id"], "Research is ready for codex")
        board = work.WorkStore(self.path).snapshot()
        self.assertEqual(board["activity"][0]["actor"], "claude")
        self.assertEqual(board["tasks"][0]["acceptance"], "Tests pass")
        self.assertNotIn("claim_id", board["tasks"][0])

    def test_cross_project_dependency_and_malformed_payload_refused(self):
        other = self.store.create_project("@rad:test", True, {"title": "Other", "goal": "Other goal"})
        foreign = self.store.create_task("codex", other["id"], {"title": "Foreign", "acceptance": "Done"}, {"codex"})
        with self.assertRaises(work.WorkError):
            self.task(dependencies=[foreign["id"]])
        for bad in ["not a list", [42], ["x"] * 51]:
            with self.assertRaises(work.WorkError):
                self.task(dependencies=bad)
        with self.assertRaises(work.WorkError):
            self.task(room_id="!room:test")

    def test_ship_requires_every_task_done_and_shipped_projects_refuse_new_tasks(self):
        task = self.task()
        with self.assertRaises(work.WorkError):
            self.store.project_phase("@rad:test", True, self.project["id"], "shipped")
        self.ready(task); self.finish(task)
        self.assertEqual(self.store.project_phase("@rad:test", True, self.project["id"], "shipped")["phase"], "shipped")
        with self.assertRaises(work.WorkError):
            self.task()

    def test_release_requires_reason_and_revokes_worker(self):
        task = self.task(); self.ready(task); claim = self.claim(task)
        with self.assertRaises(work.WorkError):
            self.store.action("@rad:test", True, task["id"], {"action": "release"})
        self.store.action("@rad:test", True, task["id"], {"action": "release", "reason": "Stop for revision"})
        with self.assertRaises(work.WorkError):
            self.store.action("codex", False, task["id"], {"action": "heartbeat", "claim_id": claim["claim_id"]})

    def test_reassignment_requires_human_and_cannot_change_live_owner(self):
        task = self.task()
        with self.assertRaises(work.WorkError):
            self.store.action("codex", False, task["id"], {"action": "assign", "assignee": "claude"}, {"claude"})
        assigned = self.store.action("@rad:test", True, task["id"], {"action": "assign", "assignee": "claude"}, {"claude"})
        self.assertEqual(assigned["assignee"], "claude")
        self.ready(task)
        self.store.action("claude", False, task["id"], {"action": "claim"})
        with self.assertRaises(work.WorkError):
            self.store.action("@rad:test", True, task["id"], {"action": "assign", "assignee": "codex"}, {"codex"})

    def test_memory_backlink_is_persistent_and_scoped_to_task_project(self):
        task = self.task()
        self.store.link_memory("codex", task["id"], "drawer_output")
        self.store.link_memory("codex", task["id"], "drawer_output")
        board = work.WorkStore(self.path).board_for_task(task["id"])
        self.assertEqual(board["tasks"][0]["output_memory_ids"], ["drawer_output"])
        self.assertEqual(sum(e["kind"] == "memory_captured" for e in board["activity"]), 1)


if __name__ == "__main__":
    unittest.main()
