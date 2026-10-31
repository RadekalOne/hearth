"""Durable launch intent for a trusted controller, not a process launcher.

The immutable journal holds the one instance-wide slot across restarts. A
successful consume commits before a future launcher may act; replay never
authorizes another launch. A crash in that gap requires reconciliation rather
than a retry. No credential, executable, host path or worker command is stored.
"""
import json
import hashlib
import re
from .store import RecordError, require, safe_payload, native_receipt_metadata


class DispatchRegistry:
    def __init__(self, store, controller):
        require(controller, {'controller'})
        self.store, self.controller = store, controller

    @staticmethod
    def _latest(db):
        latest = {}
        for row in db.execute("SELECT * FROM audit_events WHERE action='dispatch' ORDER BY seq DESC"):
            if row['entity_id'] not in latest:
                latest[row['entity_id']] = {
                    **json.loads(row['data']), 'seq':row['seq'],
                    'at':row['at'], 'controller':row['actor']}
        return latest

    def _append(self, db, data):
        # Journal metadata is rebuilt from the immutable event, never trusted
        # from a caller's replay of a prior response.
        payload = {k:v for k,v in data.items() if k not in {'seq', 'at', 'controller'}}
        self.store.audit(db, self.controller, payload['run_id'], 'dispatch', payload)
        return self._latest(db)[payload['run_id']]

    def _owned(self, latest, run_id):
        registration = latest.get(run_id)
        if registration is None or registration['controller'] != self.controller.id:
            raise RecordError('dispatch registration unavailable')
        return registration

    def prepare(self, claim, *, policy_sha256):
        with self.store.transaction() as db:
            return self._prepare(db, claim, policy_sha256=policy_sha256)

    def _prepare(self, db, claim, *, policy_sha256, request_revision=None):
        """Register a live claim once; replay is status, not launch permission.

        The digest identifies a trusted launch-policy artifact. This library
        does not establish that the artifact is safe or installed/enforced.
        """
        if not isinstance(policy_sha256, str) or re.fullmatch(r'[0-9a-f]{64}', policy_sha256) is None:
            raise RecordError('launch policy requires a SHA256 digest')
        current, task, run = self.store._live_claim(db, self.controller, claim)
        latest = self._latest(db)
        if run['id'] in latest:
            existing = self._owned(latest, run['id'])
            if existing['policy_sha256'] != policy_sha256:
                raise RecordError('launch policy changed for registered run')
            if request_revision is not None and existing.get('request_revision') != request_revision:
                raise RecordError('preflight request revision conflict')
            return existing
        if any(item['phase'] != 'released' for item in latest.values()):
            raise RecordError('one unresolved workload permitted per instance')
        meta = json.loads(run['data'])
        return self._append(db, {
            'phase':'reserved', 'claim_id':current['id'], 'run_id':run['id'],
            'task_id':task['id'], 'attempt':current['attempt'],
            'generation':current['generation'], 'restore_epoch':current['restore_epoch'],
            'workload_id':'hearth2-' + run['id'][4:],
            'deadline_at':run['deadline_at'], 'policy_sha256':policy_sha256,
            'model':meta['model'], 'role_revision':meta['role_revision'],
            'request_revision':request_revision,
        })

    def consume(self, claim):
        """Return a launch transition exactly once, after its durable commit.

        Only the root-side launcher may consume. It must separately enforce
        policy, account/allowance, limits and deadline before a native prompt.
        """
        with self.store.transaction() as db:
            current, task, run = self.store._live_claim(db, self.controller, claim)
            registration = self._owned(self._latest(db), run['id'])
            if (registration['phase'] != 'reserved'
                    or registration['claim_id'] != current['id']
                    or registration['restore_epoch'] != current['restore_epoch']
                    or registration['generation'] != current['generation']):
                raise RecordError('launch registration already consumed or fenced')
            return self._append(db, {**registration, 'phase':'launching'})

    def release(self, run_id):
        with self.store.transaction() as db:
            return self._release(db, run_id)

    def _release(self, db, run_id, *, receipt_sha256=None):
        """Release only after the authoritative record has trusted empty proof.

        This reads evidence, not the OS. A caller cannot pass its own boolean
        assertion here. Unknown/active work retains the slot, even past expiry.
        """
        registration = self._owned(self._latest(db), run_id)
        if registration['phase'] == 'released':
            return registration
        epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
        if registration['restore_epoch'] != epoch:
            restored = db.execute("SELECT seq FROM audit_events WHERE action='restored' ORDER BY seq DESC LIMIT 1").fetchone()
            fresh = any(
                event.get('run_id') == run_id
                and event.get('outcome') in {'failed', 'completed'}
                for event in (json.loads(row['data']) for row in db.execute(
                    "SELECT data FROM audit_events WHERE action='run_reconciled' AND seq>?",
                    (restored['seq'],)))
            ) if restored else False
            if not fresh:
                raise RecordError('restored dispatch requires fresh run reconciliation')
        run = self.store.row(db, 'runs', run_id)
        claim = self.store.row(db, 'claims', run['claim_id'])
        proof = json.loads(run['termination_evidence']) if run['termination_evidence'] else {}
        if (claim['state'] != 'closed' or run['ended_at'] is None
                or run['containment_state'] != 'verified_empty'
                or not proof.get('references')):
            raise RecordError('unresolved workload requires independent termination evidence')
        finished = {**registration, 'phase':'released'}
        if receipt_sha256 is not None:
            finished['receipt_sha256'] = receipt_sha256
        return self._append(db, finished)

    def pending(self):
        """Read all owners/epochs; restart or restore never implies termination."""
        with self.store.transaction() as db:
            return [item for item in self._latest(db).values() if item['phase'] != 'released']

    def claim_and_prepare(self, task_id, *, expected_revision, request_id,
                          expected_role_revision, policy_sha256):
        """Claim and reserve together, after fresh trusted account preflight.

        The role revision is the one observed before the account check. A role
        change or occupied slot consumes no attempt. No native prompt is sent.
        """
        if type(expected_role_revision) is not int or expected_role_revision < 1:
            raise RecordError('native preflight role revision required')
        if type(expected_revision) is not int or expected_revision < 1:
            raise RecordError('preflight request revision required')
        with self.store.transaction() as db:
            pending = [item for item in self._latest(db).values() if item['phase'] != 'released']
            previous = db.execute('SELECT id FROM runs WHERE request_id=?', (request_id,)).fetchone()
            if pending and (len(pending) != 1 or previous is None
                            or pending[0]['run_id'] != previous['id']):
                raise RecordError('one unresolved workload permitted per instance')
            claim = self.store._claim(db, self.controller, task_id,
                expected_revision=expected_revision, request_id=request_id,
                expected_role_revision=expected_role_revision)
            registration = self._prepare(db, claim, policy_sha256=policy_sha256,
                                         request_revision=expected_revision)
            return {'claim':claim, 'registration':registration}

    def record_and_release(self, claim, receipt):
        """Commit the trusted receipt and eligible slot release atomically.

        Held/unknown outcomes keep their slot. A normal closed run cannot be
        exported between receipt commit and slot release through this path.
        """
        if not isinstance(claim, dict):
            raise RecordError('registered launch claim required')
        digest = hashlib.sha256(safe_payload(receipt).encode()).hexdigest()
        with self.store.transaction() as db:
            registration = self._owned(self._latest(db), claim.get('run_id'))
            if registration['phase'] == 'released':
                epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
                current = self.store.row(db, 'claims', registration['claim_id'])
                fields = ['id', 'task_id', 'run_id', 'attempt', 'generation', 'restore_epoch']
                if (registration['restore_epoch'] != epoch
                        or any(type(claim.get(k)) is not type(current[k])
                               or claim[k] != current[k] for k in fields)
                        or current['runner'] != self.controller.id
                        or registration.get('receipt_sha256') != digest):
                    raise RecordError('completed receipt replay conflict or restore fence')
                return {'run':self.store.row(db, 'runs', current['run_id']),
                        'registration':registration}
            if registration['phase'] != 'launching':
                raise RecordError('consumed launch registration required')
            run = self.store._record_run(db, self.controller, claim, receipt)
            current = self.store.row(db, 'claims', run['claim_id'])
            if current['state'] == 'closed':
                registration = self._release(db, run['id'], receipt_sha256=digest)
            return {'run':run, 'registration':registration}

    def record_native_result(self, claim, result, *, ended_at, exit_status,
                             containment_state, termination_evidence):
        """Settle sanitized native data with independently collected OS evidence.

        This method cannot observe a process or authenticate native output. Only
        the trusted controller may call it after durable consume and OS cleanup.
        An output stop pauses the role; missing output preserves the real exit
        but holds the task. Native estimates never become actual seat charges.
        """
        from .native_output import decode_object
        if not isinstance(result, dict) or not isinstance(claim, dict):
            raise RecordError('native output and claim required')
        metadata = {'native_state':result.get('state'),
                    'native_stop_reason':result.get('stop_reason'),
                    'native_usage_scope':result.get('usage_scope')}
        state, stop, scope = native_receipt_metadata(metadata)
        usage = result.get('usage')
        if (state == 'observed' or type(result.get('pause_role')) is not bool
                or result['pause_role'] != (stop is not None)
                or not isinstance(usage, dict) or usage.get('actual_charge') is not None):
            raise RecordError('invalid native output provenance or charge')
        with self.store.transaction() as db:
            run = self.store.row(db, 'runs', claim.get('run_id'))
            if result.get('provider') != json.loads(run['data'])['family']:
                raise RecordError('native output provider does not match claimed role')
        closeout = None
        if state == 'completed':
            try:
                candidate = decode_object(result.get('text'))
                if isinstance(candidate, dict):
                    safe_payload(candidate)
                    closeout = candidate
            except RecordError:
                # Keep failed closeout validation without persisting native
                # diagnostics, prose or possible credentials as a task result.
                pass
        receipt = {'ended_at':ended_at, 'exit_status':exit_status, 'closeout':closeout,
                   'containment_state':containment_state,
                   'termination_evidence':termination_evidence, 'usage':usage, **metadata}
        return self.record_and_release(claim, receipt)
