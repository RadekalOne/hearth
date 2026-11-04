"""Bounded, conditional MCode source analysis. Never runtime or start authority."""
from dataclasses import dataclass, fields
import hashlib
import json
import re

import yaml
from yaml import events as ev

from .mcode_oauth import _JS_TRIM
from .minimax_consumer import _HEADER, _load
from .store import RecordError

_SOURCES=('0.4.1','b79bf405b47654e4295b918bfc0bf5d84e4f73d3b05197c89c909dedef8f9b9f',
          '7f91af66b8692739662669da6a04ba294d9da871bb667b19ce6ff98cddd42e73',
          'fc77436612ef5b8d771252eb6f47772e2f4b19ee82e8a815b351f78540f4c9a0')
_ID=re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',re.ASCII)
_MODEL=re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.:/-]*',re.ASCII)
_URL=re.compile(r'https://([A-Za-z0-9.-]+)(?::443)?(/[A-Za-z0-9._~!$&\'()*+,;=:@%/-]*)?',re.ASCII|re.IGNORECASE)
_HOST_LABEL=re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',re.ASCII)
_MANAGED=frozenset(('agent.minimax.io','agent.minimax.cn','agent.minimaxi.com'))
_BAD_KEYS=frozenset(('__proto__','prototype','constructor','<<'))
_AUTH_HEADERS=frozenset(('authorization','proxy-authorization','x-api-key','api-key','x-goog-api-key','cookie'))
_BEARER=object()


def _refuse():raise RecordError('unsupported MCode configuration input') from None
def _trim(value):return value.strip(_JS_TRIM)
def _text(value):
    if type(value) is not str:_refuse()
def _fields(value,allowed):
    if type(value) is not dict or value.keys()-set(allowed):_refuse()
def _unparsed(value,allowed):
    if type(value) is not dict:_refuse()
    return len(value.keys()-set(allowed))
def _boolean(value):
    if type(value) is not bool:_refuse()
def _name(value,model=False):
    pattern=_MODEL if model else _ID
    if type(value) is not str or len(value)>256 or value in _BAD_KEYS or not pattern.fullmatch(value):_refuse()
    if value.startswith('minimax-legacy'):_refuse()


def _js_keys(mapping):
    indices=[key for key in mapping if len(key)<=10 and re.fullmatch(r'(?:0|[1-9][0-9]*)',key)
             and int(key)<4294967295]
    indexed=set(indices)
    return sorted(indices,key=int)+[key for key in mapping if key not in indexed]


def _url(value):
    _text(value)
    if not value.isascii():_refuse()
    text=_trim(value)
    if not text:return None
    match=_URL.fullmatch(text)
    if not match or len(match[1])>253 or any(not _HOST_LABEL.fullmatch(label) for label in match[1].split('.')):
        _refuse()
    if re.search(r'%(?![A-Fa-f0-9]{2})',text):_refuse()
    return match[1].lower()


def _scalar(event):
    text=event.value
    if len(text.encode('utf8'))>8192:raise ValueError()
    if event.style is not None:return text
    if text in ('','~','null','Null','NULL'):return None
    if text in ('true','True','TRUE'):return True
    if text in ('false','False','FALSE'):return False
    if re.fullmatch(r'-?(?:0|[1-9][0-9]*)',text):
        if len(text)>17:raise ValueError()
        value=int(text)
        if abs(value)>9007199254740991:raise ValueError()
        return value
    numeric=r'[-+]?(?:[0-9][0-9_]*(?:\.[0-9_]*)?(?:[eE][-+]?[0-9]+)?|\.[0-9_]+(?:[eE][-+]?[0-9]+)?|0[xX][0-9a-fA-F_]+|0[oObB][0-9_]+)'
    if re.fullmatch(numeric,text) or re.match(r'[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:$|[Tt ])',text) or \
            text.lower() in ('.inf','+.inf','-.inf','.nan'):
        raise ValueError()
    return text


def _yaml(raw):
    if type(raw) is not bytes or len(raw)>65536:_refuse()
    failed=False;stream=None
    try:
        text=raw.decode('utf8')
        stream=yaml.parse(text,Loader=yaml.BaseLoader)
        nodes=0
        def node(event,depth):
            nonlocal nodes
            nodes+=1
            if nodes>2048 or depth>8 or getattr(event,'anchor',None) is not None or getattr(event,'tag',None) is not None:
                raise ValueError()
            if isinstance(event,ev.ScalarEvent):return _scalar(event)
            if isinstance(event,ev.MappingStartEvent):
                result={}
                while True:
                    key_event=next(stream)
                    if isinstance(key_event,ev.MappingEndEvent):return result
                    key=node(key_event,depth+1)
                    if type(key) is not str or not 0<len(key)<=256 or not key.isascii() or not key.isprintable() or key in _BAD_KEYS or key in result:
                        raise ValueError()
                    result[key]=node(next(stream),depth+1)
            if isinstance(event,ev.SequenceStartEvent):
                result=[]
                while True:
                    child=next(stream)
                    if isinstance(child,ev.SequenceEndEvent):return result
                    result.append(node(child,depth+1))
            raise ValueError()
        if not isinstance(next(stream),ev.StreamStartEvent):raise ValueError()
        start=next(stream)
        if isinstance(start,ev.StreamEndEvent):value={}
        else:
            if not isinstance(start,ev.DocumentStartEvent) or start.tags or start.version not in (None,(1,2)):
                raise ValueError()
            value=node(next(stream),1)
            if not isinstance(next(stream),ev.DocumentEndEvent) or not isinstance(next(stream),ev.StreamEndEvent):raise ValueError()
        if type(value) is not dict:raise ValueError()
    except (ValueError,yaml.YAMLError,StopIteration,RecursionError):failed=True
    finally:
        if stream is not None:stream.close()
    if failed:_refuse()
    return value


def _headers(value,counts):
    if type(value) is not dict:_refuse()
    for key,text in value.items():
        if not _HEADER.fullmatch(key):_refuse()
        _text(text);counts[1]+=1


def _options(value,counts):
    counts[2]+=_unparsed(value,('apiKey','baseURL','authMode','headers','allowManagedBaseURLOverride'))
    if 'apiKey' in value:_text(value['apiKey']);counts[0]+=1
    if 'baseURL' in value:_url(value['baseURL'])
    if 'authMode' in value and value['authMode'] not in ('managed-login','api-key','oauth'):_refuse()
    if 'headers' in value:_headers(value['headers'],counts)
    if 'allowManagedBaseURLOverride' in value:_boolean(value['allowManagedBaseURLOverride'])


def _schema(value):
    unknown_sections=_unparsed(value,('provider','custom_provider','minimax_api','minimaxModelSource','defaultModel','beta'))
    counts=[0,0,unknown_sections]
    for family in ('provider','custom_provider'):
        entries=value.get(family,{})
        if type(entries) is not dict:_refuse()
        for name,provider in entries.items():
            _name(name)
            counts[2]+=_unparsed(provider,('name','npm','api','kind','enabled','options','models'))
            for field in ('name','npm','api'):
                if field in provider:_text(provider[field])
            if 'kind' in provider and provider['kind'] not in ('custom','oauth'):_refuse()
            if 'enabled' in provider:_boolean(provider['enabled'])
            if 'options' in provider:_options(provider['options'],counts)
            models=provider.get('models',{})
            if type(models) is not dict:_refuse()
            for model,config in models.items():
                _name(model,True);counts[2]+=_unparsed(config,('enabled','headers'))
                if 'enabled' in config:_boolean(config['enabled'])
                if 'headers' in config:_headers(config['headers'],counts)
    if 'minimax_api' in value:
        api=value['minimax_api'];counts[2]+=_unparsed(api,('apiKey','baseURL','modelContextLimits'))
        if 'apiKey' in api:_text(api['apiKey']);counts[0]+=1
        if 'baseURL' in api:_url(api['baseURL'])
        if 'modelContextLimits' in api:
            limits=api['modelContextLimits']
            if type(limits) is not dict:_refuse()
            for model,limit in limits.items():
                _name(model,True)
                if type(limit) is not int or not 0<limit<=9007199254740991:_refuse()
    if value.get('minimaxModelSource','token_plan') not in ('token_plan','minimax_api_key'):_refuse()
    if 'defaultModel' in value:_text(value['defaultModel'])
    if 'beta' in value:
        counts[2]+=_unparsed(value['beta'],('codexOAuth',))
        if 'codexOAuth' in value['beta']:_boolean(value['beta']['codexOAuth'])
    return counts,unknown_sections


@dataclass(frozen=True,slots=True,repr=False)
class SelectionHypothesis:
    resolver:str
    region:str
    preset_models:tuple
    preset_default_model:str
    api_models:tuple
    managed_runtime:bool
    managed_bearer_present:bool
    selection_source:str
    require_catalog:bool
    check_availability:bool
    allow_custom_prefix_fallback:bool
    reference:str
    build_env:str='prod'

    def __post_init__(self):
        if any(type(value) is not str for value in (self.resolver,self.region,self.build_env,self.selection_source)):_refuse()
        if self.resolver not in ('OD','MI') or self.region not in ('en','cn') or self.build_env!='prod' or \
                self.selection_source not in ('runtime-default','host-model-ref'):_refuse()
        for flag in (self.managed_runtime,self.managed_bearer_present,self.require_catalog,
                     self.check_availability,self.allow_custom_prefix_fallback):_boolean(flag)
        if self.selection_source=='runtime-default' and (self.require_catalog or self.allow_custom_prefix_fallback):_refuse()
        for names in (self.preset_models,self.api_models):
            if type(names) is not tuple or len(names)>64:_refuse()
            for name in names:_name(name,True)
            if len(set(names))!=len(names):_refuse()
            if tuple(_js_keys(dict.fromkeys(names)))!=names:_refuse()
        if self.api_models!=self.preset_models:_refuse()
        _name(self.preset_default_model,True)
        if self.managed_runtime and self.preset_default_model not in self.preset_models:_refuse()
        if type(self.reference) is not str or not 0<len(self.reference)<=256 or not _trim(self.reference) or not self.reference.isascii() or not self.reference.isprintable():_refuse()


@dataclass(frozen=True,slots=True)
class ConditionalSelection:
    outcome:str
    route:str
    credential_source:str
    fallback:bool
    configured_key_fields:int
    stored_header_fields:int
    host_key_fields:int
    resolver:str
    hypothesis_fingerprint:str
    effective_header_fields:int|None=None
    unresolved_http_auth:bool=False
    unknown_sections:int=0
    unparsed_config_fields:int=0
    unparsed_model_ref_fields:int=0


def _hypothesis_fingerprint(context):
    values=tuple((field.name,getattr(context,field.name)) for field in fields(context) if field.name!='reference')
    encoded=json.dumps((_SOURCES,values),ensure_ascii=True,separators=(',',':')).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def _identity(provider,model):
    _text(provider);_text(model);provider=_trim(provider);model=_trim(model)
    if provider.startswith('custom_provider:'):_name(provider[len('custom_provider:'):])
    else:_name(provider)
    _name(model,True)
    return provider,model


def _model(config,provider,model,ctx):
    if provider=='minimax_api' or provider=='minimax' and config.get('minimaxModelSource')=='minimax_api_key':
        return {} if model in ctx.api_models else None
    if provider.startswith('custom_provider:'):
        return config.get('custom_provider',{}).get(provider.split(':',1)[1],{}).get('models',{}).get(model)
    return config['provider'].get(provider,{}).get('models',{}).get(model)


def _migration_fence(config,ctx):
    if not ctx.managed_runtime:return
    for name,provider in config.get('provider',{}).items():
        if name in ('minimax','minimax_api'):continue
        options=provider.get('options',{})
        if type(provider.get('models')) is dict and _trim(options.get('apiKey','')) and _trim(options.get('baseURL','')):
            _refuse()


def _competing_auth(headers):
    return any(name.lower() in _AUTH_HEADERS and value is not _BEARER for name,value in headers.items())


@dataclass(frozen=True,slots=True)
class MCodeConfigParser:
    version:str
    config_bundle_sha256:str
    od_bundle_sha256:str
    mi_bundle_sha256:str

    def __post_init__(self):
        for value,expected in zip((self.version,self.config_bundle_sha256,self.od_bundle_sha256,self.mi_bundle_sha256),_SOURCES):
            if type(value) is not str or value!=expected:_refuse()
        if yaml.__version__!='6.0.3':_refuse()

    def analyze(self,raw,context,model_ref_json=None):
        if type(context) is not SelectionHypothesis:_refuse()
        context.__post_init__()
        fingerprint=_hypothesis_fingerprint(context)
        config=_yaml(raw);counts,unknown_sections=_schema(config);_migration_fence(config,context)
        ref={};host_keys=0;unparsed_ref=0
        if context.selection_source=='host-model-ref':
            failed=False
            try:ref=_load(model_ref_json)
            except RecordError:failed=True
            if failed:_refuse()
            unparsed_ref=_unparsed(ref,('provider','model_id','api_key','base_url'))
            if 'provider' not in ref or 'model_id' not in ref:_refuse()
            if 'api_key' in ref:_text(ref['api_key']);host_keys=1
            if 'base_url' in ref:_url(ref['base_url'])
            provider,model=_identity(ref['provider'],ref['model_id'])
        else:
            if model_ref_json is not None:_refuse()
            selection=_trim(config.get('defaultModel','minimax/'+context.preset_default_model))
            parts=selection.split('/',1)
            if len(parts)!=2:_refuse()
            provider,model=_identity(*parts)
        raw_providers=config.get('provider',{})
        providers=dict(raw_providers);providers.pop('minimax_api',None)
        existing=providers.get('minimax',{});options=existing.get('options',{})
        if context.managed_runtime or options.get('authMode')=='managed-login' or _url(options.get('baseURL','')) in _MANAGED:
            base='https://'+('agent.minimax.io' if context.region=='en' else 'agent.minimax.cn')+'/mavis/api/v1/llm/v1'
            effective={'authMode':'managed-login','apiKey':'sk-xxx','baseURL':base,**options}
            if context.managed_runtime:
                if options.get('baseURL','') and _url(options['baseURL']) not in _MANAGED:effective['apiKey']='sk-xxx'
                effective.update(authMode='managed-login',baseURL=base)
            providers['minimax']={**existing,'options':effective,
                'models':existing.get('models') or {name:{} for name in context.preset_models}}
        config={**config,'provider':providers}
        if context.allow_custom_prefix_fallback and provider!='minimax' and provider not in providers and ':' not in provider and \
                _model(config,provider,model,context) is None and \
                _model(config,'custom_provider:'+provider,model,context) is not None:
            provider='custom_provider:'+provider
        def result(outcome='error',route='none',source='none',fallback=False,headers=None,unresolved=False):
            if counts[2] or unparsed_ref:
                outcome='unresolved';route='unresolved';fallback=False;headers=None;unresolved=True
                source='unparsed-input' if counts[2] and unparsed_ref else ('unparsed-config' if counts[2] else 'unparsed-model-ref')
            return ConditionalSelection(outcome=outcome,route=route,credential_source=source,fallback=fallback,
                configured_key_fields=counts[0],stored_header_fields=counts[1],host_key_fields=host_keys,
                resolver=context.resolver,hypothesis_fingerprint=fingerprint,effective_header_fields=headers,
                unresolved_http_auth=unresolved,unknown_sections=unknown_sections,
                unparsed_config_fields=counts[2],unparsed_model_ref_fields=unparsed_ref)
        entry=_model(config,provider,model,context)
        if context.require_catalog and (entry is None or entry.get('enabled') is False):return result()
        if context.check_availability:
            disabled=provider.startswith('custom_provider:') and config.get('custom_provider',{}).get(provider.split(':',1)[1],{}).get('enabled') is False
            if disabled or entry is None or entry.get('enabled') is False:return result()
        fallback=False
        def api_plan():
            block=config.get('minimax_api')
            if block is None:return None
            if not _trim(block.get('apiKey','')):return result(fallback=fallback)
            return result('conditional','minimax_api_key','config-key',fallback)
        if provider=='minimax_api' or provider.startswith('custom_provider:'):
            plan=None
            if provider=='minimax_api':plan=api_plan()
            else:
                custom=config.get('custom_provider',{}).get(provider.split(':',1)[1])
                if custom is not None and custom.get('enabled') is not False and model in custom.get('models',{}):
                    options=custom.get('options',{})
                    if not _trim(options.get('baseURL','')):return result()
                    if custom.get('kind')=='oauth' or options.get('authMode')=='oauth':
                        return result('unresolved','oauth' if provider=='custom_provider:openai-codex' else 'custom_provider','pi-auth-unparsed')
                    if not _trim(options.get('apiKey','')):return result()
                    merged={}
                    for layer in (options.get('headers',{}),custom['models'][model].get('headers',{})):
                        for name,value in layer.items():merged[name.lower()]=value
                    return result('conditional','custom_provider','config-key',headers=len(merged),unresolved=_competing_auth(merged))
            if plan is not None:return plan
            if context.resolver=='MI':return result()
            candidates=[(name,tuple(_js_keys(providers[name].get('models',{})))) for name in _js_keys(providers)]
            candidates.sort(key=lambda pair:pair[0]!='minimax')
            chosen=next(((name,models[0]) for name,models in candidates if models),None)
            if chosen is None:return result()
            provider,model=chosen;ref={};fallback=True
        if provider=='minimax' and config.get('minimaxModelSource')=='minimax_api_key':
            plan=api_plan()
            if plan is not None:return plan
            if context.resolver=='MI':return result(fallback=fallback)
        options=providers.get(provider,{}).get('options',{})
        url=_trim(ref.get('base_url','')) or _trim(options.get('baseURL',''))
        origin=_url(url)
        mode=options.get('authMode') or ('managed-login' if origin in _MANAGED else 'api-key')
        if provider=='openai-codex':return result('unresolved','oauth','pi-auth-unparsed',fallback)
        host_key=_trim(ref.get('api_key',''));key=host_key or _trim(options.get('apiKey',''))
        if mode=='managed-login' and not key:key='sk-xxx'
        headers={**options.get('headers',{}),**providers.get(provider,{}).get('models',{}).get(model,{}).get('headers',{})}
        if mode=='managed-login' and context.managed_bearer_present:headers['Authorization']=_BEARER
        if not key or not url or mode=='managed-login' and origin not in _MANAGED:return result(fallback=fallback)
        if mode=='managed-login' and key=='sk-xxx' and not headers.get('Authorization'):return result(fallback=fallback)
        collision=len({name.lower() for name in headers})!=len(headers)
        source='host-key' if host_key else 'config-key'
        if not host_key and key=='sk-xxx' and provider=='minimax' and \
                'apiKey' not in raw_providers.get(provider,{}).get('options',{}):source='preset-placeholder'
        if mode=='managed-login':
            source='managed-bearer-assumed' if key=='sk-xxx' and context.managed_bearer_present else 'mixed-assumed'
            unresolved=collision or key!='sk-xxx' or not context.managed_bearer_present or _competing_auth(headers)
            return result('conditional','token_plan',source,fallback,len(headers),unresolved)
        return result('conditional','oauth' if mode=='oauth' else 'provider_api_key',source,fallback,
                      len(headers),collision or _competing_auth(headers))
