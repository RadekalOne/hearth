"""Inactive preflight-to-dispatch coordinator; no scheduler or native launch.

The account observer is a trusted controller-side collector, not a worker tool.
It runs outside the database lock. A role fence closes the gap between native
preflight and atomic claim/reservation. This module never calls a model.
"""
import copy
from .dispatch import DispatchRegistry
from .launch_guards import codex_launch_check, claude_launch_check
from .store import RecordError, text


class PreflightController:
    def __init__(self, store, controller, observe_account, *, policy_sha256,
                 claude_review=None, accepted_seat_limit=None):
        self.registry = DispatchRegistry(store, controller)
        if not callable(observe_account):
            raise RecordError('trusted native account observer required')
        self.store, self.controller = store, controller
        self.observe_account, self.policy_sha256 = observe_account, policy_sha256
        self.claude_review = copy.deepcopy(claude_review)
        self.accepted_seat_limit = accepted_seat_limit

    def _failure(self, task_id, request_id, state):
        snapshot = self.store.control_snapshot()
        previous = next((item for item in snapshot['failures']
            if item['kind'] == 'dispatch_blocked' and item['target'] == task_id
            and item['key'] == 'native-account-preflight'), None)
        if state == 'recovered' and (previous is None or previous['state'] == 'recovered'):
            return None
        return self.store.control_failure(self.controller,
            kind='dispatch_blocked', target=task_id, key='native-account-preflight',
            expected_seq=previous['seq'] if previous else 0,
            expected_epoch=snapshot['restore_epoch'], state=state,
            evidence=['native account preflight '+state, 'controller-request:'+request_id])

    def prepare(self, task_id, *, expected_revision, request_id):
        """Observe the account before a claim; refuse unknowns without attempts.

        Returns prepared registration or a durable blocked observation. It does
        not consume the launch permission, send a task prompt, renew a lease or
        establish that an observer/launcher is installed and correctly isolated.
        """
        text(request_id, 'controller request id', 64)
        with self.store.transaction() as db:
            task = self.store.row(db, 'tasks', task_id)
            role = dict(self.store._eligible(db, task))
            if (task['state'] != 'ready' or type(expected_revision) is not int
                    or task['revision'] != expected_revision or task['attempts'] >= 3):
                raise RecordError('task is not ready for native preflight')
        try:
            observed = self.observe_account(role)
            if not isinstance(observed, dict):
                raise RecordError('native observation unavailable')
            common = dict(route=observed.get('route'), observed_at=observed.get('observed_at'),
                          now=self.store.now())
            if role['family'] == 'openai':
                account_check = codex_launch_check(account=observed.get('account'),
                    limits=observed.get('limits'), **common)
            elif role['family'] == 'anthropic':
                account_check = claude_launch_check(auth=observed.get('auth'),
                    review=self.claude_review, accepted_seat_limit=self.accepted_seat_limit, **common)
            else:
                raise RecordError('unsupported native provider')
        except Exception:
            # Never copy native stderr, account data, credentials or exception
            # text into the record or the worker's context.
            failure = self._failure(task_id, request_id, 'open')
            return {'state':'blocked', 'failure':failure}
        dispatch = self.registry.claim_and_prepare(task_id,
            expected_revision=expected_revision, request_id=request_id,
            expected_role_revision=role['revision'], policy_sha256=self.policy_sha256)
        self._failure(task_id, request_id, 'recovered')
        return {'state':'prepared', **dispatch, 'account_check':account_check}
