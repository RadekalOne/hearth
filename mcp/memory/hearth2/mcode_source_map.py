"""Static 0.4.1 role spellings only. Nothing here grants acquisition or absence."""
from dataclasses import dataclass
import base64
import hashlib
import json
import re

from .store import RecordError

SOURCE_PINS=(
 ('V7D3N7GI','619ff2ee477d5339b7b3f70ab17c500d5618e52c64b53a270adbb0cd523e1e6a'),
 ('6BYKHQOV','b79bf405b47654e4295b918bfc0bf5d84e4f73d3b05197c89c909dedef8f9b9f'),
 ('AAJMOWWM','acf1ff9d270aca155e09b747d3e475a7e48c24bd5f84241d5268c1e3e1155674'),
 ('GOLYEPEW','fc77436612ef5b8d771252eb6f47772e2f4b19ee82e8a815b351f78540f4c9a0'),
 ('4NX3LPKA','0be24cbc0d87177be43f7e7888d85c2209f5565bf92d1fecea5fa12fe451a887'),
 ('2ZG44JU6','a1c8ac338d1b66a9d71bd508f1d30e6c1ea0cf2b20a505b1ef32b2c910bc4c74'))
_ROOT=(('pi-auth',('codex-auth.json',)),('projection-shared',('local-runtime.auth.json',)),
 ('lease-capability',('run','mcode-auth-lease-v1.cap')),('shared-selector',('cli-auth','shared-projection.json')),
 ('region-selector',('preferences','mcode-region.json')),('legacy-encrypted',('auth','credentials.enc')),
 ('mcode-config',('config.yaml',)),('host-model-ref',None),('mcp-consumers',None),('environment',None),
 ('oauth-state',('auth','auth-state.json')))
_ENV=(('projection-legacy','local-runtime.auth.json'),('legacy-scope-marker','cli-auth.scope.json'))
_NAMESPACE=(('oauth-store','auth.json'),('oauth-state','auth-state.json'),
 ('projection-namespaced','local-runtime.auth.json'),('account-identity','account-identity.json'),('scope-marker','cli-auth.scope.json'))
MAP_SHA256=hashlib.sha256(json.dumps(('mcode-source-map-v2','0.4.1',SOURCE_PINS,_ROOT,_ENV,_NAMESPACE),
    separators=(',',':')).encode('ascii')).hexdigest()


def _refuse():raise RecordError('unsupported pinned MCode source map') from None


@dataclass(frozen=True,slots=True,repr=False)
class MapLeaf:
    source_id:str
    kind:str
    path:tuple|None
    build_env:str|None
    region:str|None
    status:str='unscanned'
    acquisition_supported:bool=False


def _slice(value):
    from .data_dir_policy import RootPolicySlice
    if type(value) is not RootPolicySlice:_refuse()
    value.encode()


class MCodeSourceMap:
    @staticmethod
    def expand(root_slice):
        _slice(root_slice)
        rows=[(kind,path,None,None) for kind,path in _ROOT]
        for env in sorted({ns.build_env for ns in root_slice.root.namespaces}):
            rows.extend((kind,('cli-auth',env,name),env,None) for kind,name in _ENV)
        for ns in sorted(root_slice.root.namespaces,key=lambda ns:(ns.build_env,ns.region)):
            for kind,name in _NAMESPACE:
                prefix=('auth',ns.build_env,ns.region,'mcode-public') if kind.startswith('oauth-') else ('cli-auth',ns.build_env,ns.region)
                rows.append((kind,prefix+(name,),ns.build_env,ns.region))
        # Exclusive logical-source cap; never return a truncated prefix.
        if len(rows)>=root_slice.limits[5]:_refuse()
        return tuple(MapLeaf('leaf'+str(i),*row) for i,row in enumerate(rows))

    @staticmethod
    def account_matches(root_slice,build_env,region):
        _slice(root_slice)
        if type(build_env) is not str or type(region) is not str:_refuse()
        ns=next((n for n in root_slice.root.namespaces if (n.build_env,n.region)==(build_env,region)),None)
        if ns is None or ns.account is None:return False
        # POSIX target spelling only; independently supplied expected account is
        # compared, never populated. No Windows path normalization is inferred.
        digest=hashlib.sha256((root_slice.root.path+'/auth\0mcode-public').encode('ascii')).digest()
        return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')==ns.account

    @staticmethod
    def transient(path,kind):
        # Name/type classification only, NEVER an ignore or absence decision.
        if (type(path) is not tuple or not 1<=len(path)<=6 or type(kind) is not str
                or any(type(x) is not str or not 0<len(x)<=256 or x in ('.','..')
                       or any(not 33<=ord(c)<=126 or c in '/\\' for c in x) for x in path)):_refuse()
        parent=path[:-1];name=path[-1]
        auth=len(parent)==4 and parent[0]=='auth' and parent[1] in ('dev','test','staging','prod') and parent[2] in ('cn','en') and parent[3]=='mcode-public'
        legacy_auth=parent==('auth',)
        cli=len(parent) in (2,3) and parent[0]=='cli-auth' and parent[1] in ('dev','test','staging','prod') and (len(parent)==2 or parent[2] in ('cn','en'))
        if kind=='directory':return ((auth or legacy_auth) and name=='auth.lock.lock') or (not parent and name=='config.yaml.lock')
        if kind!='regular':return False
        if (auth or legacy_auth) and name=='auth.lock':return True
        if not parent and re.fullmatch(r'\.config-tmp-[0-9a-f]{12}',name):return True
        if parent==('run',):return re.fullmatch(r'mcode-auth-lease-v1\.cap\.[1-9][0-9]*\.[0-9a-f]{16}\.tmp',name) is not None
        targets=('auth.json','auth-state.json') if auth else (('local-runtime.auth.json','cli-auth.scope.json') if cli else ())
        if legacy_auth:targets=('auth-state.json',)
        if cli and len(parent)==3:targets+=('account-identity.json',)
        if not parent:targets=('local-runtime.auth.json',)
        if parent==('cli-auth',):targets=('shared-projection.json',)
        if parent==('preferences',):targets=('mcode-region.json',)
        return any(re.fullmatch(re.escape(target)+r'\.[1-9][0-9]*\.[0-9]+\.tmp',name) for target in targets)
