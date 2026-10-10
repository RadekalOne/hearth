"""REST integration: auth, roles, CSRF, validation, and coordinated lifecycle."""
import unittest
from unittest.mock import patch
from test import test_dashboard_auth as auth_tests


class WorkAPITests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        auth_tests.DashboardAuthTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        auth_tests.DashboardAuthTests.tearDownClass.__func__(cls)

    async def asyncSetUp(self):
        await auth_tests.DashboardAuthTests.asyncSetUp(self)

    async def asyncTearDown(self):
        await auth_tests.DashboardAuthTests.asyncTearDown(self)

    async def post(self, path, payload, token="admin-test-token", **kwargs):
        return await self.client.post(path, json=payload, headers={"Authorization": "Bearer " + token, **kwargs})

    async def project(self):
        response = await self.post("/api/work/projects", {"title": "Test team", "goal": "Verified implementation"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_capability_directory_auth_maintenance_and_suggestions(self):
        path = "/api/work/agents/codex/profile"
        profile = {"strengths": ["coding", "review"], "supporting": ["research"],
                   "source": "Reviewed test task", "work_mode": "interactive", "availability": "accepting"}
        self.assertEqual((await self.client.get("/api/work/agents")).status_code, 401)
        self.assertEqual((await self.post(path, profile, "codex-test-token")).status_code, 403)
        self.assertEqual((await self.post(path, profile, Origin="https://evil.test")).status_code, 403)
        self.assertEqual((await self.post(path, {**profile, "source": ""})).status_code, 400)
        self.assertEqual((await self.post("/api/work/agents/missing/profile", profile)).status_code, 404)
        session = self.memory.create_session("@rad:hearth.test", "matrix")
        self.client.cookies.set(self.memory.SESSION_COOKIE, session)
        saved = await self.client.post(path, json=profile)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["updated_by"], "@rad:hearth.test")
        directory = (await self.client.get("/api/work/agents?capability=coding&work_mode=interactive")).json()
        self.assertEqual(directory["suggestions"][0]["agent"], "codex")
        self.assertEqual((await self.client.get("/api/work/agents?capability=invalid")).status_code, 400)
        self.assertEqual((await self.client.get("/api/work/agents?capability=coding&work_mode=background")).json()["suggestions"], [])
        board = (await self.client.get("/api/work")).json()
        self.assertTrue(any(p["id"] == "codex" and p["source"] for p in board["profiles"]))

    async def test_board_requires_auth_and_agent_cannot_manage(self):
        self.assertEqual((await self.client.get("/api/work")).status_code, 401)
        denied = await self.post("/api/work/projects", {"title": "x", "goal": "y"}, "codex-test-token")
        self.assertEqual(denied.status_code, 403)
        response = await self.client.get("/api/work", headers={"Authorization": "Bearer codex-test-token"})
        self.assertFalse(response.json()["can_manage"])

    async def test_explicit_legacy_human_token_can_manage_without_promoting_agents(self):
        tokens = self.memory.load_tokens()
        tokens["rad"] = "legacy-human-test-token"
        self.memory.save_tokens(tokens)
        try:
            with patch.object(self.memory, "HUMAN_TOKEN_IDS", {"rad"}, create=True), \
                 patch.object(self.memory, "HUMAN_IDS", {"rad", "codex"}):
                login = await self.client.post("/api/auth/login", json={"token": "legacy-human-test-token"})
                self.assertEqual(login.status_code, 200)
                self.assertEqual(login.json()["principal"], "rad")
                self.assertTrue((await self.client.get("/api/work")).json()["can_manage"])
                created = await self.client.post("/api/work/projects", json={"title": "Legacy human", "goal": "Manage projects"})
                self.assertEqual(created.status_code, 200, created.text)
                self.client.cookies.clear()
                agent = await self.client.get("/api/work", headers={"Authorization": "Bearer codex-test-token"})
                self.assertFalse(agent.json()["can_manage"])
                denied = await self.post("/api/work/projects", {"title": "Agent", "goal": "Denied"}, "codex-test-token")
                self.assertEqual(denied.status_code, 403)
                admin = await self.client.get("/api/work", headers={"Authorization": "Bearer admin-test-token"})
                self.assertTrue(admin.json()["can_manage"])
            with patch.object(self.memory, "HUMAN_TOKEN_IDS", set(), create=True):
                legacy = await self.client.get("/api/work", headers={"Authorization": "Bearer legacy-human-test-token"})
                self.assertFalse(legacy.json()["can_manage"])
        finally:
            tokens.pop("rad", None)
            self.memory.save_tokens(tokens)

    async def test_human_matrix_session_can_manage_and_csrf_is_rejected(self):
        session = self.memory.create_session("@rad:hearth.test", "matrix")
        self.client.cookies.set(self.memory.SESSION_COOKIE, session)
        response = await self.client.post("/api/work/projects", json={"title": "Human idea", "goal": "Build it"})
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.post("/api/work/projects", headers={"Origin": "https://evil.test"}, json={"title": "x", "goal": "y"})
        self.assertEqual(response.status_code, 403)

    async def test_propose_claim_handoff_review_and_context(self):
        project = await self.project()
        response = await self.post(f'/api/work/projects/{project["id"]}/tasks',
            {"title": "Implement", "acceptance": "Meaningful tests pass", "assignee": "codex"}, "codex-test-token")
        self.assertEqual(response.status_code, 200, response.text)
        task = response.json()
        path = f'/api/work/tasks/{task["id"]}/action'
        self.assertEqual((await self.post(path, {"action": "ready"}, "codex-test-token")).status_code, 403)
        self.assertEqual((await self.post(path, {"action": "ready"})).status_code, 200)
        claim = (await self.post(path, {"action": "claim", "surface": "test"}, "codex-test-token")).json()
        self.assertTrue(claim["claim_id"])
        response = await self.post(path, {"action": "review", "claim_id": claim["claim_id"], "summary": "Tests passed", "evidence": ["test suite receipt"]}, "codex-test-token")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.post(path, {"action": "accept"})).status_code, 200)
        board = (await self.client.get("/api/work", headers={"Authorization": "Bearer admin-test-token"})).json()
        persisted = next(t for t in board["tasks"] if t["id"] == task["id"])
        self.assertEqual(persisted["state"], "done")
        self.assertNotIn("claim_id", persisted)
        response = await self.post(f'/api/work/tasks/{task["id"]}/remember',
            {"content": "Keep work claims atomic across worker surfaces.", "kind": "lessons"}, "codex-test-token")
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved["readback"]["added_by"], "codex")
        self.assertTrue(saved["readback"]["is_current"])
        response = await self.post(f'/api/work/tasks/{task["id"]}/remember',
            {"content": "Keep work claims atomic across worker surfaces.", "kind": "lessons"}, "codex-test-token")
        self.assertEqual(response.json()["drawer_id"], saved["drawer_id"])
        board = (await self.client.get("/api/work", headers={"Authorization": "Bearer admin-test-token"})).json()
        self.assertEqual(sum(e["kind"] == "memory_captured" and e["task_id"] == task["id"] for e in board["activity"]), 1)
        response = await self.client.get(f'/api/work/tasks/{task["id"]}/context', headers={"Authorization": "Bearer codex-test-token"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any(m["drawer_id"] == saved["drawer_id"] for m in response.json()["memory"]))

    async def test_context_filters_retired_unsourced_and_import_records_and_bounds_excerpts(self):
        project = await self.project()
        task = (await self.post(f'/api/work/projects/{project["id"]}/tasks',
            {"title": "Memory quality", "acceptance": "Current source only", "assignee": "codex"})).json()
        records = [
            {"drawer_id": "good", "content": "a" * 9000, "record_class": "knowledge", "is_current": True, "source_status": "provided"},
            {"drawer_id": "retired", "content": "old", "record_class": "knowledge", "is_current": False, "source_status": "provided"},
            {"drawer_id": "noise", "content": "import", "record_class": "import", "is_current": True, "source_status": "provided"},
            {"drawer_id": "unsourced", "content": "claim", "record_class": "knowledge", "is_current": True, "source_status": "missing"}]
        with patch.object(self.memory, "search_drawers", return_value={"results": records}):
            response = await self.client.get(f'/api/work/tasks/{task["id"]}/context', headers={"Authorization": "Bearer codex-test-token"})
        self.assertEqual(response.status_code, 200, response.text)
        bundle = response.json()
        self.assertEqual([m["drawer_id"] for m in bundle["memory"]], ["good"])
        self.assertEqual(len(bundle["memory"][0]["content"]), 4000)
        self.assertTrue(bundle["memory"][0]["content_truncated"])
        self.assertEqual(len(bundle["excluded_memory"]), 3)

    async def test_bad_payload_and_missing_memory_reference_refused(self):
        self.assertEqual((await self.post("/api/work/projects", ["bad"])).status_code, 400)
        project = await self.project()
        path = f'/api/work/projects/{project["id"]}/tasks'
        response = await self.post(path, {"title": "x", "acceptance": "y", "assignee": "codex", "memory_ids": ["drawer_missing"]})
        self.assertEqual(response.status_code, 400)

    async def test_prerequisite_memory_is_inherited_without_semantic_match(self):
        project = await self.project()
        path = f'/api/work/projects/{project["id"]}/tasks'
        parent = (await self.post(path, {"title": "Research", "acceptance": "Cited sources", "assignee": "codex"})).json()
        child = (await self.post(path, {"title": "Build", "acceptance": "Validated artifact", "assignee": "codex", "dependencies": [parent["id"]]})).json()
        self.memory.work_store.link_memory("codex", parent["id"], "drawer_parent")
        record = {"drawer_id": "drawer_parent", "content": "Accepted prerequisite lesson", "record_class": "knowledge", "is_current": True, "source_status": "provided"}
        with patch.object(self.memory, "search_drawers", return_value={"results": []}), patch.object(self.memory, "_drawer_detail", return_value=record):
            response = await self.client.get(f'/api/work/tasks/{child["id"]}/context', headers={"Authorization": "Bearer codex-test-token"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["memory"][0]["drawer_id"], "drawer_parent")
        response = await self.post(path, {"title": "x", "acceptance": "y", "assignee": "unknown"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
