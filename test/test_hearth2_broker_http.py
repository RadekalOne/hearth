"""Real HTTP requests to the separate stateless, read-only broker surface."""
import json
import asyncio
import unittest
import httpx
import test_hearth2_broker as fixtures
from hearth2.broker_http import create_app


class BrokerHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fixtures.BrokerTests.setUp(self)
        self.token=fixtures.BrokerTests.grant(self)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(self.broker)),base_url='http://broker.test')
        self.addAsyncCleanup(self.client.aclose)

    async def rpc(self,method,params=None,**options):
        return await self.client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':method,'params':params or {}},
            headers={'Authorization':'Bearer '+self.token,**options})

    async def test_only_read_tools_are_exposed_and_scope_cannot_be_spoofed(self):
        init=await self.rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'fixture','version':'1'}})
        self.assertEqual(init.status_code,200,init.text)
        listed=await self.rpc('tools/list')
        names={t['name'] for t in listed.json()['result']['tools']}
        self.assertEqual(names,{'memory_search','memory_get'})
        for tool in listed.json()['result']['tools']:
            self.assertEqual(tool['annotations'],{'readOnlyHint':True,
                'destructiveHint':False,'idempotentHint':True})
        read=await self.rpc('tools/call',{'name':'memory_search','arguments':{'query':'answer'}})
        self.assertEqual(read.status_code,200,read.text)
        self.assertFalse(read.json()['result'].get('isError',False))
        self.assertEqual(self.calls[0][1]['wing'],'trial')
        for name,args in [('memory_add',{'content':'forged'}),('memory_search',{'query':'answer','wing':'other'})]:
            response=await self.rpc('tools/call',{'name':name,'arguments':args})
            self.assertTrue(response.json()['result']['isError'])
        self.assertEqual(len(self.calls),1)

    async def test_no_admin_routes_cookie_auth_or_unauthorized_reads(self):
        payload={'jsonrpc':'2.0','id':1,'method':'tools/list'}
        for headers in [{},{'Cookie':'broker='+self.token},{'Authorization':'Bearer not-a-grant'}]:
            r=await self.client.post('/mcp',json=payload,headers=headers)
            self.assertIn(r.status_code,{401,403})
        for path in ['/mint','/admin','/api/hearth2','/docs','/openapi.json']:
            self.assertEqual((await self.client.get(path)).status_code,404)
        self.assertEqual((await self.client.post('/mint',json={})).status_code,404)

    async def test_revoked_capability_denies_discovery_and_read(self):
        self.broker.revoke(self.controller,self.token)
        for method,params in [('tools/list',{}),('tools/call',{'name':'memory_get','arguments':{'drawer_id':'drawer_fixture'}})]:
            r=await self.rpc(method,params)
            self.assertEqual(r.status_code,403,r.text)
        self.assertEqual(self.calls,[])

    async def test_unsafe_envelopes_and_browser_origins_are_rejected(self):
        self.assertEqual((await self.rpc('tools/list',Origin='https://other.test')).status_code,403)
        headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'}
        r=await self.client.post('/mcp',content='{"jsonrpc":"2.0","id":1,"id":2,"method":"tools/list"}',headers=headers)
        self.assertEqual(r.status_code,400,r.text)
        r=await self.client.post('/mcp',content='x'*65537,headers=headers)
        self.assertEqual(r.status_code,413,r.text)
        unknown=await self.rpc('resources/read',{'uri':'file:///private/core.env'})
        self.assertEqual(unknown.json()['error']['code'],-32601)
        malformed=await self.rpc('initialize',{'protocolVersion':[]})
        self.assertEqual(malformed.status_code,400,malformed.text)
        self.assertEqual(self.calls,[])

    async def test_sdk_client_can_initialize_list_and_read_without_admin_auth(self):
        # MCP 2 declares httpx2; its SDK transport uses that client, while the
        # raw JSON-RPC fixtures above use the service's separate httpx client.
        import httpx2
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=create_app(self.broker)),
                headers={'Authorization':'Bearer '+self.token}) as client:
            async with asyncio.timeout(10):
                async with streamable_http_client('http://broker.test/mcp',http_client=client,terminate_on_close=False) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        tools=await session.list_tools()
                        self.assertEqual({tool.name for tool in tools.tools},{'memory_search','memory_get'})
                        result=await session.call_tool('memory_get',arguments={'drawer_id':'drawer_fixture'})
                        self.assertFalse(result.is_error)
                        self.assertEqual(json.loads(result.content[0].text)['content'],'existing answer')

    async def test_standard_mcp_progress_metadata_does_not_change_tool_or_memory_scope(self):
        listed=await self.rpc('tools/list',{'_meta':{'progressToken':0}})
        self.assertIn('result',listed.json())
        self.assertEqual({tool['name'] for tool in listed.json()['result']['tools']},
                         {'memory_search','memory_get'})
        read=await self.rpc('tools/call',{'name':'memory_search','arguments':{'query':'answer'},
            '_meta':{'progressToken':'native-request','wing':'other','room':'secret'}})
        self.assertFalse(read.json()['result'].get('isError',False))
        self.assertEqual(self.calls[0][1]['wing'],'trial')
        self.assertEqual(self.calls[0][1]['room'],'project')
        self.assertNotIn('_meta',self.calls[0][1])
        snapshot=json.dumps(self.store.snapshot())
        self.assertNotIn('_meta',snapshot)
        self.assertNotIn('native-request',snapshot)
        denied=await self.rpc('tools/call',{'name':'memory_search',
            'arguments':{'query':'answer','wing':'other'},'_meta':{'progressToken':1}})
        self.assertTrue(denied.json()['result']['isError'])
        self.assertEqual(len(self.calls),1)

    async def test_invalid_progress_metadata_is_rejected_without_upstream_access(self):
        for metadata in [[],None,{'progressToken':False},{'progressToken':{}}]:
            with self.subTest(metadata=metadata):
                response=await self.rpc('tools/list',{'_meta':metadata})
                self.assertEqual(response.status_code,400)
        self.assertEqual(self.calls,[])
