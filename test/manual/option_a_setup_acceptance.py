"""Explicit trial-only disposable proof for Option A setup. Sends no model requests."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from hearth2.broker import Broker
from hearth2.private_broker import PrivateBrokerChannel
from option_a_setup import DockerEnrollment, RUN, _docker, _registered, bounded_enrollment, fixture_upstream
from test_hearth2_private_broker import PrivateBrokerTests


TRIAL = Path('/root/hearth-runner-trial')
STAGED = TRIAL / RUN
ORIGINAL = 'c3e5d738af6b5cfa12d4ba50bd2561530e099c3bdf677adc7a95b08942f74029'
BINARY = TRIAL / 'clients/codex/0.159.1/vendor/x86_64-unknown-linux-musl/bin/codex'
WORKER = """
import json, urllib.error, urllib.request, sys
def call(method, params):
    body=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8010/mcp',data=body),timeout=2) as reply:
            return json.load(reply)
    except urllib.error.HTTPError as error:
        if error.code == 502:
            return {'channel_closed': True}
        raise
def read(name, args):
    return call('tools/call', {'name':name,'arguments':args})
def value(response):
    return json.loads(response['result']['content'][0]['text'])
if sys.argv[1] == 'revoked':
    assert call('tools/list',{}).get('channel_closed') is True
else:
    tools=call('tools/list',{})['result']['tools']
    assert {t['name'] for t in tools} == {'memory_search','memory_get'}
    assert all(t['annotations']['readOnlyHint'] for t in tools)
    rows=value(read('memory_search',{'query':'entitlement-20261116-01','limit':1}))['results']
    assert len(rows)==1
    row=rows[0]
    assert row['content']=='Verification marker: HEARTH-RECEIPT-16NOV. This is synthetic memory, not production.'
    assert value(read('memory_get',{'drawer_id':row['drawer_id']}))==row
    assert 'error' in read('memory_add',{'content':'fixture only'})
    assert 'error' in read('memory_get',{'drawer_id':'drawer_other'})
    assert 'error' in read('memory_search',{'query':row['key'],'wing':'shared'})
"""


def proof(state_dir, bridge, fail_after_start, exit_controller=False):
    fixture = PrivateBrokerTests()
    fixture.setUp()
    broker = Broker(fixture.store, fixture.controller, fixture_upstream(STAGED / 'synthetic-memory.json'))
    channel = PrivateBrokerChannel(broker, fixture.controller, fixture.claim,
                                   directory=Path(fixture.tmp.name),
                                   wing='entitlement-fixture', room='synthetic')
    port = DockerEnrollment(binary=BINARY, config=STAGED / 'config.toml', bridge=bridge,
                            state_dir=state_dir)
    start = port.start
    if fail_after_start:
        def fail(cid):
            start(cid)
            raise ValueError('synthetic startup failure')
        port.start = fail
    try:
        try:
            with bounded_enrollment(port, channel) as cid:
                assert not fail_after_start
                if exit_controller:
                    (state_dir / 'controller-exit.json').write_text(json.dumps({
                        'cid': cid, 'label': port.attempt, 'socket': str(channel.socket_path),
                        'outcome': str(port.receipt.with_suffix('.outcome')),
                    }), encoding='utf-8')
                    os._exit(0)
                for _ in range(12):
                    result = _docker('exec', cid, 'python', '-B', '-c', WORKER, 'read', check=False)
                    if result.returncode == 0:
                        break
                    if 'Connection refused' not in result.stderr:
                        raise AssertionError(result.stderr[-700:])
                    time.sleep(.2)
                else:
                    raise AssertionError('loopback bridge did not become ready')
                assert port.read_native_account('account/read', {'refreshToken': False})['account'] is None
                channel.close()
                _docker('exec', cid, 'python', '-B', '-c', WORKER, 'revoked')
        except ValueError as error:
            assert fail_after_start and str(error) == 'synthetic startup failure'
        assert channel.metadata()['closed'] and not channel.socket_path.exists()
        assert not _registered(port.attempt)
        assert not _docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + port.cid).stdout.strip()
        assert port.watchdog.poll() is not None
    finally:
        channel.close()
        fixture.doCleanups()
        fixture.tmp.cleanup()


def original_status():
    return _docker('inspect','--format','{{.State.Status}} {{.HostConfig.NetworkMode}}',ORIGINAL).stdout.strip()


def cutoff_after_controller_exit(state_dir, bridge):
    child = os.fork()
    if child == 0:
        try:
            proof(state_dir, bridge, False, exit_controller=True)
        finally:
            os._exit(1)
    _, result = os.waitpid(child, 0)
    assert os.waitstatus_to_exitcode(result) == 0
    ready = json.loads((state_dir / 'controller-exit.json').read_text(encoding='utf-8'))
    outcome = Path(ready['outcome'])
    deadline = time.monotonic() + 107
    while time.monotonic() < deadline:
        if outcome.is_file():
            try:
                observed = json.loads(outcome.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                pass
            else:
                assert observed == {'cid': ready['cid'], 'removed': True}
                break
        time.sleep(.2)
    else:
        raise AssertionError('outside cutoff outcome missing')
    assert not _registered(ready['label'])
    assert not Path(ready['socket']).exists()


if __name__ == '__main__':
    if (os.getenv('HEARTH_OPTION_A_FIXTURE') != '1' or os.geteuid() != 0
            or os.uname().nodename.split('.')[0] != 'srv2065995'):
        raise SystemExit('requires explicit trial fixture opt-in')
    assert original_status() == 'created none'
    with tempfile.TemporaryDirectory(prefix='option-a-fixture-', dir=TRIAL) as state:
        bridge = Path(sys.argv[1]).resolve()
        tempfile.tempdir = state
        proof(Path(state), bridge, False)
        print('Exact fixture and signed-out local status verified; denied reads and revocation verified.', flush=True)
        proof(Path(state), bridge, True)
        print('Startup failure removed exact staging CID and revoked the grant.', flush=True)
        if '--outside-cutoff' in sys.argv:
            cutoff_after_controller_exit(Path(state), bridge)
            print('Independent cutoff removed the exact CID and socket after controller exit.', flush=True)
    assert original_status() == 'created none'
