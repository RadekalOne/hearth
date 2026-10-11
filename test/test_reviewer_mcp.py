import json
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import httpx2
from test.test_memory_mcp_protocol import MemoryMCPProtocolTests


class ReviewerMCP(MemoryMCPProtocolTests):
    async def asyncSetUp(self):
        if not self.memory.reviewer_store.accounts():
            self.memory.reviewer_store.provision('fixture','reviewer-protocol-secret','full')
        await super().asyncSetUp()

    async def test_modern_and_legacy_clients_discover_bootstrap(self):
        for mode in ('auto','legacy'):
            transport_client=httpx2.AsyncClient(headers={'Authorization':'Bearer reviewer-protocol-secret'},timeout=10)
            try:
                async with Client(streamable_http_client(f'http://127.0.0.1:{self.port}/mcp',http_client=transport_client),mode=mode) as client:
                    tools=await client.list_tools()
                    names={tool.name for tool in tools.tools}
                    self.assertIn('memory_bootstrap',names)
                    self.assertTrue(names <= self.memory._reviewers.READ_TOOLS,names)
                    result=await client.call_tool('memory_bootstrap',{'agent':'codex','compact':True})
                    self.assertFalse(result.is_error)
                    payload=result.structured_content or json.loads(result.content[0].text)
                    self.assertEqual(payload['authenticated_as'],'reviewer:fixture')
                    resource=await client.read_resource('hearth://bootstrap')
                    self.assertEqual(json.loads(resource.contents[0].text)['authenticated_as'],'reviewer:fixture')
            finally:
                await transport_client.aclose()
