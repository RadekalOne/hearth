"""Root-owned direct native profiles; configuration only, not launch authority.

The launcher must mount these read-only in a fresh home, project exactly one
provider login and the scoped broker capability, and validate effective policy.
No raw secret, arbitrary URL/provider/helper or native fallback is accepted here.
The Claude context is root-approved rules only; retrieved memory and worker text
belong in explicitly untrusted user input, never in this system-prompt field.
"""
import json
import re
import uuid
from .native_policy import BROKER_URL
from .store import RecordError


def _model(value):
    if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}',value) is None:
        raise RecordError('explicit native model identity required')
    return value


def codex_config(*,model):
    model=_model(model)
    return ('model = '+json.dumps(model)+'\n'
        'model_provider = "openai"\n'
        'forced_login_method = "chatgpt"\n'
        'approval_policy = "never"\n'
        'sandbox_mode = "read-only"\n'
        'web_search = "disabled"\n'
        '[features]\nshell_tool = false\nshell_snapshot = false\n'
        '[shell_environment_policy]\ninherit = "none"\nignore_default_excludes = false\n'
        'experimental_use_profile = false\n[shell_environment_policy.filters]\n"HEARTH_*" = "exclude"\n'
        '[history]\npersistence = "none"\n'
        '[mcp_servers.hearth]\n'
        'url = "'+BROKER_URL+'"\n'
        'bearer_token_env_var = "HEARTH_BROKER_CAPABILITY"\n'
        'enabled_tools = ["memory_search", "memory_get"]\n'
        'required = true\nstartup_timeout_sec = 10\ntool_timeout_sec = 15\n')


def claude_arguments(*,model,session_id,context):
    model=_model(model)
    try:
        canonical=str(uuid.UUID(session_id))
        if canonical!=session_id:raise ValueError()
        if (not isinstance(context,str) or not context.strip() or '\0' in context
                or len(context.encode('utf-8'))>32768):raise ValueError()
    except (ValueError,TypeError,AttributeError,UnicodeError):
        raise RecordError('native session identity or context invalid') from None
    servers={'mcpServers':{'hearth':{'type':'http','url':BROKER_URL,
        'headers':{'Authorization':'Bearer ${HEARTH_BROKER_CAPABILITY}'}}}}
    return ['-p','--input-format','stream-json','--output-format','stream-json',
        '--verbose','--include-partial-messages','--replay-user-messages',
        '--permission-prompts','none','--no-chrome','--permission-mode','dontAsk',
        '--tools','','--allowedTools','mcp__hearth__memory_search,mcp__hearth__memory_get',
        '--strict-mcp-config','--mcp-config',json.dumps(servers,separators=(',',':')),
        '--disable-slash-commands','--setting-sources','',
        '--settings','{"fastMode":false,"enableWorkflows":false}',
        '--model',model,'--session-id',canonical,
        '--append-system-prompt','Hearth approved task context.\n'+context]
