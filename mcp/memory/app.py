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

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import chromadb
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

DATA_DIR = os.environ.get("HEARTH_DATA_DIR", "./data")
HOMESERVER_URL = os.environ.get("HEARTH_HOMESERVER_URL", "")

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


@app.get("/")
def dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# MCP streamable HTTP endpoint lives at /mcp on this same port.
app.mount("/", mcp.streamable_http_app())
