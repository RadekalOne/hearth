"""Dashboard browser authentication tests.

Run with:
    python -m unittest test/test_dashboard_auth.py
"""

import importlib.util
import gc
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _MatrixClient:
    calls = []

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append((url, json, headers))
        if url.endswith("/login"):
            if json["identifier"]["user"] == "rad" and json["password"] == "correct":
                return _Response(200, {
                    "user_id": "@rad:hearth.test",
                    "access_token": "temporary-matrix-token",
                })
            return _Response(403, {"errcode": "M_FORBIDDEN"})
        return _Response(200, {})


class DashboardAuthTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.TemporaryDirectory(prefix="hearth-dashboard-auth-test-")
        os.environ["HEARTH_DATA_DIR"] = cls.data_dir.name
        os.environ["HEARTH_MEMORY_ADMIN_TOKEN"] = "admin-test-token"
        os.environ["HEARTH_HOMESERVER_URL"] = "http://matrix.test"
        Path(cls.data_dir.name, "memory-tokens.json").write_text(
            json.dumps({"codex": "codex-test-token"}), encoding="utf-8"
        )
        app_path = Path(__file__).parents[1] / "mcp" / "memory" / "app.py"
        spec = importlib.util.spec_from_file_location("hearth_dashboard_auth_test_app", app_path)
        cls.memory = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.memory)

    @classmethod
    def tearDownClass(cls):
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

    async def asyncSetUp(self):
        self.memory.SESSIONS.clear()
        transport = httpx.ASGITransport(app=self.memory.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="https://hearth-memory.test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_protected_api_requires_authentication(self):
        response = await self.client.get("/api/status")
        self.assertEqual(response.status_code, 401)
        status = await self.client.get("/api/auth/status")
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["authenticated"])
        self.assertEqual(status.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'", status.headers["content-security-policy"])

    async def test_token_login_uses_httponly_session_but_mcp_stays_bearer_only(self):
        response = await self.client.post("/api/auth/login", json={"token": "admin-test-token"})
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("Secure", cookie)
        self.assertNotIn("admin-test-token", cookie)

        status = await self.client.get("/api/auth/status")
        self.assertEqual(status.json()["principal"], "admin")
        self.assertEqual((await self.client.get("/api/status")).status_code, 200)
        self.assertEqual((await self.client.post("/mcp")).status_code, 401)

    async def test_matrix_password_login_creates_session_and_discards_access_token(self):
        _MatrixClient.calls = []
        with patch.object(self.memory.httpx, "AsyncClient", _MatrixClient):
            response = await self.client.post(
                "/api/auth/login",
                json={"username": "rad", "password": "correct"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["principal"], "@rad:hearth.test")
        self.assertTrue(_MatrixClient.calls[0][0].endswith("/login"))
        self.assertTrue(_MatrixClient.calls[1][0].endswith("/logout"))
        self.assertEqual(
            _MatrixClient.calls[1][2]["Authorization"],
            "Bearer temporary-matrix-token",
        )
        self.assertEqual((await self.client.get("/api/status")).status_code, 200)

    async def test_invalid_matrix_password_returns_generic_error(self):
        with patch.object(self.memory.httpx, "AsyncClient", _MatrixClient):
            response = await self.client.post(
                "/api/auth/login",
                json={"username": "rad", "password": "wrong"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid username, password, or access token")

    async def test_logout_invalidates_session(self):
        await self.client.post("/api/auth/login", json={"token": "codex-test-token"})
        self.assertEqual((await self.client.get("/api/status")).status_code, 200)
        self.assertEqual((await self.client.post("/api/auth/logout")).status_code, 200)
        self.assertEqual((await self.client.get("/api/status")).status_code, 401)


if __name__ == "__main__":
    unittest.main()
