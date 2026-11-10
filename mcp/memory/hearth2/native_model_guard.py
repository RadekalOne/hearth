"""Inactive root-supplied exact-model gate before a Codex thread/start.

No process, turn, credential, service or retry is created here. A concrete trusted
launcher must use this boundary, supply the mounted artifact pins and a fresh
complete model/list response, and acknowledge a durable audit before transport.
Mount immutability, freshness and claim/lease authority remain launcher duties.
"""
import hashlib
import json
import os
import re
import stat

_ALLOWED_MODEL = 'gpt-6.1-sol'
_MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z')
_MAX_BINARY = 600_000_000
_MAX_CATALOG = 1_000_000
_FIXED_REQUEST = (('cwd', '/scratch'), ('approvalPolicy', 'never'),
                  ('sandbox', 'read-only'), ('ephemeral', True))
_REQUEST_KEYS = frozenset(('model', *(key for key, _ in _FIXED_REQUEST)))


class ModelSelectionRefused(RuntimeError):
    def __init__(self, decision):
        self.decision = dict(decision)
        super().__init__(decision['reason'])


class ModelAuditUnavailable(RuntimeError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise ValueError('duplicate catalog field')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite catalog field')


def _request_allowed(params):
    if (any(type(key) is not str for key in params)
            or set(params) != _REQUEST_KEYS):
        return False
    return all(type(params[key]) is type(value) and params[key] == value
               for key, value in _FIXED_REQUEST)


def _identities(entries, field):
    if type(entries) is not list or not 1 <= len(entries) <= 128:
        raise ValueError('bounded complete catalog required')
    result = set()
    for entry in entries:
        if type(entry) is not dict: raise ValueError('model object required')
        value = entry.get(field)
        if type(value) is not str or not _MODEL.fullmatch(value) or value in result:
            raise ValueError('invalid or duplicate identity')
        if field == 'model' and 'id' in entry and entry['id'] != value:
            raise ValueError('ambiguous identity')
        result.add(value)
    return result


def _check(requested, mounted_binary, binary_pin, catalog_pin, model_list, evidence):
    if type(requested) is not str or requested != _ALLOWED_MODEL:
        return 'model_not_allowed'
    try:
        fd = os.open(mounted_binary, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            meta = os.fstat(stream.fileno())
            if not stat.S_ISREG(meta.st_mode) or not 1 <= meta.st_size <= _MAX_BINARY:
                return 'binary_unavailable'
            raw = stream.read(meta.st_size+1)
            if len(raw) != meta.st_size: return 'binary_unavailable'
    except (OSError, TypeError, ValueError):
        return 'binary_unavailable'
    evidence['binary_sha256'] = hashlib.sha256(raw).hexdigest()
    if evidence['binary_sha256'] != binary_pin: return 'binary_pin_mismatch'
    try:
        marker = raw.index(b'{\n  "models": [')
        text = raw[marker:marker+_MAX_CATALOG].decode('utf-8', errors='surrogateescape')
        catalog, end = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_constant).raw_decode(text)
        evidence['catalog_sha256'] = hashlib.sha256(text[:end].encode('utf-8')).hexdigest()
        if evidence['catalog_sha256'] != catalog_pin: return 'catalog_pin_mismatch'
        identities = _identities(catalog['models'], 'slug')
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return 'mounted_catalog_invalid'
    if _ALLOWED_MODEL not in identities: return 'allowed_model_missing_from_binary'
    try:
        if type(model_list) is not dict or model_list.get('nextCursor') is not None:
            raise ValueError('incomplete client catalog')
        identities = _identities(model_list['data'], 'model')
    except (ValueError, TypeError, KeyError):
        return 'client_catalog_invalid'
    if _ALLOWED_MODEL not in identities: return 'allowed_model_missing_from_client'
    return None


def start_codex_thread(request, *, mounted_binary, expected_binary_sha256,
                       expected_catalog_sha256, model_list, record_decision,
                       thread_start):
    """Audit allow/refuse, then invoke the trusted thread transport at most once.

    record_decision must return exactly True after durable persistence. Failure
    or missing acknowledgement aborts before transport. No human decision/card
    schema is used. Downstream transport/provider errors remain downstream errors;
    they are never reclassified as this pre-thread model-selection refusal.
    """
    params = dict(request) if type(request) is dict else {}
    requested = params.get('model')
    evidence = {'binary_sha256': None, 'catalog_sha256': None}
    try:
        reason = ('request_fields_not_allowed' if not _request_allowed(params)
                  else _check(requested, mounted_binary, expected_binary_sha256,
                              expected_catalog_sha256, model_list, evidence))
    except Exception:
        # Only guard evaluation is covered: audit and transport errors stay
        # outside this catch. Never echo an unexpected exception's raw text.
        reason = 'guard_error'
    decision = {'kind': 'native_model_selection', 'allowed_model': _ALLOWED_MODEL,
        'requested_model': requested if type(requested) is str and _MODEL.fullmatch(requested) else None,
        'outcome': 'refused' if reason else 'allowed',
        'reason': reason or 'exact_model_in_both_catalogs',
        'failure_class': ('guard_error' if reason == 'guard_error'
                          else 'model_selection' if reason else None), **evidence}
    if record_decision(dict(decision)) is not True:
        raise ModelAuditUnavailable('durable model decision acknowledgement required')
    if reason: raise ModelSelectionRefused(decision)
    return thread_start(params)
