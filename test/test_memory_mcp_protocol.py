"""End-to-end MCP 2.0 and legacy-protocol checks for Hearth Memory."""

import asyncio
import gc
import importlib.util
import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

import httpx2
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


class MemoryMCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.TemporaryDirectory(prefix="hearth-memory-mcp-test-")
        os.environ["HEARTH_DATA_DIR"] = cls.data_dir.name
        os.environ["HEARTH_MEMORY_ADMIN_TOKEN"] = "admin-test-token"
        Path(cls.data_dir.name, "memory-tokens.json").write_text(
            json.dumps({"codex": "codex-test-token"}), encoding="utf-8"
        )
        app_path = Path(__file__).parents[1] / "mcp" / "memory" / "app.py"
        spec = importlib.util.spec_from_file_location("hearth_memory_mcp_test_app", app_path)
        cls.memory = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.memory)

    @classmethod
    def tearDownClass(cls):
        cls.memory.chroma._system.stop()
        cls.memory.chroma.clear_system_cache()
        # Chroma's SQLite handle can be released a moment after the ASGI server on
        # Windows. Drop collection references and retry cleanup instead of making an
        # otherwise-passing protocol test flaky with WinError 32.
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        config = uvicorn.Config(
            self.memory.app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(self.server.serve(sockets=[self.sock]))
        for _ in range(100):
            if self.server.started:
                break
            await asyncio.sleep(0.05)
        self.assertTrue(self.server.started, "test MCP server did not start")

    async def asyncTearDown(self):
        self.server.should_exit = True
        await asyncio.wait_for(self.server_task, timeout=10)
        self.sock.close()

    async def _client(self, mode: str):
        http_client = httpx2.AsyncClient(
            headers={"Authorization": "Bearer codex-test-token"},
            timeout=10,
        )
        transport = streamable_http_client(
            f"http://127.0.0.1:{self.port}/mcp",
            http_client=http_client,
        )
        return http_client, Client(transport, mode=mode)

    async def test_modern_and_legacy_clients_discover_bootstrap(self):
        for mode in ("auto", "legacy"):
            with self.subTest(mode=mode):
                http_client, client = await self._client(mode)
                try:
                    async with client:
                        self.assertIn("memory_bootstrap", client.instructions)
                        self.assertIn("queue relay_request", client.instructions)
                        tools = await client.list_tools()
                        tool_names = {tool.name for tool in tools.tools}
                        tools_by_name = {tool.name: tool for tool in tools.tools}
                        self.assertIn("memory_bootstrap", tool_names)
                        self.assertTrue(
                            {"relay_request", "relay_inbox", "relay_claim", "relay_resolve"}
                            <= tool_names
                        )
                        self.assertTrue(
                            tools_by_name["memory_bootstrap"].annotations.read_only_hint
                        )
                        self.assertFalse(
                            tools_by_name["relay_request"].annotations.read_only_hint
                        )
                        self.assertFalse(
                            tools_by_name["relay_request"].annotations.destructive_hint
                        )
                        resources = await client.list_resources()
                        self.assertIn(
                            "hearth://bootstrap",
                            {str(resource.uri) for resource in resources.resources},
                        )
                        resource_result = await client.read_resource("hearth://bootstrap")
                        resource_payload = json.loads(resource_result.contents[0].text)
                        self.assertEqual(resource_payload["authenticated_as"], "codex")
                        result = await client.call_tool(
                            "memory_bootstrap",
                            {"agent": "codex", "surface": "test", "project": "hearth"},
                        )
                        self.assertFalse(result.is_error)
                        payload = result.structured_content or json.loads(result.content[0].text)
                        self.assertEqual(payload["authenticated_as"], "codex")
                        self.assertEqual(payload["service"]["agent_spec_version"], "1.2")
                        self.assertEqual(payload["default_search"]["mode"], "current")
                        if mode == "auto":
                            await client.call_tool(
                                "memory_checkpoint",
                                {"agent": "codex", "surface": "test", "monitor": "heartbeat", "content": "A"},
                            )
                            await client.call_tool(
                                "memory_checkpoint",
                                {"agent": "codex", "surface": "test", "monitor": "heartbeat", "content": "B"},
                            )
                            checkpoint_result = await client.call_tool(
                                "memory_checkpoint_read",
                                {"agent": "codex", "surface": "test", "monitor": "heartbeat"},
                            )
                            checkpoint_payload = checkpoint_result.structured_content or json.loads(
                                checkpoint_result.content[0].text
                            )
                            self.assertEqual(checkpoint_payload["count"], 1)
                            self.assertEqual(checkpoint_payload["entries"][0]["content"], "B")

                            add_result = await client.call_tool(
                                "memory_add",
                                {
                                    "wing": "hearth-test",
                                    "room": "decisions",
                                    "content": "Authenticated authorship wins",
                                    "added_by": "claude @ fake-surface",
                                    "source": "MCP protocol authentication test",
                                },
                            )
                            add_payload = add_result.structured_content or json.loads(add_result.content[0].text)
                            get_result = await client.call_tool(
                                "memory_get", {"drawer_id": add_payload["drawer_id"]}
                            )
                            get_payload = get_result.structured_content or json.loads(get_result.content[0].text)
                            self.assertEqual(get_payload["added_by"], "codex")
                            self.assertEqual(get_payload["surface"], "claude @ fake-surface")

                            forbidden = await client.call_tool(
                                "memory_checkpoint",
                                {"agent": "claude", "surface": "test", "content": "spoof"},
                            )
                            self.assertTrue(forbidden.is_error)

                            relay_result = await client.call_tool(
                                "relay_request",
                                {
                                    "target_agent": "codex",
                                    "request": "Continue this in an interactive session",
                                    "source_surface": "chat",
                                    "priority": "high",
                                },
                            )
                            relay_payload = relay_result.structured_content or json.loads(
                                relay_result.content[0].text
                            )
                            inbox_result = await client.call_tool(
                                "relay_inbox", {"agent": "codex"}
                            )
                            inbox_payload = inbox_result.structured_content or json.loads(
                                inbox_result.content[0].text
                            )
                            self.assertEqual(inbox_payload["entries"][0]["relay_id"], relay_payload["relay_id"])
                finally:
                    await http_client.aclose()


if __name__ == "__main__":
    unittest.main()
