"""Root-private socket capability; no secret enters worker-facing metadata."""
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import socket
import threading
import urllib.request
import urllib.error
import unittest
import test_hearth2_claims as fixtures
from hearth2.broker import Broker
from hearth2.store import RecordError


@unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'root/Linux private socket checks')
class PrivateBrokerTests(unittest.TestCase):
    def setUp(self):
        fixtures.ClaimTests.setUp(self)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.private_broker'),'private broker channel missing')
        from hearth2.private_broker import PrivateBrokerChannel
        self.Channel=PrivateBrokerChannel;self.claim=self.claim_for_test();self.reads=[];self.tokens=[]
        owner=self
        class ObservedBroker(Broker):
            def mint(self,*args,**kwargs):
                cap=super().mint(*args,**kwargs);owner.tokens.append(cap);return cap
        def upstream(tool,args):
            self.reads.append((tool,args))
            row={'drawer_id':'drawer_fixture','wing':'trial','room':'private','content':'synthetic'}
            return row if tool=='memory_get' else {'results':[row]}
        self.broker=ObservedBroker(self.store,self.controller,upstream)
        self.channel=self.Channel(self.broker,self.controller,self.claim,directory=Path(self.tmp.name),wing='trial',room='private')
        self.addCleanup(self.channel.close)

    def claim_for_test(self):return self.store.claim(self.controller,self.task['id'],expected_revision=1,request_id='private-broker')
    def rpc(self,method='tools/call',params=None,**extra):
        value={'jsonrpc':'2.0','id':1,'method':method,'params':params if params is not None else
            {'name':'memory_get','arguments':{'drawer_id':'drawer_fixture'}},**extra}
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3);client.connect(str(self.channel.socket_path))
            client.sendall(json.dumps(value).encode()+b'\n')
            return json.loads(client.makefile('rb').readline(65537))

    def test_real_scoped_read_without_worker_bearer_and_no_secret_in_metadata(self):
        self.channel.start();response=self.rpc()
        self.assertEqual(json.loads(response['result']['content'][0]['text'])['content'],'synthetic')
        self.assertEqual(self.reads,[('memory_get',{'drawer_id':'drawer_fixture'})])
        public=json.dumps(self.channel.metadata())+repr(self.channel)+json.dumps(response)
        self.assertNotIn(self.tokens[0],public)
        self.assertEqual(Path(self.tmp.name).stat().st_mode&0o777,0o700)
        self.assertEqual(self.channel.socket_path.stat().st_mode&0o777,0o666)

    def test_metadata_and_tools_still_check_live_claim_and_expiry(self):
        self.channel.start();self.assertEqual(len(self.rpc('tools/list',{})['result']['tools']),2)
        self.time+=timedelta(minutes=16)
        self.assertIn('error',self.rpc('tools/list',{}));self.assertEqual(self.reads,[])

    def test_writes_override_fields_and_scope_broadening_are_refused(self):
        self.channel.start()
        for response in [self.rpc(params={'name':'memory_add','arguments':{'content':'no'}}),
            self.rpc(params={'name':'memory_get','arguments':{'drawer_id':'drawer_fixture','room':'other'}}),
            self.rpc(authorization='Bearer supplied-by-worker'),self.rpc('work_claim',{})]:
            self.assertTrue('error' in response or response['result'].get('isError'))
        self.assertEqual(self.reads,[])

    def test_close_revokes_grant_and_unlinks_only_owned_socket(self):
        self.channel.start();self.channel.close();self.channel.close()
        self.assertFalse(self.channel.socket_path.exists());self.assertEqual(len(self.broker._grants),0)

    def test_existing_file_and_symlink_are_preserved_and_grant_not_leaked(self):
        target=Path(self.tmp.name)/'target';target.write_text('preserve')
        self.channel.socket_path.symlink_to(target)
        with self.assertRaises(RecordError):self.channel.start()
        self.assertEqual(target.read_text(),'preserve');self.assertTrue(self.channel.socket_path.is_symlink())
        self.assertEqual(len(self.broker._grants),0)

    def test_nonprivate_directory_refuses_before_mint(self):
        Path(self.tmp.name).chmod(0o755)
        with self.assertRaises(RecordError):self.channel.start()
        self.assertEqual(self.tokens,[])

    def test_tool_annotations_and_request_metadata_match_never_policy(self):
        self.channel.start();tools=self.rpc('tools/list',{'_meta':{'progressToken':2}})['result']['tools']
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in tools))
        self.assertEqual(self.rpc('initialize',{'protocolVersion':'2025-03-26'})['result']['protocolVersion'],'2025-03-26')

    def test_loopback_bridge_reads_real_broker_without_worker_authorization(self):
        from hearth2.private_broker_bridge import create_private_mcp_server
        self.channel.start();server=create_private_mcp_server(socket_path=self.channel.socket_path,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        request={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{
            'name':'memory_get','arguments':{'drawer_id':'drawer_fixture'}}}
        url='http://127.0.0.1:'+str(server.server_port)+'/mcp'
        def send(headers=None):return urllib.request.urlopen(urllib.request.Request(url,
            data=json.dumps(request).encode(),headers={'Content-Type':'application/json',**(headers or {})}),timeout=3)
        self.assertEqual(json.loads(send().read())['id'],3)
        for headers in [{'Authorization':'Bearer must-not-be-forwarded'},{'Origin':'https://outside.test'}]:
            with self.assertRaises(urllib.error.HTTPError) as error:send(headers)
            self.assertEqual(error.exception.code,403)
        self.assertEqual(len(self.reads),1)


class PrivateProfileTests(unittest.TestCase):
    def test_private_profile_contains_no_worker_token_reference_or_override(self):
        from hearth2 import native_profiles
        self.assertTrue(callable(getattr(native_profiles,'codex_private_config',None)),'private profile missing')
        value=native_profiles.codex_private_config(model='gpt-6.1-sol')
        self.assertNotIn('bearer_token',value);self.assertNotIn('Authorization',value)
        self.assertNotIn('HEARTH_BROKER_CAPABILITY',value)
        self.assertIn('model_provider = "openai"',value);self.assertIn('shell_tool = false',value)


if __name__=='__main__':unittest.main()
