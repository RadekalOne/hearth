"""Immutable root creation identity; no OS creation, guard arming or launch.

Collectors remain trusted. A stored host fingerprint is meaningful only when
the independent collector authenticates the original host, not a restored DB's
current machine. The journal is exported unchanged across restore.
"""
import hashlib
import json
import re
from .store import RecordError, safe_payload, timestamp


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def read_binding(db, run_id):
    row = db.execute("SELECT * FROM audit_events WHERE action='creation_bound' AND entity_id=? ORDER BY seq LIMIT 1",
                     (run_id,)).fetchone()
    if row is None:
        return None
    return {**json.loads(row['data']), 'seq':row['seq'], 'at':row['at'], 'controller':row['actor']}


def validate_bound_identity(db, run_id, observation):
    """Legacy unbound records stay compatible; bound records cannot swap hosts."""
    binding = read_binding(db, run_id)
    if binding is not None and any(observation.get(key) != binding[key]
                                  for key in ['host_id', 'container_id', 'workload_id']):
        raise RecordError('proof must target the sealed original host and container')


class CreationRegistry:
    def __init__(self, registry):
        self.registry = registry
        self.store = registry.store
        self.controller = registry.controller

    def read(self, run_id):
        """Status only, including after restore; never reauthorizes launch."""
        with self.store.transaction() as db:
            self.registry._owned(self.registry._latest(db), run_id)
            return read_binding(db, run_id)

    def bind(self, registration, claim, *, host_id, container_id):
        """Seal a root-observed STOPPED container before any guard/consume/start.

        The caller must independently verify stopped state, resource policy and
        actual host/container identity. This method persists that identity, not
        an OS attestation. Unknown partial creates require outside reconciliation.
        """
        if (not _digest(host_id) or not _digest(container_id)
                or not isinstance(registration, dict) or not isinstance(claim, dict)
                or not isinstance(registration.get('run_id'), str)
                or any(type(v) not in {str, int, type(None)} for v in registration.values())):
            raise RecordError('exact creation registration and immutable identities required')
        with self.store.transaction() as db:
            current, _, run = self.store._live_claim(db, self.controller, claim)
            latest = self.registry._owned(self.registry._latest(db), run['id'])
            if (safe_payload(latest) != safe_payload(registration)
                    or latest['phase'] != 'reserved'
                    or latest['claim_id'] != current['id']
                    or latest['restore_epoch'] != current['restore_epoch']
                    or latest['generation'] != current['generation']):
                raise RecordError('creation requires exact reserved current registration')
            # Original epoch, never current restore epoch or a fresh UUID.
            identity = hashlib.sha256(safe_payload({
                'run_id':run['id'], 'creation_epoch':latest['restore_epoch']}).encode()).hexdigest()
            binding = {
                'run_id':run['id'], 'claim_id':current['id'],
                'creation_epoch':latest['restore_epoch'], 'generation':current['generation'],
                'registration_seq':latest['seq'], 'workload_id':latest['workload_id'],
                'host_id':host_id, 'container_id':container_id,
                'guard_id':'hearth2-deadline-' + identity,
                'parent_cgroup':'hearth2-' + identity,
                'deadline_at':latest['deadline_at'], 'policy_sha256':latest['policy_sha256'],
            }
            previous = read_binding(db, run['id'])
            if previous is not None:
                recorded = {k:v for k,v in previous.items() if k not in {'seq','at','controller'}}
                if recorded != binding or previous['controller'] != self.controller.id:
                    raise RecordError('original creation binding is immutable')
                return previous
            self.store.audit(db, self.controller, run['id'], 'creation_bound', binding)
            return read_binding(db, run['id'])

    def consume_armed(self, claim, binding, *, proof):
        """One-use DB launch transition AFTER independent OS guard verification.

        Only the caller receiving a successful commit may proceed to start the
        sealed immutable ID. A crash/lost acknowledgment after commit is held,
        never retried as start. This method performs no OS side effects; the
        guard must remain armed on every exception, timeout and restart.
        """
        identity_fields = {'host_id','container_id','workload_id','guard_id',
                           'parent_cgroup','deadline_at','policy_sha256'}
        fields = identity_fields | {'observed_at','guard_state','container_state','references'}
        if (not isinstance(claim,dict) or not isinstance(binding,dict)
                or not isinstance(proof,dict) or set(proof)!=fields
                or proof['guard_state']!='armed' or proof['container_state']!='created'
                or not isinstance(proof['references'],list) or not 1<=len(proof['references'])<=100
                or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in proof['references'])):
            raise RecordError('fresh armed guard and stopped immutable container proof required')
        observed = timestamp(proof['observed_at'])
        with self.store.transaction() as db:
            current, _, run = self.store._live_claim(db,self.controller,claim)
            sealed = read_binding(db,run['id'])
            if (sealed is None or sealed!=binding or sealed['controller']!=self.controller.id
                    or sealed['claim_id']!=current['id']
                    or sealed['creation_epoch']!=current['restore_epoch']
                    or sealed['generation']!=current['generation']
                    or any(proof[key]!=sealed[key] for key in identity_fields)):
                raise RecordError('guard proof does not match sealed original creation')
            now = self.store.now()
            if (observed>now or (now-observed).total_seconds()>60
                    or observed<timestamp(sealed['at']) or now>=timestamp(sealed['deadline_at'])):
                raise RecordError('guard observation stale or deadline expired')
            # Both journal events commit or neither does; OS guard is untouched.
            self.store.audit(db,self.controller,run['id'],'creation_armed',
                {'binding_seq':sealed['seq'],'proof':proof})
            return self.registry._consume(db,claim)
