/* Hearth dashboard v2.
 *
 * Plain vanilla JS, no build step, no CDN (the CSP is default-src 'self'). Everything is
 * built with DOM APIs, never innerHTML, so agent-written text can never become markup.
 * Views: #overview (what needs you, who is awake, this week), #memory (palace map + search
 * + drawer detail), #agents (per-account cards), #relays (relays + checkpoints).
 */
"use strict";

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- tiny DOM helper
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "html") el.textContent = v; // never markup
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === "dataset") Object.assign(el.dataset, v);
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else el.setAttribute(k, v);
    }
  }
  for (const c of children.flat()) {
    if (c === undefined || c === null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

// ---------------------------------------------------------------- formatting
const toMs = (v) => (typeof v === "number" ? v : v ? Date.parse(v) : NaN);
function ago(v) {
  const ms = toMs(v);
  if (!ms || Number.isNaN(ms)) return "never";
  const m = Math.round((Date.now() - ms) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  if (m < 1440) return `${Math.round(m / 60)} h ago`;
  return `${Math.round(m / 1440)} d ago`;
}
function minutes(mins) {
  if (mins === null || mins === undefined) return "—";
  if (mins < 60) return `${mins} min`;
  if (mins < 1440) return `${Math.round(mins / 6) / 10} h`;
  return `${Math.round(mins / 144) / 10} d`;
}
function when(v) {
  const ms = toMs(v);
  if (!ms || Number.isNaN(ms)) return "";
  const d = new Date(ms);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const permalink = (roomId, eventId) => `https://matrix.to/#/${encodeURIComponent(roomId)}/${encodeURIComponent(eventId)}`;

// ---------------------------------------------------------------- state
const state = {
  route: "overview",
  days: 7,
  mem: { q: "", wing: "", room: "", classes: { knowledge: true, diary: false, archive: false, import: false },
         superseded: false, retracted: false, author: "" },
  authed: false,
  authEnabled: true,
  refreshTimer: null,
  lastRefresh: 0,
};
try {
  const saved = JSON.parse(localStorage.getItem("hearth.dashboard") || "{}");
  if (saved.days) state.days = saved.days;
  if (saved.mem) state.mem = { ...state.mem, ...saved.mem, classes: { ...state.mem.classes, ...(saved.mem.classes || {}) } };
} catch { /* storage unavailable: defaults are fine */ }
function persist() {
  try { localStorage.setItem("hearth.dashboard", JSON.stringify({ days: state.days, mem: state.mem })); } catch { /* ignore */ }
}

// ---------------------------------------------------------------- API
class AuthRequired extends Error {}
async function api(path, init) {
  const res = await fetch(path, init);
  if (res.status === 401) {
    showLogin("Your session expired. Please sign in again.");
    throw new AuthRequired("authentication required");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || data.error || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}
const settle = (p) => p.then((v) => ({ ok: true, v }), (e) => ({ ok: false, e }));

// ---------------------------------------------------------------- auth
function showLogin(message = "") {
  state.authed = false;
  $("dashboard").classList.add("hidden");
  $("login-shell").classList.remove("hidden");
  $("login-error").textContent = message;
  $("password").value = "";
  stopAutoRefresh();
}
function showDashboard(principal, authEnabled = true) {
  state.authed = true;
  state.authEnabled = authEnabled;
  $("login-shell").classList.add("hidden");
  $("dashboard").classList.remove("hidden");
  $("identity").textContent = principal ? `Signed in as ${principal}` : "Authentication disabled";
  $("logout").classList.toggle("hidden", !authEnabled);
  render();
  startAutoRefresh();
}
async function signIn(body) {
  $("login-error").textContent = "";
  $("login-button").disabled = true;
  try {
    const data = await api("/api/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    $("access-token").value = "";
    showDashboard(data.principal, data.auth_enabled !== false);
  } catch (err) {
    if (!(err instanceof AuthRequired)) $("login-error").textContent = err.message;
    else $("login-error").textContent = "Invalid username, password, or access token.";
  } finally {
    $("login-button").disabled = false;
  }
}

// ---------------------------------------------------------------- router + refresh
const VIEWS = { overview: renderOverview, memory: renderMemory, agents: renderAgents, relays: renderRelays };
function currentRoute() {
  const r = (location.hash || "#overview").slice(1).split("/")[0];
  return VIEWS[r] ? r : "overview";
}
async function render() {
  if (!state.authed) return;
  state.route = currentRoute();
  for (const a of $("tabs").querySelectorAll("a")) a.classList.toggle("active", a.dataset.route === state.route);
  closeDetail();
  const view = clear($("view"));
  view.append(h("p", { class: "dim", text: "Loading…" }));
  try {
    await VIEWS[state.route](view);
    state.lastRefresh = Date.now();
    stamp();
  } catch (err) {
    if (err instanceof AuthRequired) return;
    clear(view).append(h("div", { class: "empty", text: `Could not load this view: ${err.message}` }));
  }
}
function stamp() {
  $("stamp").textContent = state.lastRefresh ? `updated ${new Date(state.lastRefresh).toLocaleTimeString()} · refreshes every 5 min` : "";
}
function startAutoRefresh() {
  stopAutoRefresh();
  state.refreshTimer = setInterval(() => { if (document.visibilityState === "visible") render(); }, 5 * 60 * 1000);
}
function stopAutoRefresh() { if (state.refreshTimer) clearInterval(state.refreshTimer); state.refreshTimer = null; }

function banner(text) {
  const b = $("banner");
  if (!text) { b.classList.add("hidden"); b.textContent = ""; return; }
  b.textContent = text;
  b.classList.remove("hidden");
}

// ---------------------------------------------------------------- shared widgets
function section(title, hint, count, ...body) {
  const head = h("div", { class: "section-head" }, h("h2", { text: title }));
  if (count !== undefined && count !== null) head.append(h("span", { class: "count", text: String(count) }));
  if (hint) head.append(h("span", { class: "hint", text: hint }));
  return h("section", { class: "section" }, head, ...body);
}
const pill = (text, tone) => h("span", { class: `pill${tone ? ` ${tone}` : ""}`, text });
const classTone = { knowledge: "accent", diary: "info", archive: "", import: "violet" };
const classLabel = { knowledge: "knowledge", diary: "diary", archive: "archive", import: "import" };
function stateDot(s) { return h("span", { class: `dot ${s}`, title: s }); }
function chip(label, on, onToggle) {
  const c = h("label", { class: `chip${on ? " on" : ""}` }, label);
  const input = h("input", { type: "checkbox" });
  input.checked = on;
  input.addEventListener("change", () => onToggle(input.checked));
  c.prepend(input);
  return c;
}
function table(columns, rows, emptyText) {
  if (!rows.length) return h("div", { class: "empty", text: emptyText });
  return h("div", { class: "table-wrap" },
    h("table", null,
      h("thead", null, h("tr", null, ...columns.map((c) => h("th", { text: c.label })))),
      h("tbody", null, ...rows.map((r) => h("tr", null, ...columns.map((c) => h("td", null, c.cell(r))))))));
}

// ---------------------------------------------------------------- Overview
async function renderOverview(view) {
  const [health, status, inbox, surfaces, timeline] = await Promise.all([
    settle(api("/health")), settle(api("/api/status")), settle(api("/api/inbox")),
    settle(api("/api/surfaces")), settle(api(`/api/timeline?days=${state.days}`)),
  ]);
  for (const r of [health, status, inbox, surfaces, timeline]) if (!r.ok && r.e instanceof AuthRequired) throw r.e;
  clear(view);
  const observerDown = !inbox.ok && inbox.e?.status === 503;
  banner(observerDown ? "Room activity is unavailable: the dashboard's Matrix observer is not configured. Run `hearth dashboard configure` on the hub." : "");

  // Health tiles
  const hv = health.ok ? health.v : {};
  const sv = status.ok ? status.v : {};
  const classes = sv.classes || {};
  const alive = surfaces.ok ? surfaces.v.surfaces : [];
  const scheduled = alive.filter((s) => s.expected_every_minutes);
  const okCount = scheduled.filter((s) => s.state === "ok").length;
  const tiles = h("div", { class: "tiles" },
    tile("Chat server", hv.homeserver || "?", hv.homeserver === "ok" ? "ok" : "bad", hv.version ? `memory ${hv.version}` : ""),
    tile("Memory", hv.memory || "?", hv.memory === "ok" ? "ok" : "bad", `${plural(hv.checkpoints ?? 0, "checkpoint")} · ${plural(hv.relays ?? 0, "relay")}`),
    tile("Drawers", String(sv.total_drawers ?? hv.drawers ?? "?"), "", classes.knowledge !== undefined
      ? `${classes.knowledge} knowledge · ${classes.diary || 0} diary · ${classes.import || 0} imported`
      : ""),
    tile("Scheduled surfaces", scheduled.length ? `${okCount} / ${scheduled.length}` : "—",
      scheduled.length ? (okCount === scheduled.length ? "ok" : okCount === 0 ? "bad" : "warn") : "",
      scheduled.length ? "ticking on time" : "no scheduled surfaces seen"),
  );
  view.append(tiles);

  // Waiting on you
  const items = inbox.ok ? inbox.v.items : [];
  const inboxBody = items.length
    ? h("div", { class: "inbox" }, ...items.map(inboxRow))
    : h("div", { class: "empty", text: observerDown ? "Unavailable until the observer is configured." : "Nothing is waiting on you right now." });
  view.append(section("Waiting on you",
    "Plans to approve, agents that are stuck, questions addressed to you, and tasks nobody has picked up. React in Element to clear one: a thumbs-up or thumbs-down on a plan decides it, a check mark on anything else marks it seen or drops an unclaimed task. An agent's own later [STATUS] or [OUTCOME] clears its items, and so does any post that cites the item's event id.",
    inbox.ok ? inbox.v.total : null, inboxBody));

  // Who is awake
  const rows = alive.slice().sort((a, b) => rank(a.state) - rank(b.state) || a.agent.localeCompare(b.agent));
  view.append(section("Who is awake",
    "One row per agent and machine. A surface is late after 1.5× its expected cadence and stalled after 3×.",
    alive.length || null,
    table([
      { label: "", cell: (s) => stateDot(s.state) },
      { label: "Agent · surface", cell: (s) => h("span", null, h("b", { text: s.agent }), ` @ ${s.surface}`, s.roles.length ? h("span", { class: "dim", text: ` (${s.roles.join(", ")})` }) : "") },
      { label: "State", cell: (s) => pill(s.state, { ok: "ok", late: "warn", stalled: "bad", "on-demand": "info" }[s.state] || "") },
      { label: "Last seen", cell: (s) => h("span", { title: s.last_seen_at || "" }, s.last_seen_at ? ago(s.last_seen_at) : "never") },
      { label: "Expected", cell: (s) => s.expected_every_minutes ? `every ${minutes(s.expected_every_minutes)}` : h("span", { class: "dim", text: "on demand" }) },
      { label: "Last post", cell: (s) => s.last_post_at ? h("span", null, s.last_post_tag ? pill(s.last_post_tag.split(/[\s/-]/)[0]) : "", ` ${s.last_post_room || ""} · ${ago(s.last_post_at)}`) : h("span", { class: "dim", text: "—" }) },
      { label: "Checkpoint", cell: (s) => s.checkpoint_at ? h("span", { title: s.monitors.join(", ") }, ago(s.checkpoint_at)) : h("span", { class: "dim", text: "—" }) },
    ], rows, observerDown ? "Unavailable until the observer is configured." : "No agent activity in the observed rooms yet.")));

  // Timeline
  const dayChips = h("div", { class: "chips" }, ...[7, 14, 30].map((d) =>
    h("span", { class: `chip${state.days === d ? " on" : ""}`, text: `${d} days`, onClick: () => { state.days = d; persist(); render(); } })));
  const tl = timeline.ok ? timeline.v.items : [];
  view.append(section("Decisions, outcomes and lessons",
    "What the team decided, what came of earlier decisions, and what it learned. From the rooms and from memory.",
    tl.length || null, dayChips,
    tl.length ? h("div", { class: "timeline", style: { marginTop: ".6rem" } }, ...tl.map(timelineRow))
      : h("div", { class: "empty", text: "Nothing filed in this window." })));

  view.append(h("p", { class: "foot-note", text: "The dashboard is an overview. Open the room or the drawer before acting on a truncated card." }));
}
const rank = (s) => ({ stalled: 0, late: 1, ok: 2, "on-demand": 3, unknown: 4 })[s] ?? 5;
function tile(label, value, tone, sub) {
  return h("div", { class: "tile" }, h("div", { class: "label", text: label }),
    h("div", { class: `value ${tone || ""}`, text: value }), sub ? h("div", { class: "sub", text: sub }) : null);
}
function inboxRow(i) {
  const kindText = { approval: "Approve", blocked: "Blocked", question: "Question", unclaimed_task: "Unclaimed" }[i.kind] || i.kind;
  return h("div", { class: `inbox-item ${i.kind}` },
    h("div", { class: "kind" }, kindText, h("small", { text: i.label })),
    h("div", null,
      h("div", { class: "who" }, h("b", { text: i.sender }), i.surface ? ` @ ${i.surface}` : "", ` in ${i.room}`, i.tag ? [" · ", pill(i.tag)] : ""),
      h("div", { class: "body", text: i.body })),
    h("div", { class: "meta" }, `waiting ${minutes(i.age_minutes)}`, h("br"),
      h("a", { href: permalink(i.room_id, i.event_id), target: "_blank", rel: "noopener", text: "open in Element" })));
}
function timelineRow(i) {
  const tone = { Decision: "accent", Outcome: "ok", Lesson: "info", Plan: "violet" }[i.kind] || "";
  const body = h("div", { class: "body clamp", text: i.body });
  body.addEventListener("click", () => body.classList.toggle("clamp"));
  const link = i.event_id
    ? h("a", { href: permalink(i.room_id, i.event_id), target: "_blank", rel: "noopener", text: i.room })
    : h("button", { class: "link", text: `${i.wing}/${i.room}`, onClick: () => openDrawer(i.drawer_id) });
  return h("div", { class: "tl-item" },
    h("div", null, pill(i.kind, tone), h("div", { class: "when", text: when(i.at) })),
    h("div", null, h("div", { class: "who" }, h("b", { text: i.who }), i.human ? " (human) · " : " · ", link,
      i.source === "memory" ? h("span", { class: "dim", text: " · memory" }) : ""), body));
}

// ---------------------------------------------------------------- Memory
let taxonomyCache = null;
async function renderMemory(view) {
  const tax = taxonomyCache || (taxonomyCache = await api("/api/taxonomy"));
  clear(view);
  const grid = h("div", { class: "memory" });
  const palace = h("aside", { class: "card palace" });
  const main = h("div");
  grid.append(palace, main);
  view.append(grid);
  renderPalace(palace, tax);
  renderSearch(main);
  await runSearch(main.querySelector(".results"));
}
function renderPalace(el, tax) {
  clear(el);
  el.append(h("div", { class: "section-head" }, h("h2", { text: "Palace map" })),
    h("p", { class: "dim", style: { fontSize: ".8rem", marginBottom: ".5rem" }, text: `${tax.total_drawers} drawers. A wing is a project, a room is a kind of fact. Click to filter.` }),
    h("div", { class: "legend" }, ...Object.keys(classLabel).map((c) => h("span", null, h("i", { class: c, style: { background: `var(--${{ knowledge: "accent", diary: "info", archive: "dim", import: "violet" }[c]})` } }), classLabel[c]))));
  const all = h("div", { class: `wing${!state.mem.wing ? " on" : ""}` }, h("b", { text: "All wings" }), h("span", { class: "n", text: String(tax.total_drawers) }));
  all.addEventListener("click", () => { state.mem.wing = ""; state.mem.room = ""; persist(); render(); });
  el.append(all);
  for (const w of tax.wings) {
    const row = h("div", { class: `wing${state.mem.wing === w.wing && !state.mem.room ? " on" : ""}` }, h("b", { text: w.wing, title: w.wing }), h("span", { class: "n", text: String(w.total) }));
    row.addEventListener("click", () => { state.mem.wing = w.wing; state.mem.room = ""; persist(); render(); });
    const bar = h("div", { class: "classbar" });
    for (const [cls, n] of Object.entries(w.classes)) bar.append(h("i", { class: cls, style: { width: `${(100 * n) / w.total}%` }, title: `${n} ${cls}` }));
    el.append(row, bar);
    if (state.mem.wing === w.wing) {
      const rooms = h("div", { class: "rooms" });
      for (const r of w.rooms) {
        const rr = h("div", { class: `room${state.mem.room === r.room ? " on" : ""}` }, h("span", { text: r.room }),
          h("span", { class: "n", text: `${r.total}${r.superseded ? ` · ${r.superseded} old` : ""}` }));
        rr.addEventListener("click", () => { state.mem.room = r.room; persist(); render(); });
        rooms.append(rr);
      }
      el.append(rooms);
    }
  }
}
function renderSearch(main) {
  const m = state.mem;
  const q = h("input", { type: "search", placeholder: "Search memory… ids and $event ids are matched exactly. Empty shows the newest drawers.", value: m.q });
  const author = h("input", { type: "text", placeholder: "author", value: m.author, style: { width: "9rem" } });
  const go = h("button", { text: "Search" });
  const results = h("div", { class: "results" });
  const run = () => { m.q = q.value.trim(); m.author = author.value.trim(); persist(); runSearch(results); };
  q.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  author.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  go.addEventListener("click", run);
  const chips = h("div", { class: "chips" },
    ...Object.keys(classLabel).map((c) => chip(classLabel[c], m.classes[c], (on) => { m.classes[c] = on; persist(); runSearch(results); })),
    h("span", { class: "dim", text: "·" }),
    chip("show superseded", m.superseded, (on) => { m.superseded = on; persist(); runSearch(results); }),
    chip("show retracted", m.retracted, (on) => { m.retracted = on; persist(); runSearch(results); }));
  const scope = h("div", { class: "dim", style: { fontSize: ".82rem", margin: ".3rem 0 .6rem" } });
  updateScope(scope);
  main.append(h("div", { class: "searchbar" }, q, author, go), chips, scope, results);
}
function updateScope(el) {
  const m = state.mem;
  clear(el);
  if (!m.wing) { el.append("Scope: all wings"); return; }
  el.append(`Scope: ${m.wing}${m.room ? ` / ${m.room}` : ""} `, h("button", { class: "link", text: "clear", onClick: () => { m.wing = ""; m.room = ""; persist(); render(); } }));
}
async function runSearch(results) {
  const m = state.mem;
  clear(results).append(h("p", { class: "dim", text: "Searching…" }));
  const params = new URLSearchParams();
  if (m.wing) params.set("wing", m.wing);
  if (m.room) params.set("room", m.room);
  if (m.author) params.set("added_by", m.author);
  let entries;
  let note = "";
  try {
    if (m.q) {
      params.set("q", m.q);
      params.set("limit", "25");
      params.set("include_diaries", String(m.classes.diary));
      params.set("include_archives", String(m.classes.archive));
      params.set("include_imports", String(m.classes.import));
      params.set("include_superseded", String(m.superseded));
      params.set("include_retracted", String(m.retracted));
      const data = await api(`/api/search?${params}`);
      entries = data.results;
      if (!m.classes.knowledge) entries = entries.filter((e) => e.record_class !== "knowledge");
      note = `${plural(entries.length, "result")}${data.exact_matches ? ` · ${data.exact_matches} exact` : ""}${data.excluded_by_default.length ? ` · hidden by default: ${data.excluded_by_default.join(", ")}` : ""}`;
    } else {
      params.set("limit", "40");
      const wanted = Object.entries(m.classes).filter(([, on]) => on).map(([c]) => c);
      if (wanted.length === 1) params.set("record_class", wanted[0]);
      else if (m.classes.import) params.set("include_imports", "true");
      const data = await api(`/api/recent?${params}`);
      entries = data.entries.filter((e) => m.classes[e.record_class] !== false);
      if (!m.superseded) entries = entries.filter((e) => e.is_current !== false);
      if (!m.retracted) entries = entries.filter((e) => !e.retracted);
      note = `Newest ${plural(entries.length, "drawer")}`;
    }
  } catch (err) {
    if (err instanceof AuthRequired) return;
    clear(results).append(h("div", { class: "empty", text: err.message }));
    return;
  }
  clear(results);
  results.append(h("p", { class: "dim", style: { fontSize: ".82rem", marginBottom: ".5rem" }, text: note }));
  if (!entries.length) results.append(h("div", { class: "empty", text: "No drawers match." }));
  for (const e of entries) results.append(drawerCard(e));
}
function drawerCard(e) {
  const card = h("div", { class: `drawer${e.is_current === false ? " superseded" : ""}${e.retracted ? " retracted" : ""}` });
  const head = h("div", { class: "head" },
    h("b", { text: `${e.wing || "?"} / ${e.room || "?"}` }),
    pill(classLabel[e.record_class] || e.record_class, classTone[e.record_class]),
    e.match === "exact" ? pill("exact match", "ok") : null,
    e.is_current === false ? pill("superseded", "warn") : null,
    e.retracted ? pill("retracted", "bad") : null,
    h("span", null, e.added_by || "", e.surface ? h("span", { class: "dim", text: ` (${e.surface})` }) : ""),
    h("span", { title: e.created_at || "", text: ago(e.created_at) }),
    e.distance !== undefined && e.match !== "exact" ? h("span", { class: "dim", title: "cosine distance, lower is closer", text: `d=${e.distance}` }) : null);
  const content = h("div", { class: "content clamp", text: e.content || "" });
  const foot = h("div", { class: "foot" },
    e.source ? h("span", { class: "src", title: e.source, text: `source: ${e.source}` }) : h("span", { class: "dim", text: "no source" }),
    h("span", { class: "mono", text: e.drawer_id }));
  card.append(head, content, foot);
  card.addEventListener("click", () => openDrawer(e.drawer_id));
  return card;
}
async function openDrawer(id) {
  const panel = $("detail");
  clear(panel).append(h("p", { class: "dim", text: "Loading…" }));
  panel.classList.remove("hidden");
  let d;
  try { d = await api(`/api/drawer/${encodeURIComponent(id)}`); }
  catch (err) { if (err instanceof AuthRequired) return; clear(panel).append(h("p", { class: "bad", text: err.message })); return; }
  clear(panel);
  panel.append(h("button", { class: "secondary small close", text: "✕", onClick: closeDetail }));
  panel.append(h("div", { class: "head", style: { display: "flex", gap: ".5rem", flexWrap: "wrap", alignItems: "center", marginTop: ".4rem" } },
    pill(classLabel[d.record_class] || d.record_class, classTone[d.record_class]),
    d.is_current === false ? pill("superseded", "warn") : pill("current", "ok"),
    d.retracted ? pill("retracted", "bad") : null));
  panel.append(h("h3", { text: `${d.wing} / ${d.room}` }));
  panel.append(h("div", { class: "content", text: d.content }));
  const dl = h("dl", null,
    h("dt", { text: "Drawer" }), h("dd", { class: "mono", text: d.drawer_id }),
    h("dt", { text: "Written by" }), h("dd", { text: `${d.added_by || "?"}${d.surface ? ` (${d.surface})` : ""}` }),
    h("dt", { text: "When" }), h("dd", { text: `${when(d.created_at)} · ${ago(d.created_at)}` }),
    h("dt", { text: "Source" }), h("dd", { text: d.source || "—" }));
  if (d.imported) dl.append(h("dt", { text: "Imported" }), h("dd", { text: "yes" }));
  if (d.retracted) {
    dl.append(h("dt", { text: "Retracted by" }), h("dd", { text: `${d.retracted_by || "?"} · ${ago(d.retracted_at)}` }),
      h("dt", { text: "Reason" }), h("dd", { text: d.retraction_reason || "—" }));
  }
  panel.append(dl);
  if (d.supersession) {
    const chain = h("div", { class: "chain" });
    d.supersession.chain.forEach((cid, idx) => {
      const node = h("div", { class: `node${cid === d.supersession.current ? " current" : ""}` },
        h("span", { class: "dim", text: `${idx + 1}.` }),
        cid === d.drawer_id ? h("span", { class: "mono", text: `${cid} (this)` }) : h("button", { class: "link mono", text: cid, onClick: () => openDrawer(cid) }),
        cid === d.supersession.current ? pill("current", "ok") : null);
      chain.append(node);
    });
    panel.append(h("h3", { text: "History of this fact" }), h("p", { class: "dim", style: { fontSize: ".82rem" }, text: "Oldest first. The current version is what agents should act on." }), chain);
  }
}
function closeDetail() { const p = $("detail"); p.classList.add("hidden"); clear(p); }

// ---------------------------------------------------------------- Agents
async function renderAgents(view) {
  let data;
  try { data = await api("/api/agents"); }
  catch (err) {
    if (err instanceof AuthRequired) throw err;
    clear(view).append(h("div", { class: "empty", text: err.status === 503 ? "Room activity is unavailable: the observer is not configured (run `hearth dashboard configure`)." : err.message }));
    return;
  }
  clear(view);
  const agents = data.agents.filter((a) => a.kind === "agent");
  const humans = data.agents.filter((a) => a.kind === "human");
  view.append(section("Agents", "One card per account. Surfaces (machines) are listed inside each card.", agents.length,
    h("div", { class: "agents" }, ...agents.map(agentCard))));
  if (humans.length) view.append(section("People", null, humans.length,
    h("div", { class: "people" }, ...humans.map((p) => h("span", { class: "person" }, h("b", { text: p.name }), ` · ${plural(p.messages, "message")} · last ${ago(p.last_seen)}`)))));
  const wings = Object.entries(data.wing_activity || {});
  if (wings.length) {
    const max = Math.max(1, ...wings.map(([, v]) => v));
    view.append(section("Where knowledge is being written", "Knowledge drawers per wing (imports, diaries and archives excluded).", null,
      h("div", { class: "card" }, ...wings.map(([k, v]) => gaugeRow(k, String(v), (100 * v) / max)))));
  }
}
function agentCard(a) {
  const fresh = Date.now() - a.last_seen;
  const tone = fresh < 3600e3 ? "ok" : fresh < 86400e3 ? "late" : "stalled";
  const card = h("div", { class: "card" });
  card.append(h("div", { class: "agent-head" }, stateDot(tone), h("span", { class: "agent-name", text: a.name }),
    h("span", { class: "agent-meta" }, `last seen ${ago(a.last_seen)}`, h("br"), `${plural(a.messages, "msg")} · ${plural(a.drawers, "drawer")}`)));
  card.append(sparkline(a.daily));
  if (a.blocked) card.append(field("Blocked", a.blocked, "bad"));
  card.append(field(a.awaiting_approval ? "Working on · waiting for approval" : "Working on", a.current_task, a.awaiting_approval ? "warn" : "", "nothing claimed"));
  card.append(field("Last status", a.last_status, "", "—"));
  if (a.last_heartbeat) card.append(field("Last heartbeat", a.last_heartbeat));
  if (a.surfaces?.length) {
    card.append(h("div", { class: "field" }, h("b", { text: "Surfaces" }),
      ...a.surfaces.map((s) => h("div", null, stateDot(s.state), `${s.surface}`, s.roles.length ? h("span", { class: "dim", text: ` (${s.roles.join(", ")})` }) : "", h("span", { class: "dim", text: ` · ${s.last_seen_at ? ago(s.last_seen_at) : "never"}` })))));
  }
  for (const u of a.usage || []) card.append(gauge(u));
  return card;
}
function field(label, item, tone, emptyText) {
  const f = h("div", { class: "field" }, h("b", { class: tone || "", text: label }));
  if (!item) { f.append(h("span", { class: "dim", text: emptyText || "—" })); return f; }
  const span = h("span", { class: "clamp", text: item.body });
  span.addEventListener("click", () => span.classList.toggle("clamp"));
  f.append(span, h("i", { class: "dim", style: { fontSize: ".78rem" } }, `${item.room} · ${ago(item.ts)}`,
    item.room_id ? [" · ", h("a", { href: permalink(item.room_id, item.event_id), target: "_blank", rel: "noopener", text: "open" })] : ""));
  return f;
}
function sparkline(daily) {
  const days = [...Array(14)].map((_, i) => new Date(Date.now() - (13 - i) * 86400e3).toISOString().slice(0, 10));
  const values = days.map((d) => daily?.[d] || 0);
  const max = Math.max(1, ...values);
  const W = 300, H = 34, bw = W / days.length;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "spark");
  svg.setAttribute("aria-label", "messages per day, last 14 days");
  values.forEach((v, i) => {
    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    const hgt = Math.max(v ? 2 : 0, (v / max) * (H - 2));
    r.setAttribute("x", String(i * bw + 1)); r.setAttribute("y", String(H - hgt));
    r.setAttribute("width", String(bw - 2)); r.setAttribute("height", String(hgt));
    r.setAttribute("rx", "1.5"); r.setAttribute("fill", "var(--accent)");
    const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
    t.textContent = `${days[i]}: ${v}`;
    r.append(t);
    svg.append(r);
  });
  return svg;
}
function gaugeRow(label, detail, pct) {
  const bar = h("div", { class: "bar" }, h("i", { style: { width: `${Math.min(pct, 100)}%` } }));
  return h("div", { class: "gauge" }, h("div", { class: "lbl" }, h("span", { text: label }), h("span", { text: detail })), bar);
}
function gauge(u) {
  const pct = u.pct ?? null;
  const label = [u.provider, u.period].filter(Boolean).join(" · ") || "usage";
  const detail = u.used && u.limit ? `${u.used} / ${u.limit}` : "self-reported";
  const row = gaugeRow(label, `${detail}${pct !== null ? ` (${pct}%)` : ""} · ${ago(u.ts)}`, pct ?? 0);
  row.querySelector("i").style.background = pct === null ? "var(--dim)" : pct < 70 ? "var(--ok)" : pct < 90 ? "var(--warn)" : "var(--bad)";
  return row;
}

// ---------------------------------------------------------------- Relays
async function renderRelays(view) {
  const [relays, checkpoints] = await Promise.all([api("/api/relays"), api("/api/checkpoints")]);
  clear(view);
  const open = relays.entries.filter((r) => r.state !== "resolved");
  const done = relays.entries.filter((r) => r.state === "resolved");
  const relayCols = [
    { label: "State", cell: (r) => pill(r.state, { queued: "warn", claimed: "info", resolved: "ok" }[r.state]) },
    { label: "Priority", cell: (r) => pill(r.priority, { urgent: "bad", high: "accent" }[r.priority] || "") },
    { label: "For", cell: (r) => h("b", { text: r.target_agent }) },
    { label: "From", cell: (r) => `${r.requested_by}${r.source_surface ? ` @ ${r.source_surface}` : ""}` },
    { label: "Request", cell: (r) => h("span", { style: { whiteSpace: "pre-wrap" }, text: r.request }) },
    { label: "Age", cell: (r) => h("span", { title: r.created_at }, ago(r.created_at)) },
    { label: "Outcome", cell: (r) => r.outcome ? h("span", { text: r.outcome }) : h("span", { class: "dim", text: r.state === "claimed" ? `claimed by ${r.claimed_surface || r.claimed_by}` : "—" }) },
  ];
  view.append(section("Open relays", "Work an agent queued for its own next interactive session. A relay is a durable note, not a wake-up call.", open.length,
    table(relayCols, open, "No open relays.")));
  view.append(section("Resolved relays", null, done.length, table(relayCols, done.slice(0, 30), "Nothing resolved yet.")));
  view.append(section("Checkpoints", "Replaceable state for recurring monitors. The age tells you when a monitor last ran.", checkpoints.count,
    table([
      { label: "Agent · surface", cell: (c) => h("span", null, h("b", { text: c.agent }), c.surface ? ` @ ${c.surface}` : "") },
      { label: "Monitor", cell: (c) => c.monitor },
      { label: "Updated", cell: (c) => h("span", { title: c.updated_at }, ago(c.updated_at)) },
      { label: "State", cell: (c) => { const s = h("span", { class: "clamp", style: { whiteSpace: "pre-wrap", display: "-webkit-box" }, text: c.content }); s.addEventListener("click", () => s.classList.toggle("clamp")); return s; } },
    ], checkpoints.entries, "No checkpoints yet.")));
}

// ---------------------------------------------------------------- boot
$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  signIn({ username: $("username").value.trim(), password: $("password").value });
});
$("token-button").addEventListener("click", () => signIn({ token: $("access-token").value.trim() }));
$("logout").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  showLogin();
});
$("refresh").addEventListener("click", () => { taxonomyCache = null; render(); });
window.addEventListener("hashchange", render);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });

fetch("/api/auth/status")
  .then((res) => res.json())
  .then((auth) => {
    if (auth.authenticated || !auth.auth_enabled) showDashboard(auth.principal, auth.auth_enabled);
    else if (!auth.matrix_login_available) $("login-error").textContent = "Matrix sign-in is unavailable; use an access token.";
  })
  .catch(() => showLogin("Hearth Memory is unavailable."));
