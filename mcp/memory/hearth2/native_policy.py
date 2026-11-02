"""Fixed memory-only trial policy for a future root-owned native launcher.

These are policy artifacts and argument validation, not permission to launch.
No credential, environment inheritance, executable path or transport is supplied
by this module. The launcher must still verify effective policy inside its OS
boundary before a prompt. General coding tools require a separate task policy.
"""
import json
import uuid
from .store import RecordError


BROKER_URL = 'http://hearth-broker:8010/mcp'


def codex_requirements():
    return '''allowed_approval_policies = ["never"]
allowed_sandbox_modes = ["read-only"]
default_permissions = ":read-only"
[allowed_permission_profiles]
":read-only" = true
[features]
multi_agent = false
shell_tool = false
apps = false
plugins = false
hooks = false
browser_use = false
browser_use_external = false
browser_use_full_cdp_access = false
in_app_browser = false
computer_use = false
code_mode = false
code_mode_host = false
image_generation = false
view_image = false
[mcp_servers.hearth]
identity = { url = "http://hearth-broker:8010/mcp" }
'''


def claude_managed_settings():
    return {
        'permissions': {
            'disableBypassPermissionsMode':'disable', 'defaultMode':'dontAsk',
            'allow':['mcp__hearth__memory_search', 'mcp__hearth__memory_get'],
            'deny':['Agent', 'Task', 'Workflow', 'SendMessage', 'Bash', 'PowerShell',
                    'Read', 'Edit', 'Write', 'WebFetch', 'WebSearch', 'mcp__cloudroom__*'],
        },
        'allowManagedPermissionRulesOnly':True,
    }


def _strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise RecordError('duplicate native configuration field')
            result[key] = item
        return result
    try:
        return json.loads(value, object_pairs_hook=pairs)
    except (ValueError, TypeError) as error:
        raise RecordError('invalid native configuration') from error


def claude_arguments(arguments, *, expected_model):
    """Validate the pinned core invocation, then replace bypass with fixed tools.

    Preserve the SDK handshake and its transcript identity, while root-managed
    denies block Cloudroom delegation tools. No resume/fork/provider/plugin or
    additional settings escape is admitted. Unknown future flags fail closed.
    """
    if (not isinstance(arguments, list) or not arguments or len(arguments) > 80
            or any(not isinstance(item, str) or '\0' in item for item in arguments)
            or sum(len(item.encode()) for item in arguments) > 65536
            or not isinstance(expected_model, str) or not expected_model.strip()):
        raise RecordError('invalid native invocation')
    flags = {'-p', '--verbose', '--include-partial-messages', '--replay-user-messages',
             '--dangerously-skip-permissions', '--no-chrome'}
    values = {'--input-format', '--output-format', '--permission-prompts', '--model',
              '--append-system-prompt', '--disallowedTools', '--mcp-config', '--session-id'}
    selected, settings, index = {}, [], 0
    while index < len(arguments):
        flag = arguments[index]
        index += 1
        if flag in flags:
            value = True
        elif flag in values or flag == '--settings':
            if index == len(arguments):
                raise RecordError('incomplete native invocation')
            value = arguments[index]
            index += 1
        else:
            raise RecordError('unsupported native invocation flag')
        if flag == '--settings':
            setting = _strict_json(value)
            if (json.dumps(setting, sort_keys=True) not in [
                    json.dumps({'fastMode':False, 'enableWorkflows':False}, sort_keys=True),
                    json.dumps({'attribution':{'commit':'', 'pr':''}}, sort_keys=True)]
                    or setting in settings):
                raise RecordError('unsupported native settings')
            settings.append(setting)
        else:
            if flag in selected:
                raise RecordError('duplicate native invocation flag')
            selected[flag] = value
    if (set(selected) != flags | values or selected['--model'] != expected_model
            or selected['--input-format'] != 'stream-json'
            or selected['--output-format'] != 'stream-json'
            or selected['--permission-prompts'] != 'none'):
        raise RecordError('native invocation differs from registered policy')
    try:
        session = str(uuid.UUID(selected['--session-id']))
    except (ValueError, TypeError, AttributeError) as error:
        raise RecordError('invalid native session identity') from error
    if session != selected['--session-id']:
        raise RecordError('invalid native session identity')
    if _strict_json(selected['--mcp-config']) != {
            'mcpServers':{'cloudroom':{'type':'sdk', 'name':'cloudroom'}}}:
        raise RecordError('unapproved native MCP configuration')
    denied = 'AskUserQuestion,EnterPlanMode,ExitPlanMode,Agent,Task,Workflow,SendMessage'
    if selected['--disallowedTools'] != denied:
        raise RecordError('native delegation policy differs from pinned core')
    output = ['-p', '--input-format', 'stream-json', '--output-format', 'stream-json',
              '--verbose', '--include-partial-messages', '--replay-user-messages',
              '--permission-prompts', 'none', '--no-chrome',
              '--permission-mode', 'dontAsk', '--tools', '',
              '--strict-mcp-config', '--disable-slash-commands', '--setting-sources', '',
              '--model', expected_model,
              '--append-system-prompt', selected['--append-system-prompt'],
              '--disallowedTools', denied, '--mcp-config', selected['--mcp-config'],
              '--session-id', session,
              '--settings', '{"fastMode":false,"enableWorkflows":false}']
    for setting in settings:
        if 'attribution' in setting:
            output += ['--settings', json.dumps(setting, separators=(',', ':'))]
    return output
