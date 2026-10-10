"""Transactional project coordination. No model calls, scheduler or chat transport.

SQLite owns operational state; HM owns knowledge; Matrix owns conversations.
All mutations and audit events commit together. Claim ids fence stale workers,
including two surfaces authenticated as the same agent.
"""
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

CAPABILITIES = {"coding": "Coding", "design": "Design", "planning": "Planning & coordination",
                "research": "Research", "review": "Review & testing", "writing": "Writing"}
WORK_MODES = {"either": "Either", "interactive": "Interactive", "background": "Background"}


def choice(value, name, options):
    value = text(value, name, 40)
    if value not in options:
        raise WorkError(f"unknown {name}")
    return value


class WorkError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text(value, name, limit=12000, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise WorkError(f"{name} must be text of at most {limit} characters")
    value = value.strip()
    if required and not value:
        raise WorkError(f"{name} is required")
    return value


def strings(value, name, limit=50):
    if not isinstance(value, list) or len(value) > limit:
        raise WorkError(f"{name} must be a list of at most {limit} entries")
    return list(dict.fromkeys(text(v, name, 240, True) for v in value))


def now():
    return datetime.now(timezone.utc).isoformat()


class WorkStore:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def transaction(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS tasks_project ON tasks(project_id);
                CREATE TABLE IF NOT EXISTS activity (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL, actor TEXT NOT NULL, kind TEXT NOT NULL,
                    at TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_profiles (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL);
            """)
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @staticmethod
    def human(human):
        if not human:
            raise WorkError("a human must authorize this action", 403)

    @staticmethod
    def get(db, table, key):
        row = db.execute(f"SELECT data FROM {table} WHERE id=?", (key,)).fetchone()
        if row is None:
            raise WorkError(f"{table[:-1]} not found", 404)
        return json.loads(row[0])

    @staticmethod
    def save(db, table, item):
        item["updated_at"] = now()
        item["revision"] += 1
        db.execute(f"UPDATE {table} SET data=? WHERE id=?", (json.dumps(item), item["id"]))

    @staticmethod
    def event(db, project_id, task_id, actor, kind, data):
        db.execute("INSERT INTO activity(project_id,task_id,actor,kind,at,data) VALUES(?,?,?,?,?,?)",
                   (project_id, task_id, actor, kind, now(), json.dumps(data)))

    def create_project(self, actor, human, payload):
        self.human(human)
        item = {"id": "project_" + uuid.uuid4().hex, "title": text(payload.get("title", ""), "title", 200, True),
                "goal": text(payload.get("goal", ""), "goal", required=True),
                "brief": text(payload.get("brief", ""), "brief"), "phase": "idea",
                "created_by": actor, "created_at": now(), "updated_at": now(), "revision": 1}
        wing = text(payload.get("memory_wing", ""), "memory_wing", 120) or item["id"]
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", wing):
            raise WorkError("memory wing must contain letters, numbers, dots, slashes, underscores or hyphens")
        item["memory_wing"] = wing
        with self.transaction() as db:
            db.execute("INSERT INTO projects VALUES(?,?)", (item["id"], json.dumps(item)))
            self.event(db, item["id"], "", actor, "project_created", {"title": item["title"]})
        return item

    def project_phase(self, actor, human, project_id, phase):
        self.human(human)
        phase = text(phase, "phase", 30, True)
        if phase not in {"idea", "design", "build", "validate", "shipped"}:
            raise WorkError("unknown project phase")
        with self.transaction() as db:
            item = self.get(db, "projects", project_id)
            tasks = [json.loads(r[0]) for r in db.execute("SELECT data FROM tasks WHERE project_id=?", (project_id,))]
            if phase == "shipped" and (not tasks or any(t["state"] != "done" for t in tasks)):
                raise WorkError("all project tasks must be reviewed and done before shipping", 409)
            item["phase"] = phase
            self.save(db, "projects", item)
            self.event(db, project_id, "", actor, "phase_changed", {"phase": phase})
        return item

    def create_task(self, actor, project_id, payload, roster):
        assignee = text(payload.get("assignee", ""), "assignee", 200)
        if assignee and assignee not in roster:
            raise WorkError("assignee must be a registered agent")
        deps = strings(payload.get("dependencies", []), "dependencies")
        references = strings(payload.get("memory_ids", []), "memory_ids")
        capability = choice(payload.get("capability", ""), "capability", {"", *CAPABILITIES})
        work_mode = choice(payload.get("work_mode", "either"), "work_mode", WORK_MODES)
        room = text(payload.get("room_id", ""), "room_id", 240)
        root = text(payload.get("thread_root", ""), "thread_root", 240)
        if bool(room) != bool(root) or (room and (not room.startswith("!") or not root.startswith("$"))):
            raise WorkError("a conversation requires a Matrix room id and thread event id")
        item = {"id": "task_" + uuid.uuid4().hex, "project_id": project_id,
                "title": text(payload.get("title", ""), "title", 200, True),
                "description": text(payload.get("description", ""), "description"),
                "acceptance": text(payload.get("acceptance", ""), "acceptance", required=True),
                "assignee": assignee, "dependencies": deps, "memory_ids": references,
                "capability": capability, "work_mode": work_mode,
                "room_id": room, "thread_root": root, "state": "draft", "claim_id": "",
                "claim_until": 0, "claim_surface": "", "summary": "", "evidence": [],
                "blocked_reason": "", "created_by": actor, "created_at": now(), "updated_at": now(), "revision": 1}
        with self.transaction() as db:
            project = self.get(db, "projects", project_id)
            if project["phase"] == "shipped":
                raise WorkError("reopen the project before adding work", 409)
            for dep in deps:
                parent = self.get(db, "tasks", dep)
                if parent["project_id"] != project_id:
                    raise WorkError("dependencies must be in the same project")
            db.execute("INSERT INTO tasks VALUES(?,?,?)", (item["id"], project_id, json.dumps(item)))
            self.event(db, project_id, item["id"], actor, "task_proposed", {"title": item["title"]})
        return item

    def set_profile(self, actor, human, agent, payload, roster):
        self.human(human)
        if agent not in roster:
            raise WorkError("profile must belong to a registered agent", 404)
        strengths = strings(payload.get("strengths", []), "strengths", 3)
        supporting = strings(payload.get("supporting", []), "supporting", 6)
        if set(strengths + supporting) - CAPABILITIES.keys() or set(strengths) & set(supporting):
            raise WorkError("use known, non-overlapping strengths and supporting skills")
        source = text(payload.get("source", ""), "assessment basis", 2000, bool(strengths or supporting))
        profile = {"id": agent, "strengths": strengths, "supporting": supporting,
                   "work_mode": choice(payload.get("work_mode", "either"), "work_mode", WORK_MODES),
                   "availability": choice(payload.get("availability", "unknown"), "availability",
                                          {"unknown", "accepting", "paused"}),
                   "notes": text(payload.get("notes", ""), "notes", 2000), "source": source,
                   "updated_by": actor, "updated_at": now()}
        with self.transaction() as db:
            db.execute("INSERT INTO agent_profiles VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                       (agent, json.dumps(profile)))
            self.event(db, "", "", actor, "agent_profile_updated", {"agent": agent, **profile})
        return profile

    def agent_directory(self, roster, capability="", work_mode="either"):
        choice(capability, "capability", {"", *CAPABILITIES})
        choice(work_mode, "work_mode", WORK_MODES)
        with self.transaction() as db:
            saved = {r["id"]: json.loads(r["data"]) for r in db.execute("SELECT * FROM agent_profiles")}
            tasks = [json.loads(r[0]) for r in db.execute("SELECT data FROM tasks")]
        profiles, matches = [], []
        for agent in sorted(roster):
            p = saved.get(agent, {"id": agent, "strengths": [], "supporting": [], "work_mode": "either",
                                  "availability": "unknown", "notes": "", "source": "",
                                  "updated_by": "", "updated_at": ""}).copy()
            p["workload"] = {s: sum(t["assignee"] == agent and t["state"] == s for t in tasks)
                             for s in ("ready", "running", "review", "blocked")}
            p["open_tasks"] = sum(p["workload"].values())
            profiles.append(p)
            skill = 2 if capability in p["strengths"] else 1 if capability in p["supporting"] else 0
            if not skill or p["availability"] == "paused":
                continue
            if work_mode != "either" and p["work_mode"] not in {"either", work_mode}:
                continue
            mode_fit = int(work_mode != "either" and p["work_mode"] == work_mode)
            reason = f'{"Strength" if skill == 2 else "Supporting skill"}: {CAPABILITIES[capability]}'
            reason += f' · {WORK_MODES[p["work_mode"]]} · {p["open_tasks"]} open {"task" if p["open_tasks"] == 1 else "tasks"}'
            if p["availability"] == "unknown":
                reason += " · availability unconfirmed"
            matches.append({"agent": agent, "reason": reason, "source": p["source"],
                            "updated_at": p["updated_at"], "rank": (skill, mode_fit, -p["open_tasks"])})
        matches.sort(key=lambda m: tuple(-v for v in m["rank"]) + (m["agent"],))
        for m in matches:
            m.pop("rank")
        return {"profiles": profiles, "suggestions": matches[:3], "categories": CAPABILITIES,
                "work_modes": WORK_MODES,
                "guidance": "Human-maintained assessments, not benchmark rankings. Workload is board state; availability is declared, not runtime liveness."}

    def action(self, actor, human, task_id, payload, roster=None):
        action = text(payload.get("action", ""), "action", 40, True)
        with self.transaction() as db:
            task = self.get(db, "tasks", task_id)
            state = task["state"]
            stamp = time.time()
            evidence = {}
            if action in {"ready", "accept", "revise", "release", "assign"}:
                self.human(human)
            if action == "assign":
                if state not in {"draft", "blocked"}:
                    raise WorkError("release or revise active work before reassigning", 409)
                assignee = text(payload.get("assignee", ""), "assignee", 200, True)
                if assignee not in (roster or set()):
                    raise WorkError("assignee must be a registered agent")
                task["assignee"] = assignee
                evidence = {"assignee": assignee}
            elif action == "ready":
                if state not in {"draft", "blocked"}:
                    raise WorkError("only draft or blocked tasks can be authorized", 409)
                if not task["assignee"]:
                    raise WorkError("assign an agent before authorizing work", 409)
                task.update(state="ready", blocked_reason="", authorized_by=actor)
            elif action == "claim":
                if human or actor != task["assignee"]:
                    raise WorkError("only the assigned agent can claim a task", 403)
                if state != "ready" and not (state == "running" and task["claim_until"] <= stamp):
                    raise WorkError("task is not ready or already has a live claim", 409)
                open_deps = [dep for dep in task["dependencies"] if self.get(db, "tasks", dep)["state"] != "done"]
                if open_deps:
                    raise WorkError("dependencies still need review: " + ", ".join(open_deps), 409)
                task.update(state="running", claim_id=uuid.uuid4().hex, claim_until=stamp + 900,
                            claim_surface=text(payload.get("surface", ""), "surface", 200), blocked_reason="")
            elif action in {"heartbeat", "review", "block"}:
                if state != "running" or actor != task["assignee"] or task["claim_until"] <= stamp:
                    raise WorkError("a live claim owned by the assigned agent is required", 409)
                if not payload.get("claim_id") or payload["claim_id"] != task["claim_id"]:
                    raise WorkError("stale or missing claim id", 409)
                if action == "heartbeat":
                    task["claim_until"] = stamp + 900
                elif action == "review":
                    summary = text(payload.get("summary", ""), "summary", required=True)
                    refs = strings(payload.get("evidence", []), "evidence")
                    if not refs:
                        raise WorkError("completion requires evidence references")
                    task.update(state="review", summary=summary, evidence=refs, claim_id="", claim_until=0)
                    evidence = {"summary": summary, "evidence": refs}
                else:
                    reason = text(payload.get("reason", ""), "reason", required=True)
                    task.update(state="blocked", blocked_reason=reason, claim_id="", claim_until=0)
                    evidence = {"reason": reason}
            elif action == "accept":
                if state != "review":
                    raise WorkError("task must have evidence and be awaiting review", 409)
                task.update(state="done", reviewed_by=actor, reviewed_at=now())
            elif action == "revise":
                if state != "review":
                    raise WorkError("only a task awaiting review can be revised", 409)
                reason = text(payload.get("reason", ""), "reason", required=True)
                task.update(state="draft", blocked_reason=reason)
                evidence = {"reason": reason}
            elif action == "release":
                if state != "running":
                    raise WorkError("only a running task can be released", 409)
                reason = text(payload.get("reason", ""), "reason", required=True)
                task.update(state="draft", claim_id="", claim_until=0, blocked_reason=reason)
                evidence = {"reason": reason}
            else:
                raise WorkError("unknown task action")
            # A parent's review can never be bypassed on submission or acceptance.
            if action in {"review", "accept"} and any(self.get(db, "tasks", d)["state"] != "done" for d in task["dependencies"]):
                raise WorkError("dependencies must be done", 409)
            self.save(db, "tasks", task)
            self.event(db, task["project_id"], task_id, actor, action, evidence)
        return task

    def comment(self, actor, task_id, body):
        body = text(body, "comment", required=True)
        with self.transaction() as db:
            task = self.get(db, "tasks", task_id)
            self.event(db, task["project_id"], task_id, actor, "comment", {"body": body})
        return {"ok": True}

    def link_memory(self, actor, task_id, drawer_id):
        """Record a successful HM capture; retrying never duplicates the board event."""
        with self.transaction() as db:
            task = self.get(db, "tasks", task_id)
            outputs = task.setdefault("output_memory_ids", [])
            if drawer_id not in outputs:
                outputs.append(drawer_id)
                self.save(db, "tasks", task)
                self.event(db, task["project_id"], task_id, actor, "memory_captured", {"drawer_id": drawer_id})

    def snapshot(self, project_id=""):
        with self.transaction() as db:
            projects = [json.loads(r[0]) for r in db.execute("SELECT data FROM projects")]
            tasks = [json.loads(r[0]) for r in db.execute("SELECT data FROM tasks")]
            if project_id:
                self.get(db, "projects", project_id)
                projects = [p for p in projects if p["id"] == project_id]
                tasks = [t for t in tasks if t["project_id"] == project_id]
            history = db.execute("SELECT * FROM activity WHERE (?='' OR project_id=?) ORDER BY seq DESC LIMIT 200",
                                 (project_id, project_id)).fetchall()
        by_id = {t["id"]: t for t in tasks}
        for task in tasks:
            task["waiting_on"] = [d for d in task["dependencies"] if by_id[d]["state"] != "done"]
            task["claim_expired"] = task["state"] == "running" and task["claim_until"] <= time.time()
            # Claim tokens go only to the claiming worker, never the shared board.
            task.pop("claim_id", None)
        return {"projects": projects, "tasks": tasks,
                "activity": [{**dict(r), "data": json.loads(r["data"])} for r in history], "generated_at": now()}

    def board_for_task(self, task_id):
        with self.transaction() as db:
            project_id = self.get(db, "tasks", task_id)["project_id"]
        return self.snapshot(project_id)
