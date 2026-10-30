"""Durable launch intent for a trusted controller, not a process launcher.

The immutable journal holds the one instance-wide slot across restarts. A
successful consume commits before a future launcher may act; replay never
authorizes another launch. A crash in that gap requires reconciliation rather
than a retry. No credential, executable, host path or worker command is stored.
"""
import json
import re
from .store import RecordError, require


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
        """Register a live claim once; replay is status, not launch permission.

        The digest identifies a trusted launch-policy artifact. This library
        does not establish that the artifact is safe or installed/enforced.
        """
        if not isinstance(policy_sha256, str) or re.fullmatch(r'[0-9a-f]{64}', policy_sha256) is None:
            raise RecordError('launch policy requires a SHA256 digest')
        with self.store.transaction() as db:
            current, task, run = self.store._live_claim(db, self.controller, claim)
            latest = self._latest(db)
            if run['id'] in latest:
                existing = self._owned(latest, run['id'])
                if existing['policy_sha256'] != policy_sha256:
                    raise RecordError('launch policy changed for registered run')
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
        """Release only after the authoritative record has trusted empty proof.

        This reads evidence, not the OS. A caller cannot pass its own boolean
        assertion here. Unknown/active work retains the slot, even past expiry.
        """
        with self.store.transaction() as db:
            registration = self._owned(self._latest(db), run_id)
            if registration['phase'] == 'released':
                return registration
            epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            if registration['restore_epoch'] != epoch:
                restored = db.execute("SELECT seq FROM audit_events WHERE action='restored' ORDER BY seq DESC LIMIT 1").fetchone()
                fresh = any(
                    json.loads(row['data']).get('run_id') == run_id
                    and json.loads(row['data']).get('outcome') in {'failed', 'completed'}
                    for row in db.execute(
                        "SELECT data FROM audit_events WHERE action='run_reconciled' AND seq>?",
                        (restored['seq'],))
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
            return self._append(db, {**registration, 'phase':'released'})

    def pending(self):
        """Read all owners/epochs; restart or restore never implies termination."""
        with self.store.transaction() as db:
            return [item for item in self._latest(db).values() if item['phase'] != 'released']
