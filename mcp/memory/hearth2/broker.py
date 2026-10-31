"""Ephemeral, read-only memory capabilities; no worker receives upstream auth.

This is a controller library, not an active service or native-tool sandbox.
The trusted transport supplies the controller principal and upstream callback.
"""
import hashlib
import json
import re
import secrets
import threading
from dataclasses import dataclass
from .store import RecordError, require, safe_payload, text, timestamp


class BrokerError(RecordError):
    pass


@dataclass(frozen=True)
class Grant:
    claim: dict
    wing: str
    room: str
    expires_at: str


class Broker:
    def __init__(self, store, controller, upstream):
        require(controller, {'controller'})
        self.store, self.controller, self._upstream = store, controller, upstream
        self._grants = {}
        self._lock = threading.RLock()

    def _controller(self, actor):
        if actor != self.controller:
            raise BrokerError('broker controller required')

    @staticmethod
    def _digest(token):
        if not isinstance(token, str) or re.fullmatch(r'[0-9a-f]{64}', token) is None:
            raise BrokerError('capability unavailable')
        return hashlib.sha256(token.encode()).digest()

    def _live(self, grant):
        try:
            if self.store.now() >= timestamp(grant.expires_at):
                raise RecordError('expired')
            with self.store.transaction() as db:
                current, task, run = self.store._live_claim(db, self.controller, grant.claim)
                # BEGIN IMMEDIATE may wait behind another writer. A renewed
                # authoritative lease must not extend this grant's fixed expiry.
                now = self.store.now()
                if min(timestamp(grant.expires_at),timestamp(current['lease_until']),timestamp(run['deadline_at'])) <= now:
                    raise RecordError('expired')
        except Exception:
            # Do not expose database, claim, upstream or credential diagnostics.
            raise BrokerError('capability unavailable') from None

    def mint(self, actor, claim, *, wing, room):
        self._controller(actor)
        try:
            wing, room = text(wing, 'wing', 240), text(room, 'room', 240)
            bound = json.loads(safe_payload(claim))
            with self.store.transaction() as db:
                current, task, run = self.store._live_claim(db, self.controller, bound)
                expiry = min(timestamp(current['lease_until']), timestamp(run['deadline_at'])).isoformat()
            grant = Grant(bound, wing, room, expiry)
        except Exception:
            raise BrokerError('capability unavailable') from None
        with self._lock:
            for key, old in list(self._grants.items()):
                try:
                    self._live(old)
                except BrokerError:
                    del self._grants[key]
            if self._grants:
                raise BrokerError('one active capability permitted')
            self._live(grant)
            token = secrets.token_hex(32)
            self._grants[self._digest(token)] = grant
            return token

    def revoke(self, actor, token):
        self._controller(actor)
        with self._lock:
            self._grants.pop(self._digest(token), None)

    def _authorized(self, digest, grant):
        with self._lock:
            if self._grants.get(digest) is not grant:
                raise BrokerError('capability unavailable')
            self._live(grant)

    def check(self, token):
        digest = self._digest(token)
        with self._lock:
            grant = self._grants.get(digest)
            if grant is None:
                raise BrokerError('capability unavailable')
        self._authorized(digest, grant)

    @staticmethod
    def _arguments(tool, arguments, grant):
        if not isinstance(arguments, dict):
            raise BrokerError('invalid read request')
        if tool == 'memory_search' and set(arguments) <= {'query', 'limit'}:
            query = text(arguments.get('query'), 'query', 4096)
            limit = arguments.get('limit', 5)
            if type(limit) is not int or not 1 <= limit <= 10:
                raise BrokerError('invalid read request')
            return dict(query=query, limit=limit, wing=grant.wing, room=grant.room)
        if tool == 'memory_get' and set(arguments) == {'drawer_id'}:
            key = arguments['drawer_id']
            if isinstance(key, str) and re.fullmatch(r'drawer_[A-Za-z0-9_-]{1,128}', key):
                return {'drawer_id':key}
        raise BrokerError('read tool or scope not permitted')

    @staticmethod
    def _result(tool, arguments, result, grant):
        result = json.loads(safe_payload(result))
        def scoped(row):
            if (not isinstance(row, dict) or row.get('wing') != grant.wing
                    or row.get('room') != grant.room or not isinstance(row.get('drawer_id'), str)):
                raise BrokerError('memory response unavailable')
            return row
        if tool == 'memory_get':
            row = scoped(result)
            if row['drawer_id'] != arguments['drawer_id']:
                raise BrokerError('memory response unavailable')
            return row
        if not isinstance(result, dict) or not isinstance(result.get('results'), list) or len(result['results']) > arguments['limit']:
            raise BrokerError('memory response unavailable')
        # Release scoped records only, never global upstream counts or metadata.
        return {'results':[scoped(row) for row in result['results']]}

    def read(self, token, tool, arguments):
        digest = self._digest(token)
        with self._lock:
            grant = self._grants.get(digest)
            if grant is None:
                raise BrokerError('capability unavailable')
        self._authorized(digest, grant)
        try:
            forwarded = self._arguments(tool, arguments, grant)
            result = self._result(tool, forwarded, self._upstream(tool, forwarded), grant)
        except Exception:
            raise BrokerError('memory read unavailable') from None
        # Revocation/expiry while upstream was reading must withhold its response.
        self._authorized(digest, grant)
        return result
