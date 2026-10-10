"""Evidence drilldowns retain authentication and exact agent/surface attribution."""
import time
import unittest
from unittest.mock import patch
from test import test_dashboard_auth as auth_tests


class ActivityDetailTests(unittest.IsolatedAsyncioTestCase):
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

    def event(self, eid, surface="desktop", **overrides):
        return {"room_id": "!room:test", "room": "Agent Tasks", "event_id": eid,
                "sender": "@codex:test", "ts": int(time.time() * 1000) - 86400000,
                "body": "[TASK] " + "full evidence " * 100, "tag": "TASK", "tag_base": "TASK",
                "sig_agent": "codex", "sig_surface": surface, "sig_role": "heartbeat",
                "thread_root": None, "reply_to": None, "mentions": [], **overrides}

    async def get(self, path, **params):
        return await self.client.get(path, params=params, headers={"Authorization": "Bearer codex-test-token"})

    async def test_auth_required_and_missing_evidence_returns_404(self):
        for path in ("/api/surfaces/detail?key=codex@desktop", "/api/activity/event?room_id=x&event_id=y"):
            self.assertEqual((await self.client.get(path)).status_code, 401)
        with patch.object(self.memory, "_fetch_room_events", return_value={"events": [], "rooms": {}, "reactions": []}):
            self.assertEqual((await self.get("/api/surfaces/detail", key="missing")).status_code, 404)
            self.assertEqual((await self.get("/api/activity/event", room_id="x", event_id="y")).status_code, 404)

    async def test_surface_contains_only_its_posts_and_checkpoints(self):
        self.memory.memory_checkpoint(agent="codex", surface="desktop", monitor="heartbeat", content="Desktop last run evidence")
        self.memory.memory_checkpoint(agent="codex", surface="laptop", monitor="heartbeat", content="Other surface")
        events = [self.event("$desktop"), self.event("$laptop", "laptop"),
                  self.event("$mismatch", sig_agent="claude")]
        with patch.object(self.memory, "_fetch_room_events", return_value={"events": events}):
            response = await self.get("/api/surfaces/detail", key="codex@desktop")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual([e["event_id"] for e in data["posts"]], ["$desktop"])
        self.assertEqual([c["content"] for c in data["checkpoints"]], ["Desktop last run evidence"])
        self.assertEqual(data["surface"]["last_post_room_id"], "!room:test")
        self.assertEqual(data["posts"][0]["body"], events[0]["body"])

    async def test_full_event_and_related_replies_are_room_scoped(self):
        original = self.event("$task")
        events = [original, self.event("$reply", thread_root="$task"),
                  self.event("$other-room", room_id="!other:test", thread_root="$task"),
                  self.event("$unrelated")]
        with patch.object(self.memory, "_fetch_room_events", return_value={"events": events}):
            response = await self.get("/api/activity/event", room_id="!room:test", event_id="$task")
        data = response.json()
        self.assertEqual(data["event"]["body"], original["body"])
        self.assertGreater(len(data["event"]["body"]), 400)
        self.assertEqual([e["event_id"] for e in data["related"]], ["$reply"])


if __name__ == "__main__":
    unittest.main()
