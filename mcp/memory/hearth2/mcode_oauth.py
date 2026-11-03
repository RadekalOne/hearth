"""Inactive pure OAuth snapshot parsers. No credentials retained in results.

Identity declarations and syntax counts are not inventory, authentication,
physical acquisition, runtime or start authority. No I/O occurs in this module.
"""
from dataclasses import dataclass, replace
import hmac
import re

from .minimax_consumer import _load
from .store import RecordError


_OAUTH = 'acf1ff9d270aca155e09b747d3e475a7e48c24bd5f84241d5268c1e3e1155674'
_PROJECTION = 'b79bf405b47654e4295b918bfc0bf5d84e4f73d3b05197c89c909dedef8f9b9f'
_ENVS = ('dev', 'test', 'staging', 'prod')
_REGIONS = ('cn', 'en')
_ACCOUNT = re.compile(r'[A-Za-z0-9_-]{43}', re.ASCII)
_STATUSES = ('anonymous', 'authorizing', 'authenticated', 'refreshing',
             'scope_upgrade_required', 'logging_out', 'logout_pending', 'expired', 'error')
_RECORD_REQUIRED = frozenset(('schemaVersion', 'accessToken', 'refreshToken', 'tokenType',
                             'clientId', 'audience', 'scopes', 'expiresAtMs', 'generation'))
_RECORD_OPTIONAL = frozenset(('subject', 'accountId', 'loginEpoch'))
_STATE_REQUIRED = frozenset(('schemaVersion', 'status', 'storeKind', 'clientId', 'audience',
                            'scopes', 'buildEnv', 'region', 'generation'))
_STATE_OPTIONAL = frozenset(('expiresAtMs', 'authorization'))
_PROJECTION_IDENTITIES = frozenset(('realUserID', 'userEmail', 'userName', 'subUserName'))
# ECMAScript WhiteSpace + LineTerminator, independent of Python's Unicode strip.
_JS_TRIM = ('\u0009\u000b\u000c\u0020\u00a0\u1680\u2000\u2001\u2002\u2003'
            '\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000'
            '\ufeff\u000a\u000d\u2028\u2029')


def _refuse():
    raise RecordError('unsupported MCode OAuth input') from None


def _decode(raw, *, key=None):
    failed = False
    try:
        value = _load(raw, oauth_record_key=key)
    except RecordError:
        failed = True
    if failed:
        _refuse()
    return value


def _fields(value, required, optional=frozenset()):
    if type(value) is not dict or not required <= value.keys() or value.keys() - required - optional:
        _refuse()


def _integer(value):
    if type(value) is not int or not 0 <= value <= 9007199254740991:
        _refuse()


def _text(value, *, nonempty=True):
    if type(value) is not str or (nonempty and not value):
        _refuse()


def _contract(value):
    if value['clientId'] != 'mcode-public' or value['audience'] != 'agent-backend' or \
            value['scopes'] != ['agent.default']:
        _refuse()


def _state(raw, build_env, region):
    state = _decode(raw)
    _fields(state, _STATE_REQUIRED, _STATE_OPTIONAL)
    if type(state['schemaVersion']) is not int or state['schemaVersion'] != 2 or \
            state['storeKind'] != 'file' or type(state['status']) is not str or \
            state['status'] not in _STATUSES or state['buildEnv'] != build_env or state['region'] != region:
        _refuse()
    _contract(state)
    _integer(state['generation'])
    if 'expiresAtMs' in state:
        _integer(state['expiresAtMs'])
    material = 0
    if 'authorization' in state:
        if state['status'] != 'authorizing':
            _refuse()
        authorization = state['authorization']
        _fields(authorization, frozenset(('leaseId', 'leaseExpiresAtMs')),
                frozenset(('userCode', 'verificationUri', 'verificationUriComplete')))
        _integer(authorization['leaseExpiresAtMs'])
        for name, value in authorization.items():
            if name != 'leaseExpiresAtMs':
                _text(value, nonempty=(name == 'leaseId'))
                material += 1
    return state, material


@dataclass(frozen=True, slots=True)
class OAuthFileSummary:
    source_kind: str
    access_tokens: int
    refresh_tokens: int
    identity_fields: int
    authorization_fields: int
    expiry_state: str
    state_status: str | None = None
    matches_primary: bool | None = None


@dataclass(frozen=True, slots=True)
class MCodeOAuthParser:
    version: str
    oauth_bundle_sha256: str
    projection_bundle_sha256: str

    def __post_init__(self):
        for value, expected in ((self.version, '0.4.1'), (self.oauth_bundle_sha256, _OAUTH),
                                (self.projection_bundle_sha256, _PROJECTION)):
            if type(value) is not str or value != expected:
                _refuse()

    def _store(self, auth_raw, state_raw, *, build_env, region, account, now_ms):
        if type(build_env) is not str or build_env not in _ENVS or \
                type(region) is not str or region not in _REGIONS or \
                type(account) is not str or not _ACCOUNT.fullmatch(account):
            _refuse()
        _integer(now_ms)
        key = 'com.minimax.mcode.oauth.' + build_env + '.' + region + '\0' + account
        payload = _decode(auth_raw, key=key)
        _fields(payload, frozenset(('schemaVersion', 'records')))
        if type(payload['schemaVersion']) is not int or payload['schemaVersion'] != 1 or \
                type(payload['records']) is not dict or payload['records'].keys() - {key}:
            _refuse()
        state, material = _state(state_raw, build_env, region)
        record = payload['records'].get(key)
        if record is None and key in payload['records']:
            _refuse()
        if record is None:
            if state['status'] in ('authenticated', 'refreshing', 'expired', 'scope_upgrade_required'):
                _refuse()
            return OAuthFileSummary('mcode-oauth-files', 0, 0, 0, material, 'absent', state['status']), None
        _fields(record, _RECORD_REQUIRED, _RECORD_OPTIONAL)
        if type(record['schemaVersion']) is not int or record['schemaVersion'] != 1 or \
                record['tokenType'] != 'Bearer':
            _refuse()
        _contract(record)
        for name in ('accessToken', 'refreshToken'):
            _text(record[name])
        for name in _RECORD_OPTIONAL & record.keys():
            _text(record[name], nonempty=False)
        _integer(record['generation'])
        _integer(record['expiresAtMs'])
        if record['generation'] != state['generation'] or record['expiresAtMs'] != state.get('expiresAtMs'):
            _refuse()
        return OAuthFileSummary('mcode-oauth-files', 1, 1,
            len(_RECORD_OPTIONAL & record.keys()), material,
            'expired' if record['expiresAtMs'] <= now_ms else 'future', state['status']), record

    def store_json(self, auth_raw, state_raw, *, build_env, region, account, now_ms):
        summary, _ = self._store(auth_raw, state_raw, build_env=build_env,
                                region=region, account=account, now_ms=now_ms)
        return summary

    @staticmethod
    def _projection(raw, source_kind):
        if type(source_kind) is not str or source_kind not in ('namespaced', 'legacy', 'shared'):
            _refuse()
        payload = _decode(raw)
        _fields(payload, frozenset(('version', 'updatedAtMs', 'auth')))
        if type(payload['version']) is not int or payload['version'] != 1:
            _refuse()
        _integer(payload['updatedAtMs'])
        auth = payload['auth']
        _fields(auth, frozenset(('accessToken',)), _PROJECTION_IDENTITIES)
        _text(auth['accessToken'])
        token = auth['accessToken'].strip(_JS_TRIM)
        if not token:
            _refuse()
        for name in _PROJECTION_IDENTITIES & auth.keys():
            _text(auth[name], nonempty=False)
        return OAuthFileSummary('mcode-projection-' + source_kind, 1, 0,
            len(_PROJECTION_IDENTITIES & auth.keys()), 0, 'unknown'), token

    def projection_json(self, raw, *, source_kind):
        summary, _ = self._projection(raw, source_kind)
        return summary

    def compare_projection(self, auth_raw, state_raw, projection_raw, *, source_kind,
                           build_env, region, account, now_ms):
        _, record = self._store(auth_raw, state_raw, build_env=build_env,
            region=region, account=account, now_ms=now_ms)
        summary, token = self._projection(projection_raw, source_kind)
        matched = record is not None and hmac.compare_digest(
            record['accessToken'].encode('utf8'), token.encode('utf8'))
        return replace(summary, matches_primary=matched)
