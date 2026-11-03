"""Pure, bounded MiniMax input syntax classification; never inventory authority.

Inputs must be acquired and bound independently. No file, environment, helper,
provider, OAuth or extension access occurs here. Counts cannot prove absence.
"""
from dataclasses import dataclass
import json
import re

from .store import RecordError


_VERSION = '0.4.1'
_CORE = 'ab278b848d10c3b8721fc00f76512994f39db9eba6691492b74c2135afa2703b'
_MCODE_RESOLVER = '7f91af66b8692739662669da6a04ba294d9da871bb667b19ce6ff98cddd42e73'
_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
_HEADER = re.compile(r"[!#$%&'*+\-.^_`|~A-Za-z0-9]+", re.ASCII)


def _refuse():
    raise RecordError('unsupported MiniMax consumer input') from None


class _InvalidJSON(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJSON()
        result[key] = value
    return result


def _number(_):
    raise _InvalidJSON()


def _load(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 65536:
        _refuse()
    failed = False
    try:
        text = raw.decode('utf-8', errors='strict')
        # Bound nesting BEFORE json.loads allocates recursive containers.
        depth = 0
        quoted = escaped = False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in '[{':
                depth += 1
                if depth > 8:
                    raise _InvalidJSON()
            elif char in ']}':
                depth -= 1
        value = json.loads(text, object_pairs_hook=_pairs,
                           parse_constant=_number, parse_float=_number)
        pending = [value]
        nodes = 0
        while pending:
            item = pending.pop()
            nodes += 1
            if nodes > 2048:
                raise _InvalidJSON()
            if isinstance(item, str):
                if len(item.encode('utf-8', errors='strict')) > 8192:
                    raise _InvalidJSON()
            elif isinstance(item, dict):
                for key, child in item.items():
                    if not 0 < len(key) <= 256 or not key.isascii() or not key.isprintable():
                        raise _InvalidJSON()
                    pending.extend((key, child))
            elif isinstance(item, list):
                pending.extend(item)
        if type(value) is not dict:
            raise _InvalidJSON()
    except (ValueError, RecursionError, OverflowError):
        failed = True
    # Raise outside the handler: no secret-bearing decoder exception context.
    if failed:
        _refuse()
    return value


def _expression(value):
    """Native BC/mZe grammar; inspect syntax only, do not construct a result."""
    if not value:
        return 'empty', 0
    if value.startswith('!'):
        return 'command', 0
    index = references = 0
    while index < len(value):
        dollar = value.find('$', index)
        if dollar < 0:
            break
        following = value[dollar + 1:dollar + 2]
        if following in ('$', '!'):
            index = dollar + 2
        elif following == '{':
            end = value.find('}', dollar + 2)
            if end < 0:
                index = dollar + 1
            else:
                if _IDENTIFIER.fullmatch(value[dollar + 2:end]):
                    references += 1
                index = end + 1
        else:
            match = _IDENTIFIER.match(value, dollar + 1)
            if match:
                references += 1
                index = match.end()
            else:
                index = dollar + 1
    return ('environment' if references else 'literal'), references


@dataclass(frozen=True, slots=True)
class ConsumerSyntax:
    """Value-free syntax counts only; no complete/absence/proof fields."""
    source_kind: str
    literal_fields: int = 0
    empty_fields: int = 0
    environment_fields: int = 0
    command_fields: int = 0
    environment_references: int = 0
    unknown_records: int = 0


def _summary(kind, values, *, expressions, unknown=0):
    counts = dict(literal_fields=0, empty_fields=0, environment_fields=0,
                  command_fields=0, environment_references=0, unknown_records=unknown)
    for value in values:
        if expressions:
            field, refs = _expression(value)
        else:
            field, refs = ('literal' if value else 'empty'), 0
        counts[field + '_fields'] += 1
        counts['environment_references'] += refs
    return ConsumerSyntax(kind, **counts)


@dataclass(frozen=True, slots=True)
class MiniMaxConsumerParser:
    version: str
    core_bundle_sha256: str

    def __post_init__(self):
        if type(self.version) is not str or self.version != _VERSION or \
                type(self.core_bundle_sha256) is not str or self.core_bundle_sha256 != _CORE:
            _refuse()

    def pi_auth_json(self, raw):
        values = []
        unknown = 0
        for record in _load(raw).values():
            if type(record) is dict and set(record) == {'type', 'key'} and \
                    record['type'] == 'api_key' and type(record['key']) is str:
                values.append(record['key'])
            else:
                unknown += 1
        return _summary('pi-auth-json', values, expressions=True, unknown=unknown)

    def pi_headers_json(self, raw):
        return self._string_map(raw, 'pi-headers-json', expressions=True, names=_HEADER)

    def pi_runtime_overrides_json(self, raw):
        return self._string_map(raw, 'pi-runtime-overrides-json', expressions=False)

    def mcode_headers_json(self, raw, *, resolver_bundle_sha256):
        if type(resolver_bundle_sha256) is not str or resolver_bundle_sha256 != _MCODE_RESOLVER:
            _refuse()
        return self._string_map(raw, 'mcode-headers-json', expressions=False, names=_HEADER)

    def environment_json(self, raw):
        return self._string_map(raw, 'environment-json', expressions=False, names=_IDENTIFIER)

    @staticmethod
    def _string_map(raw, kind, *, expressions, names=None):
        data = _load(raw)
        if any(type(value) is not str or (names is not None and not names.fullmatch(key))
               for key, value in data.items()):
            _refuse()
        return _summary(kind, data.values(), expressions=expressions)
