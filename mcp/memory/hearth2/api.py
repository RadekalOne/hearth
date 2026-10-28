"""Default-off routes in the existing service; no restore HTTP endpoint.

Principal kinds are explicit per-instance configuration. Controller tokens are
accepted only as bearer credentials, never as browser sessions or payloads.
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from fastapi import HTTPException, Request, Response
from .schema import Schema, SchemaError
from .store import Store, Principal, RecordError
from .backup import export_record


class Runtime:
    def __init__(self, app, *, enabled, data_dir, principal, typed_auth,
                 same_origin, bearer_principal, human_ids, controller_ids,
                 worker_ids, authenticated):
        self.enabled = enabled
        self.store = Store(Path(data_dir) / 'hearth2.sqlite3')
        self.principal = principal
        self.typed_auth = typed_auth
        self.same_origin = same_origin
        self.bearer_principal = bearer_principal
        self.humans, self.controllers, self.workers = map(set, (human_ids, controller_ids, worker_ids))
        self.authenticated = authenticated
        self.initialized = False
        self.routes(app)

    def initialize(self):
        if not self.enabled:
            return
        groups = [self.humans, self.controllers, self.workers]
        if (not self.authenticated or not self.humans or any('anonymous' in g for g in groups)
                or self.humans & self.controllers or self.humans & self.workers or self.controllers & self.workers):
            raise RuntimeError('Hearth 2 requires authentication and disjoint explicit principal roles')
        Schema.initialize(self.store.path, enabled=True)
        self.initialized = True

    def actor(self, request, kinds):
        if not self.enabled:
            raise HTTPException(409, 'Hearth 2 is disabled')
        if not self.initialized:
            raise HTTPException(503, 'Hearth 2 initialization required')
        identity = self.principal()
        if self.typed_auth() is not None or identity == 'anonymous':
            raise HTTPException(403, 'Hearth 2 principal not authorized')
        kind = ('human' if identity in self.humans else 'controller' if identity in self.controllers
                else 'worker' if identity in self.workers else None)
        if kind not in kinds or kind == 'controller' and self.bearer_principal(request) != identity:
            raise HTTPException(403, 'Hearth 2 principal not authorized')
        if request.method != 'GET' and not self.same_origin(request):
            raise HTTPException(403, 'cross-site request rejected')
        return Principal(identity, kind)

    async def body(self, request, fields):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 1_000_000:
                raise HTTPException(413, 'Hearth 2 request too large')
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError, UnicodeError):
            raise HTTPException(400, 'expected a JSON object') from None
        if not isinstance(data, dict) or set(data) - set(fields):
            raise HTTPException(400, 'unknown fields; identity is server supplied')
        return data

    @staticmethod
    def call(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except RecordError as error:
            raise HTTPException(409, str(error)) from None
        except (TypeError, KeyError, AttributeError, RecursionError):
            raise HTTPException(400, 'invalid Hearth 2 request') from None
        except (SchemaError, sqlite3.DatabaseError):
            raise HTTPException(503, 'Hearth 2 store unavailable') from None

    def routes(self, app):
        @app.get('/api/hearth2')
        def snapshot(request: Request, project_id: str | None = None):
            self.actor(request, {'human', 'controller'})
            return self.call(self.store.snapshot, project_id)

        @app.get('/api/hearth2/export')
        def export(request: Request):
            self.actor(request, {'human'})
            with tempfile.TemporaryDirectory(prefix='hearth2-export-') as directory:
                path = Path(directory) / 'backup.json'
                self.call(export_record, self.store.path, path)
                raw = path.read_bytes()
            return Response(raw, media_type='application/json', headers={
                'Content-Disposition': 'attachment; filename="hearth2-work-record-v1.json"',
                'Cache-Control': 'no-store'})

        @app.post('/api/hearth2/projects')
        async def project(request: Request):
            actor = self.actor(request, {'human', 'controller'})
            return self.call(self.store.create_project, actor, await self.body(request, {'title', 'goal'}))

        @app.post('/api/hearth2/projects/{project_id}/plans')
        async def plan(project_id: str, request: Request):
            actor = self.actor(request, {'human', 'controller'})
            return self.call(self.store.create_plan, actor, project_id, await self.body(request, {'content_ref', 'scope', 'actions'}))

        @app.post('/api/hearth2/tasks')
        async def task(request: Request):
            actor = self.actor(request, {'human', 'controller'})
            data = await self.body(request, {'project_id', 'plan_id', 'action_id', 'recipient', 'ask', 'done_means', 'inputs', 'return', 'dependencies'})
            return self.call(self.store.create_task, actor, data)

        @app.post('/api/hearth2/roles/{agent}')
        async def role(agent: str, request: Request):
            actor = self.actor(request, {'human'})
            data = await self.body(request, {'model', 'family', 'role', 'confirm'})
            return self.call(self.store.set_role, actor, agent, data)

        @app.post('/api/hearth2/decisions')
        async def decision(request: Request):
            actor = self.actor(request, {'human', 'controller'})
            data = await self.body(request, {'plan_id', 'intended_subject', 'expires_at'})
            if data.get('intended_subject') not in self.humans:
                raise HTTPException(400, 'intended subject must be a configured human')
            return self.call(self.store.create_decision, actor, data.get('plan_id'),
                             intended_subject=data.get('intended_subject'), expires_at=data.get('expires_at'))

        @app.post('/api/hearth2/decisions/{decision_id}/actions')
        async def decide(decision_id: str, request: Request):
            actor = self.actor(request, {'human'})
            data = await self.body(request, {'expected_revision', 'action', 'source'})
            return self.call(self.store.record_decision, actor, decision_id, data.get('expected_revision'), data.get('action'), data.get('source'))

        @app.post('/api/hearth2/tasks/{task_id}/claim')
        async def claim(task_id: str, request: Request):
            actor = self.actor(request, {'controller'})
            data = await self.body(request, {'expected_revision', 'request_id'})
            return self.call(self.store.claim, actor, task_id, expected_revision=data.get('expected_revision'), request_id=data.get('request_id'))

        @app.post('/api/hearth2/claims/{claim_id}/renew')
        async def renew(claim_id: str, request: Request):
            actor = self.actor(request, {'controller'})
            data = await self.body(request, {'claim', 'lease_until'})
            if not isinstance(data.get('claim'), dict) or data['claim'].get('id') != claim_id:
                raise HTTPException(400, 'claim identity mismatch')
            return self.call(self.store.renew, actor, data['claim'], lease_until=data.get('lease_until'))

        @app.post('/api/hearth2/runs/{run_id}/receipt')
        async def receipt(run_id: str, request: Request):
            actor = self.actor(request, {'controller'})
            data = await self.body(request, {'claim', 'receipt'})
            if not isinstance(data.get('claim'), dict) or data['claim'].get('run_id') != run_id:
                raise HTTPException(400, 'run identity mismatch')
            return self.call(self.store.record_run, actor, data['claim'], data.get('receipt'))

        @app.post('/api/hearth2/runs/{run_id}/reconcile')
        async def reconcile(run_id: str, request: Request):
            actor = self.actor(request, {'controller'})
            data = await self.body(request, {'termination_evidence', 'outcome'})
            return self.call(self.store.reconcile, actor, run_id, termination_evidence=data.get('termination_evidence'), outcome=data.get('outcome'))

        @app.post('/api/hearth2/notices')
        async def notice(request: Request):
            actor = self.actor(request, {'controller'})
            data = await self.body(request, {'claim', 'notice'})
            return self.call(self.store.append_notice, actor, data.get('notice'), claim=data.get('claim'))

        @app.post('/api/hearth2/tasks/{task_id}/reviews')
        async def review(task_id: str, request: Request):
            actor = self.actor(request, {'worker'})
            data = await self.body(request, {'expected_revision', 'verdict', 'evidence'})
            return self.call(self.store.record_review, actor, task_id, data.get('expected_revision'), data.get('verdict'), data.get('evidence'))

        @app.post('/api/hearth2/tasks/{task_id}/acceptance')
        async def accept(task_id: str, request: Request):
            actor = self.actor(request, {'human'})
            data = await self.body(request, {'expected_revision', 'evidence'})
            return self.call(self.store.accept_result, actor, task_id, data.get('expected_revision'), data.get('evidence'))

        @app.post('/api/hearth2/tasks/{task_id}/revision')
        async def revise(task_id: str, request: Request):
            actor = self.actor(request, {'controller'})
            data = await self.body(request, {'expected_revision', 'revision_note'})
            return self.call(self.store.revise_task, actor, task_id, data.get('expected_revision'), data.get('revision_note'))
