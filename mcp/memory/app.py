"""Hearth memory service.

Durable shared memory for a Hearth hub, modeled on the MemPalace pattern:
wings (projects) -> rooms (aspects) -> drawers (verbatim facts), plus a
per-agent diary. Embeddings are computed locally (ChromaDB's default ONNX
MiniLM model) so no API key is required.

Exposes:
  - MCP over streamable HTTP at /mcp  (for agents)
  - REST under /api                   (for the dashboard)
  - the admin dashboard at /
"""

import json
import os
import secrets as pysecrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import chromadb
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

DATA_DIR = os.environ.get("HEARTH_DATA_DIR", "./data")
HOMESERVER_URL = os.environ.get("HEARTH_HOMESERVER_URL", "")
# When set, /api/* and /mcp require a bearer token (the admin token or a minted
# agent token). When unset, the service runs open — safe only on loopback.
ADMIN_TOKEN = os.environ.get("HEARTH_MEMORY_ADMIN_TOKEN", "")
# Optional: a Matrix access token (any account joined to the standard rooms)
# lets the dashboard observe agent activity via /api/agents.
MATRIX_TOKEN = os.environ.get("HEARTH_MATRIX_TOKEN", "")
TOKENS_PATH = os.path.join(DATA_DIR, "memory-tokens.json")


def load_tokens() -> dict:
    try:
        with open(TOKENS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_tokens(tokens: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


def bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    return auth[7:] if auth.lower().startswith("bearer ") else ""

chroma = chromadb.PersistentClient(path=os.path.join(DATA_DIR, "chroma"))
drawers = chroma.get_or_create_collection("drawers", metadata={"hnsw:space": "cosine"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _where(wing: str | None = None, room: str | None = None) -> dict | None:
    clauses = []
    if wing:
        clauses.append({"wing": wing})
    if room:
        clauses.append({"room": room})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def add_drawer(wing: str, room: str, content: str, added_by: str, source: str | None) -> dict:
    drawer_id = f"drawer_{uuid.uuid4().hex[:16]}"
    drawers.add(
        ids=[drawer_id],
        documents=[content],
        metadatas=[{
            "wing": wing,
            "room": room,
            "added_by": added_by,
            "source": source or "",
            "created_at": _now(),
        }],
    )
    return {"drawer_id": drawer_id, "wing": wing, "room": room}


def search_drawers(query: str, wing: str | None, room: str | None,
                   limit: int, max_distance: float) -> dict:
    res = drawers.query(
        query_texts=[query],
        n_results=max(1, min(limit, 50)),
        where=_where(wing, room),
    )
    results = []
    for i, doc in enumerate(res["documents"][0]):
        distance = res["distances"][0][i]
        if max_distance and distance > max_distance:
            continue
        meta = res["metadatas"][0][i]
        results.append({
            "drawer_id": res["ids"][0][i],
            "content": doc,
            "wing": meta.get("wing"),
            "room": meta.get("room"),
            "added_by": meta.get("added_by"),
            "created_at": meta.get("created_at"),
            "distance": round(distance, 4),
        })
    return {"query": query, "results": results}


def status() -> dict:
    total = drawers.count()
    got = drawers.get(include=["metadatas"], limit=10000)
    wings: dict[str, int] = {}
    rooms: dict[str, int] = {}
    for meta in got["metadatas"]:
        wings[meta.get("wing", "?")] = wings.get(meta.get("wing", "?"), 0) + 1
        rooms[meta.get("room", "?")] = rooms.get(meta.get("room", "?"), 0) + 1
    return {"total_drawers": total, "wings": wings, "rooms": rooms}


PROTOCOL = (
    "Hearth Memory Protocol: 1) On wake-up, call memory_status. "
    "2) Before answering about people, projects, or past events, call memory_search first — "
    "never guess. 3) After each work session, call diary_write with what happened and what "
    "you learned. 4) File durable facts and decisions with memory_add so other agents can "
    "find them."
)

# ---------------------------------------------------------------- MCP tools

# Host-header (DNS-rebinding) checks are disabled: the service is localhost-only by
# default and the host port is user-configurable, so a static allowlist can't work.
mcp = FastMCP(
    "hearth-memory",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
def memory_status() -> dict:
    """Palace overview: drawer counts by wing and room, plus the memory protocol."""
    return {**status(), "protocol": PROTOCOL}


@mcp.tool()
def memory_add(wing: str, room: str, content: str, added_by: str = "agent",
               source: str = "") -> dict:
    """File verbatim content into memory. wing = project, room = aspect (e.g. decisions,
    notes-between-agents), content = exact words to preserve, never a summary."""
    return add_drawer(wing, room, content, added_by, source)


@mcp.tool()
def memory_search(query: str, wing: str = "", room: str = "", limit: int = 5,
                  max_distance: float = 1.2) -> dict:
    """Semantic search over all drawers. Returns verbatim content with cosine distances
    (lower = closer). Optionally filter by wing and/or room."""
    return search_drawers(query, wing or None, room or None, limit, max_distance)


@mcp.tool()
def memory_get(drawer_id: str) -> dict:
    """Fetch one drawer verbatim by id."""
    got = drawers.get(ids=[drawer_id], include=["documents", "metadatas"])
    if not got["ids"]:
        return {"error": f"no drawer {drawer_id}"}
    return {"drawer_id": drawer_id, "content": got["documents"][0], **got["metadatas"][0]}


@mcp.tool()
def diary_write(agent: str, content: str) -> dict:
    """Write a diary entry for this agent: what happened this session, what you learned,
    what the next session should know."""
    return add_drawer(f"agent_{agent}", "diary", content, agent, "")


@mcp.tool()
def diary_read(agent: str, limit: int = 10) -> dict:
    """Read this agent's most recent diary entries, newest first."""
    got = drawers.get(where=_where(f"agent_{agent}", "diary"),
                      include=["documents", "metadatas"])
    entries = sorted(
        (
            {"drawer_id": i, "content": d, "created_at": m.get("created_at")}
            for i, d, m in zip(got["ids"], got["documents"], got["metadatas"])
        ),
        key=lambda e: e["created_at"] or "",
        reverse=True,
    )[: max(1, min(limit, 100))]
    return {"agent": agent, "count": len(entries), "entries": entries}


# ---------------------------------------------------------------- REST + dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="hearth-memory", lifespan=lifespan)


@app.middleware("http")
async def require_token(request: Request, call_next):
    protected = request.url.path.startswith(("/api/", "/mcp"))
    if ADMIN_TOKEN and protected:
        token = bearer(request)
        if token != ADMIN_TOKEN and token not in load_tokens().values():
            return JSONResponse({"error": "missing or invalid bearer token"}, status_code=401)
    return await call_next(request)


def require_admin(request: Request) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(403, "token administration requires HEARTH_MEMORY_ADMIN_TOKEN to be set")
    if bearer(request) != ADMIN_TOKEN:
        raise HTTPException(403, "admin token required")


@app.post("/api/tokens")
async def mint_token(request: Request):
    require_admin(request)
    body = await request.json()
    agent = str(body.get("agent", "")).strip()
    if not agent:
        raise HTTPException(400, "agent name required")
    tokens = load_tokens()
    tokens[agent] = pysecrets.token_urlsafe(32)
    save_tokens(tokens)
    return {"agent": agent, "token": tokens[agent]}


@app.post("/api/import")
async def bulk_import(request: Request):
    """Admin bulk import. Body: {"drawers": [{wing, room, content, added_by?,
    source?, created_at?, drawer_id?}]}. Preserves provided timestamps/ids;
    upserts, so re-running an import is idempotent."""
    require_admin(request)
    body = await request.json()
    items = body.get("drawers", [])
    if not items:
        raise HTTPException(400, "no drawers provided")
    if len(items) > 200:
        raise HTTPException(400, "max 200 drawers per request — batch your import")
    ids, docs, metas = [], [], []
    for it in items:
        content = (it.get("content") or "").strip()
        if not content or not it.get("wing") or not it.get("room"):
            continue
        ids.append(it.get("drawer_id") or f"drawer_{uuid.uuid4().hex[:16]}")
        docs.append(content)
        metas.append({
            "wing": it["wing"],
            "room": it["room"],
            "added_by": it.get("added_by", "import"),
            "source": it.get("source", ""),
            "created_at": it.get("created_at") or _now(),
            "imported": True,
        })
    if ids:
        drawers.upsert(ids=ids, documents=docs, metadatas=metas)
    return {"imported": len(ids), "skipped": len(items) - len(ids)}


@app.get("/api/tokens")
def list_tokens(request: Request):
    require_admin(request)
    return {"agents": sorted(load_tokens().keys())}


@app.delete("/api/tokens/{agent}")
def revoke_token(agent: str, request: Request):
    require_admin(request)
    tokens = load_tokens()
    if agent not in tokens:
        raise HTTPException(404, f"no token for '{agent}'")
    del tokens[agent]
    save_tokens(tokens)
    return {"revoked": agent}


@app.get("/health")
async def health():
    homeserver = "unconfigured"
    if HOMESERVER_URL:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{HOMESERVER_URL.rstrip('/')}/_matrix/client/versions")
                homeserver = "ok" if r.status_code == 200 else f"error {r.status_code}"
        except Exception as err:
            homeserver = f"unreachable ({type(err).__name__})"
    return {"memory": "ok", "homeserver": homeserver, "drawers": drawers.count()}


@app.get("/api/status")
def api_status():
    return status()


@app.get("/api/search")
def api_search(q: str, wing: str = "", room: str = "", limit: int = 10):
    if not q.strip():
        raise HTTPException(400, "empty query")
    return search_drawers(q, wing or None, room or None, limit, max_distance=1.5)


@app.get("/api/recent")
def api_recent(limit: int = 20):
    got = drawers.get(include=["documents", "metadatas"], limit=1000)
    entries = sorted(
        (
            {"drawer_id": i, "content": d[:400], **m}
            for i, d, m in zip(got["ids"], got["documents"], got["metadatas"])
        ),
        key=lambda e: e.get("created_at") or "",
        reverse=True,
    )[: max(1, min(limit, 100))]
    return {"entries": entries}


def _parse_usage(body: str) -> dict:
    """Parse a [USAGE] message: key=value pairs, e.g.
    [USAGE] provider=anthropic period=daily used=120k limit=500k"""
    fields = {}
    for part in body.split():
        if "=" in part:
            k, _, v = part.partition("=")
            fields[k.strip().lower()] = v.strip()

    def num(s):
        try:
            s = s.lower().replace(",", "")
            mult = 1
            if s.endswith("k"):
                mult, s = 1_000, s[:-1]
            elif s.endswith("m"):
                mult, s = 1_000_000, s[:-1]
            return float(s) * mult
        except (ValueError, AttributeError):
            return None

    used, limit = num(fields.get("used", "")), num(fields.get("limit", ""))
    if used is not None and limit:
        fields["pct"] = round(100 * used / limit, 1)
    return fields


@app.get("/api/agents")
async def api_agents():
    """Aggregate live agent activity from the Matrix rooms + memory writes."""
    if not (MATRIX_TOKEN and HOMESERVER_URL):
        raise HTTPException(503, "activity observer not configured — set HEARTH_MATRIX_TOKEN")
    base = HOMESERVER_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {MATRIX_TOKEN}"}
    events, room_names = [], {}
    async with httpx.AsyncClient(timeout=15) as client:
        rooms = (await client.get(f"{base}/_matrix/client/v3/joined_rooms", headers=headers)).json().get("joined_rooms", [])
        for rid in rooms:
            try:
                name = (await client.get(f"{base}/_matrix/client/v3/rooms/{rid}/state/m.room.name", headers=headers)).json().get("name", rid)
            except Exception:
                name = rid
            room_names[rid] = name
            try:
                msgs = (await client.get(f"{base}/_matrix/client/v3/rooms/{rid}/messages",
                                         headers=headers, params={"dir": "b", "limit": 100})).json()
            except Exception:
                continue
            for e in msgs.get("chunk", []):
                if e.get("type") == "m.room.message":
                    events.append({"room": name, "sender": e["sender"],
                                   "body": e.get("content", {}).get("body", ""),
                                   "ts": e.get("origin_server_ts", 0)})

    agents: dict[str, dict] = {}
    for ev in sorted(events, key=lambda x: x["ts"]):
        a = agents.setdefault(ev["sender"], {
            "id": ev["sender"], "name": ev["sender"].split(":")[0].lstrip("@"),
            "last_seen": 0, "messages": 0, "current_task": None, "blocked": None,
            "last_status": None, "usage": [], "daily": {},
        })
        a["last_seen"] = max(a["last_seen"], ev["ts"])
        a["messages"] += 1
        day = datetime.fromtimestamp(ev["ts"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        a["daily"][day] = a["daily"].get(day, 0) + 1
        body = ev["body"].strip()
        tag = body[1:body.index("]")].upper() if body.startswith("[") and "]" in body[:12] else ""
        text = {"body": body[:280], "room": ev["room"], "ts": ev["ts"]}
        if tag == "CLAIM":
            a["current_task"], a["blocked"] = text, None
        elif tag == "HANDOFF":
            a["current_task"] = None
        elif tag == "BLOCKED":
            a["blocked"] = text
        elif tag == "USAGE":
            a["usage"] = [u for u in a["usage"] if u.get("provider") != _parse_usage(body).get("provider")]
            a["usage"].append({**_parse_usage(body), "ts": ev["ts"]})
        elif tag == "STATUS":
            a["last_status"] = text
            if "done" in body[:40].lower():
                a["current_task"], a["blocked"] = None, None

    # Memory contribution counts per agent + wing activity.
    got = drawers.get(include=["metadatas"], limit=10000)
    drawer_counts, wing_counts = {}, {}
    for meta in got["metadatas"]:
        drawer_counts[meta.get("added_by", "?")] = drawer_counts.get(meta.get("added_by", "?"), 0) + 1
        if not meta.get("imported"):
            wing_counts[meta.get("wing", "?")] = wing_counts.get(meta.get("wing", "?"), 0) + 1
    for a in agents.values():
        a["drawers"] = drawer_counts.get(a["name"], 0)

    return {"generated_at": _now(),
            "agents": sorted(agents.values(), key=lambda a: -a["last_seen"]),
            "wing_activity": dict(sorted(wing_counts.items(), key=lambda x: -x[1])[:12])}


@app.get("/")
def dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# MCP streamable HTTP endpoint lives at /mcp on this same port.
app.mount("/", mcp.streamable_http_app())
