"""Opt-in isolated trial policy checks, without a user turn or real credentials.

Tests installed native clients in disposable network-none containers. The
Claude SDK handshake uses an explicitly fake key and a closed loopback URL;
this is not a subscription/account/allowance or model acceptance test.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'mcp/memory'))
from hearth2.native_policy import codex_requirements, claude_managed_settings, claude_arguments


CODEX = Path('/usr/local/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex')
CLAUDE = Path('/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe')
IMAGE = 'hearth2-verify:20261028'


class NativeProcess:
    def __init__(self, directory, provider, policy, arguments, *, projection=None):
        self.name = 'hearth2-native-policy-' + uuid.uuid4().hex
        binary = CODEX if provider == 'codex' else CLAUDE
        destination = ('/etc/codex/requirements.toml' if provider == 'codex'
                       else '/etc/claude-code/managed-settings.json')
        home, cwd = '/scratch', '/scratch'
        mounts = []
        if projection is not None:
            if provider != 'claude':
                raise RuntimeError('projection fixture is Claude-only')
            account, work = map(Path, projection)
            for path in (account, work):
                path.relative_to('/run/hearth2-fixtures')
                if not path.is_absolute() or path.resolve() != path or not path.is_dir():
                    raise RuntimeError('invalid fixture projection')
            if account.parent != work.parent:
                raise RuntimeError('fixture projections must share one run root')
            home, cwd = str(account), str(work)
            mounts = ['--mount', f'type=bind,src={account},dst={account}',
                      '--mount', f'type=bind,src={work},dst={work},readonly']
        self.log = (directory / (self.name + '.stderr')).open('wb')
        args = ['docker', 'run', '-i', '--rm', '--name', self.name,
                '--label', 'hearth2.native-policy=' + self.name,
                '--pull', 'never', '--network', 'none', '--read-only',
                '--user', '1000:1000', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                '--memory', '2g', '--cpus', '1',
                '--tmpfs', '/scratch:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
                '--tmpfs', '/tmp:rw,nosuid,nodev,uid=1000,gid=1000,size=64m',
                '--env', 'HOME=' + home, '--workdir', cwd,
                '--mount', f'type=bind,src={binary},dst=/usr/local/bin/{provider},readonly',
                '--mount', f'type=bind,src={policy},dst={destination},readonly'] + mounts
        if provider == 'codex':
            args += ['--env', 'CODEX_HOME=/scratch']
        else:
            args += ['--env', 'CLAUDE_CONFIG_DIR=' + (home + '/.claude' if projection else '/scratch/claude'),
                     '--env', 'DISABLE_AUTOUPDATER=1',
                     '--env', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1',
                     '--env', 'ANTHROPIC_BASE_URL=http://127.0.0.1:9',
                     '--env', 'ANTHROPIC_API_KEY=fixture-not-a-real-key']
        try:
            self.process = subprocess.Popen(args + [IMAGE, provider] + arguments,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log)
        except BaseException:
            self.log.close()
            raise
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b''
        self.cleanup_verified = False

    def send(self, message):
        self.process.stdin.write(json.dumps(message).encode() + b'\n')
        self.process.stdin.flush()

    def receive(self, predicate, *, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                value = json.loads(line)
                if predicate(value):
                    return value
                # A minimal empty SDK server keeps the compatibility handshake
                # independent of Cloudroom tools, credentials and child agents.
                request = value.get('request', {})
                if value.get('type') == 'control_request' and request.get('subtype') == 'mcp_message':
                    message = request.get('message', {})
                    if 'id' in message:
                        result = ({'protocolVersion':'2025-11-25', 'capabilities':{'tools':{}},
                                   'serverInfo':{'name':'hearth2-empty-fixture', 'version':'1'}}
                                  if message.get('method') == 'initialize' else {'tools':[]})
                        self.send({'type':'control_response', 'response':{
                            'subtype':'success', 'request_id':value['request_id'],
                            'response':{'mcp_response':{'jsonrpc':'2.0', 'id':message['id'], 'result':result}}}})
                continue
            if self.selector.select(min(1, max(0, end-time.monotonic()))):
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('native fixture ended before expected response')
                self.buffer += chunk
                if len(self.buffer) > 8_000_000:
                    raise RuntimeError('native fixture response exceeded bound')
        raise RuntimeError('native fixture response deadline expired')

    def text_output(self):
        output, _ = self.process.communicate(timeout=20)
        if self.process.returncode != 0:
            raise RuntimeError('native fixture command failed; private stderr retained')
        return output.decode()

    def close(self):
        # The host observer owns cleanup; neither client gets Docker access.
        def present():
            query = subprocess.run(['docker', 'container', 'ls', '--all',
                '--filter', 'name=^/' + self.name + '$', '--format', '{{.Names}}'],
                text=True, capture_output=True, timeout=5)
            if query.returncode != 0:
                raise RuntimeError('native fixture inventory unavailable; cleanup unconfirmed')
            names = query.stdout.splitlines()
            if names not in ([], [self.name]):
                raise RuntimeError('native fixture inventory identity mismatch')
            return bool(names)
        try:
            if self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
            if present():
                label = subprocess.run(['docker', 'inspect', '-f',
                    '{{index .Config.Labels "hearth2.native-policy"}}', self.name],
                    text=True, capture_output=True, timeout=5)
                if label.returncode == 0:
                    if label.stdout.strip() != self.name:
                        raise RuntimeError('native fixture ownership mismatch')
                    # --rm can remove an exiting client between inspect and rm.
                    # A failed rm needs a successful inventory proving absence.
                    subprocess.run(['docker', 'rm', '--force', self.name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                elif present():
                    raise RuntimeError('native fixture ownership unavailable')
            if present():
                raise RuntimeError('native fixture cleanup not confirmed')
            self.cleanup_verified = True
        finally:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process.stdout.close()
            self.selector.close()
            self.log.close()


@contextmanager
def native(directory, provider, policy, arguments):
    process = NativeProcess(directory, provider, policy, arguments)
    try:
        yield process
    finally:
        process.close()


def immutable_file(path, content):
    path.write_text(content)
    path.chmod(0o444)


def codex_probe(directory):
    policy = directory / 'codex-requirements.toml'
    immutable_file(policy, '')
    with native(directory, 'codex', policy, ['--version']) as process:
        version = process.text_output().strip()
    assert version == 'codex-cli 0.154.0', 'unreviewed native Codex version'
    overrides = ['--enable', 'multi_agent', '--enable', 'shell_tool', 'features', 'list']
    with native(directory, 'codex', policy, overrides) as process:
        baseline = {line.split()[0]:line.split()[-1] for line in process.text_output().splitlines()
                    if line.startswith(('multi_agent ', 'shell_tool '))}
    assert baseline == {'multi_agent':'true', 'shell_tool':'true'}, 'baseline did not exercise enabled features'
    policy.chmod(0o644)
    immutable_file(policy, codex_requirements())
    with native(directory, 'codex', policy, overrides) as process:
        managed = {line.split()[0]:line.split()[-1] for line in process.text_output().splitlines()
                   if line.startswith(('multi_agent ', 'shell_tool '))}
    assert managed == {'multi_agent':'false', 'shell_tool':'false'}, 'managed feature pins bypassed'
    with native(directory, 'codex', policy, ['app-server', '--listen', 'stdio://']) as process:
        process.send({'id':1, 'method':'initialize', 'params':{
            'clientInfo':{'name':'hearth2-policy-fixture', 'version':'1'},
            'capabilities':{'experimentalApi':True}}})
        process.receive(lambda value:value.get('id') == 1)
        process.send({'method':'initialized'})
        process.send({'id':2, 'method':'thread/start', 'params':{
            'cwd':'/scratch', 'model':'gpt-6.1-sol', 'approvalPolicy':'never',
            'sandbox':'danger-full-access', 'ephemeral':True,
            'config':{'features.multi_agent':True, 'features.shell_tool':True}}})
        response = process.receive(lambda value:value.get('id') == 2)
        result = response.get('result', {})
        assert result.get('sandbox') == {'type':'readOnly', 'networkAccess':False}, 'unsafe sandbox override escaped requirement'
        assert result.get('activePermissionProfile', {}).get('id') == ':read-only'
        assert result.get('thread', {}).get('status', {}).get('type') == 'idle'
        # No turn/start request or user input is sent.
    return {'version':version, 'baseline_features':baseline, 'managed_features':managed,
            'unsafe_request_effective_sandbox':result['sandbox'],
            'cleanup_verified':process.cleanup_verified}


def claude_probe(directory):
    policy = directory / 'claude-managed-settings.json'
    immutable_file(policy, json.dumps(claude_managed_settings()))
    with native(directory, 'claude', policy, ['--version']) as process:
        version = process.text_output().strip()
    assert version == '2.1.280 (Claude Code)', 'unreviewed native Claude version'
    source = ['-p', '--input-format', 'stream-json', '--output-format', 'stream-json',
              '--verbose', '--include-partial-messages', '--replay-user-messages',
              '--dangerously-skip-permissions', '--permission-prompts', 'none', '--no-chrome',
              '--model', 'sonnet', '--append-system-prompt', 'Synthetic policy fixture; no user turn.',
              '--disallowedTools', 'AskUserQuestion,EnterPlanMode,ExitPlanMode,Agent,Task,Workflow,SendMessage',
              '--mcp-config', '{"mcpServers":{"cloudroom":{"type":"sdk","name":"cloudroom"}}}',
              '--session-id', str(uuid.uuid4())]
    arguments = claude_arguments(source, expected_model='sonnet')
    with native(directory, 'claude', policy, arguments) as process:
        process.send({'type':'control_request', 'request_id':'1', 'request':{
            'subtype':'initialize',
            'hooks':{'SubagentStart':[{'hookCallbackIds':['cloudroom-native-child']}]},
            'sdkMcpServers':['cloudroom']}})
        initialized = process.receive(lambda value:value.get('type') == 'control_response'
            and value.get('response', {}).get('request_id') == '1')['response']
        info = initialized.get('response', {})
        assert initialized.get('subtype') == 'success' and info.get('hooks_applied') is True
        assert info.get('current_permission_mode') == 'dontAsk'
        assert info.get('commands') == [], 'native workflow commands remain enabled'
        process.send({'type':'control_request', 'request_id':'2', 'request':{
            'subtype':'set_permission_mode', 'mode':'bypassPermissions'}})
        denied = process.receive(lambda value:value.get('type') == 'control_response'
            and value.get('response', {}).get('request_id') == '2')['response']
        assert denied.get('subtype') == 'error' and 'disabled' in denied.get('error', '')
        # No user message, bootstrap prompt or inference request is sent.
    return {'version':version, 'sdk_hooks_applied':True, 'permission_mode':'dontAsk', 'workflow_commands':0,
            'bypass_change_refused':True, 'cleanup_verified':process.cleanup_verified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture', action='store_true')
    args = parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid() != 0 or socket.gethostname() != 'srv2065995':
        parser.error('explicit opt-in, root and exact isolated trial host required')
    base = Path('/root/hearth-runner-trial')
    directory = Path(tempfile.mkdtemp(prefix='native-policy-', dir=base))
    directory.chmod(0o755)
    result = {'codex':codex_probe(directory), 'claude':claude_probe(directory),
              'model_called':False, 'real_provider_credentials_mounted':False,
              'dummy_claude_auth_used':True, 'network':'none',
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (directory / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'receipt_directory':str(directory), **result}, sort_keys=True))


if __name__ == '__main__':
    main()
