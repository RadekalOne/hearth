/* Durable work views. The existing dashboard owns authentication and Matrix actions. */
"use strict";
let selectedProject = window.history.state?.projectId || "";
let workMode = "board";
const workStates = ["draft", "ready", "running", "blocked", "review", "done", "cancelled"];
const workLabels = { draft: "Proposed", ready: "Approved", running: "In progress", blocked: "Blocked", review: "Needs your review", done: "Done", cancelled: "Cancelled" };
const workPhases = { idea: "Idea", design: "Design", build: "Building", validate: "Checking", shipped: "Delivered" };
const personName = value => (value || "").replace(/^@/, "").split(":")[0];
function isSignedInPerson(value) {
  const viewer = state.principal;
  return Boolean(viewer && value && (viewer === value ||
    ((!viewer.includes(":") || !value.includes(":")) && personName(viewer) === personName(value))));
}
const workTaskLink = task => `#projects/${encodeURIComponent(task.project_id)}/${encodeURIComponent(task.id)}`;
const workProjectLink = id => `#projects/${encodeURIComponent(id)}`;
const historyActor = actor => isSignedInPerson(actor) ? "You" : personName(actor) || "Someone";
function projectWorkForViewer(board) {
  if (!board.can_manage || state.principal === "admin") return board;
  const projectsOwned = new Set(board.projects.filter(p => isSignedInPerson(p.created_by)).map(p => p.id));
  const tasks = board.tasks.filter(t => projectsOwned.has(t.project_id) ||
    [t.created_by, t.authorized_by, t.reviewed_by].some(isSignedInPerson));
  const joined = new Set(tasks.map(t => t.project_id));
  const taskIds = new Set(tasks.map(t => t.id));
  return { ...board, tasks, projects: board.projects.filter(p => projectsOwned.has(p.id) || joined.has(p.id)),
    activity: board.activity.filter(e => e.task_id ? taskIds.has(e.task_id) : projectsOwned.has(e.project_id) || isSignedInPerson(e.actor)) };
}
function workPlainText(value) {
  return (value || "").split(/^(?:--- )?Technical details?\b[^\n]*/im, 1)[0].trim();
}
function workSummaryLine(task) {
  const source = workPlainText(task.state === "review" ? task.summary : task.description);
  const first = source.split(/\r?\n/).find(line => line.trim()) || task.acceptance || "";
  const text = first.replace(/^what(?: (?:i found|changed))?[.:]\s*/i, "").trim();
  return text.length > 200 ? `${text.slice(0, 197).trimEnd()}…` : text;
}
const workEventText = {
  task_proposed: "proposed", ready: "approved", claim: "started", review: "asked you to review",
  accept: "accepted", revise: "asked for changes to", release: "returned to proposals",
  block: "reported a blocker on", assign: "assigned", comment: "added a note to",
  withdraw: "withdrew approval for", cancel: "cancelled", reopen: "reopened",
  memory_captured: "saved a lesson from", phase: "updated the stage of",
  project_created: "created", project_phase: "updated the stage of", project_category: "changed the category of",
  heartbeat: "checked in on",
};
function workActivity(events, board) {
  const taskTitles = new Map(board.tasks.map(t => [t.id, t.title]));
  const projectTitles = new Map(board.projects.map(p => [p.id, p.title]));
  const routine = new Set(["heartbeat", "phase", "project_phase"]);
  const groups = [];
  for (const item of events) {
    const previous = groups.at(-1);
    if (routine.has(item.kind) && previous && previous.item.kind === item.kind &&
        previous.item.task_id === item.task_id && previous.item.project_id === item.project_id && previous.item.actor === item.actor) {
      previous.count += 1;
    } else groups.push({ item, count: 1 });
  }
  const recent = h("div", { class: "work-history" }, ...groups.slice(0, 12).map(({item, count}) => {
    const title = taskTitles.get(item.task_id) || projectTitles.get(item.project_id) || "this work";
    const sentence = `${historyActor(item.actor)} ${workEventText[item.kind] || "updated"} ${title}${count > 1 ? ` (${count} times)` : ""}.`;
    return h("div", { class: "history-entry" }, h("p", { text: sentence }), h("small", { class: "dim", text: when(item.at) }));
  }));
  if (!groups.length) recent.append(h("p", { class: "empty", text: "Changes to this work will appear here." }));
  return h("div", null, recent, h("details", null, h("summary", { text: "Show full history" }),
    h("div", { class: "work-history" }, ...events.map(item => h("article", { class: "card" },
      h("p", { text: `${item.actor} · ${when(item.at)} · ${item.kind}` }),
      h("pre", { class: "work-prose", text: JSON.stringify(item, null, 2) }))))));
}
const workTone = s => s === "done" ? "ok" : s === "blocked" ? "bad" : s === "review" ? "warn" : "";
const workPost = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const capabilityLabels = { coding: "Coding", design: "Design", planning: "Planning & coordination", research: "Research", review: "Review & testing", writing: "Writing" };
const modeLabels = { either: "Either", interactive: "Interactive", background: "Background" };
const availabilityLabels = { unknown: "Availability unconfirmed", accepting: "Accepting work", paused: "Paused" };

function capabilitySelect(value = "") {
  return h("select", null, h("option", { value: "", selected: !value, text: "No specific strength" }),
    ...Object.entries(capabilityLabels).map(([id, label]) => h("option", { value: id, text: label, selected: id === value })));
}
function modeSelect(value = "either") {
  return h("select", null, ...Object.entries(modeLabels).map(([id, label]) => h("option", { value: id, text: label, selected: id === value })));
}
function assignmentSuggestions(assignee, capability, mode) {
  const box = h("div", { class: "work-suggestions", "aria-live": "polite" });
  let request = 0;
  async function update() {
    const version = ++request;
    clear(box);
    if (!capability.value) { box.append(h("p", { class: "dim", text: "Choose a strength to see suggested agents. You choose who receives the task." })); return; }
    box.append(h("p", { class: "dim", text: "Checking profiles and team workload…" }));
    try {
      const data = await api(`/api/work/agents?capability=${encodeURIComponent(capability.value)}&work_mode=${encodeURIComponent(mode.value)}`);
      if (version !== request) return;
      clear(box).append(h("strong", { text: "Suggested matches" }));
      if (!data.suggestions.length) box.append(h("p", { class: "dim", text: "No matching profile yet. Update strengths in Agents, or choose an agent yourself." }));
      data.suggestions.forEach(s => box.append(h("div", { class: "work-match" },
        h("button", { type: "button", class: "secondary small", text: `Choose ${s.agent}`, onClick: () => {
          assignee.value = s.agent; assignee.dispatchEvent(new Event("change"));
        } }), h("span", { text: s.reason }),
        h("small", { class: "dim", text: `Assessment: ${s.source} · ${when(s.updated_at)}` }))));
      box.append(h("small", { class: "dim", text: "Based on maintained profiles; workload includes all projects. Confirm access, availability and budget before authorizing." }));
    } catch (err) { if (version === request) { clear(box); workMessage(box, err); } }
  }
  capability.addEventListener("change", update); mode.addEventListener("change", update);
  assignee.addEventListener("change", () => {
    box.querySelectorAll("button").forEach(b => { b.setAttribute("aria-pressed", String(b.textContent === `Choose ${assignee.value}`)); });
  });
  update();
  return box;
}

async function renderAgentCapabilities(view) {
  const data = await api("/api/work/agents");
  const directory = h("section", { class: "capability-directory" }, h("h1", { text: "Agent strengths" }),
    h("p", { class: "dim", text: "A simple guide to choosing teammates. Strengths are human assessments; interactive/background describes working style. Declared availability is separate from observed activity." }));
  const filter = capabilitySelect(); filter.setAttribute("aria-label", "Filter agent strengths");
  const cards = h("div", { class: "agents" });
  function show() {
    clear(cards);
    data.profiles.filter(p => !filter.value || [...p.strengths, ...p.supporting].includes(filter.value)).forEach(p => {
      const card = h("div", { class: "card capability-card" }, h("h3", { text: p.id }),
        h("div", { class: "capability-tags" }, ...p.strengths.map(s => pill(capabilityLabels[s], "ok"))));
      if (!p.strengths.length) card.append(h("p", { class: "dim", text: "Strengths not assessed yet" }));
      if (p.supporting.length) card.append(h("p", { class: "dim", text: `Also useful for: ${p.supporting.map(s => capabilityLabels[s]).join(", ")}` }));
      card.append(h("p", { text: `${p.updated_at ? modeLabels[p.work_mode] : "Working style unassessed"} · ${availabilityLabels[p.availability]}` }),
        h("p", { class: "dim", text: `${p.workload.running} in progress · ${p.workload.ready} approved · ${p.workload.review} need review · ${p.workload.blocked} blocked` }));
      if (p.notes) card.append(h("p", { class: "work-prose", text: p.notes }));
      if (p.updated_at) card.append(h("small", { class: "dim work-prose", text: `Assessment: ${p.source || "Not provided"} · ${p.updated_by} · ${when(p.updated_at)}` }));
      if (data.can_manage) card.append(h("button", { class: "secondary small", text: `Edit ${p.id} profile`, onClick: () => editAgentProfile(directory, p) }));
      cards.append(card);
    });
    if (!cards.childElementCount) cards.append(h("p", { class: "empty", text: "No agent has this strength listed yet." }));
  }
  filter.addEventListener("change", show); directory.append(filter, cards); view.append(directory); show();
}
function editAgentProfile(parent, profile) {
  if (parent.querySelector("form")) { parent.querySelector("input,textarea,select")?.focus(); return; }
  const skills = Object.entries(capabilityLabels).map(([id, label]) => {
    const input = h("select", null, ...[["", "Not listed"], ["strength", "Strength"], ["supporting", "Supporting"]].map(([value, text]) =>
      h("option", { value, text, selected: value === (profile.strengths.includes(id) ? "strength" : profile.supporting.includes(id) ? "supporting" : "") })));
    return { id, input, field: workField(label, input) };
  });
  const mode = modeSelect(profile.work_mode);
  const availability = h("select", null, ...Object.entries(availabilityLabels).map(([value, text]) => h("option", { value, text, selected: value === profile.availability })));
  const source = h("textarea", { rows: 2, maxlength: 2000, value: profile.source, placeholder: "Your assessment or a reviewed task/result. Required when listing a skill." });
  const notes = h("textarea", { rows: 2, maxlength: 2000, value: profile.notes, placeholder: "Useful constraints, access limits or examples" });
  workForm(parent, `${profile.id} · capability profile`, [h("p", { class: "dim", text: "Choose up to three main strengths. Use supporting skills for the rest. Assess the configured agent and its tools, not just the model name." }),
    h("div", { class: "profile-skills" }, ...skills.map(s => s.field)), workField("Preferred working style", mode), workField("Declared availability", availability), workField("Assessment basis", source), workField("Notes (optional)", notes)],
    () => workPost(`/api/work/agents/${encodeURIComponent(profile.id)}/profile`, { strengths: skills.filter(s => s.input.value === "strength").map(s => s.id),
      supporting: skills.filter(s => s.input.value === "supporting").map(s => s.id), work_mode: mode.value, availability: availability.value, source: source.value, notes: notes.value }));
}

function workMessage(parent, err) {
  let el = parent.querySelector(".work-error");
  if (!el) { el = h("p", { class: "work-error error", role: "alert" }); parent.append(el); }
  el.textContent = err.message || String(err);
}
function workField(label, input) {
  const id = `work-field-${workField.next++}`;
  input.id = id;
  return h("div", { class: "work-field" }, h("label", { for: id, text: label }), input);
}
workField.next = 1;
function workForm(parent, title, fields, submit) {
  const form = h("form", { class: "card work-form" }, h("h3", { text: title }), ...fields);
  const button = h("button", { type: "submit", text: "Save" });
  const cancel = h("button", { type: "button", class: "secondary", text: "Cancel", onClick: () => { form.remove(); startAutoRefresh(); } });
  form.append(h("div", { class: "work-toolbar" }, button, cancel));
  form.addEventListener("focusin", stopAutoRefresh);
  form.addEventListener("submit", async e => {
    e.preventDefault(); button.disabled = true;
    try { await submit(); startAutoRefresh(); await render(); }
    catch (err) { workMessage(form, err); }
    finally { button.disabled = false; }
  });
  parent.prepend(form);
  form.querySelector("input,textarea,select")?.focus();
}
function projectCategory(project, canManage) {
  let saved = project.category || "";
  if (!canManage) return h("p", { text: `Category: ${saved || "Not set"}` });

  const select = h("select", null, ...["", "Personal", "Climate Central"].map(value =>
    h("option", { value, text: value || "Not set", selected: value === saved })));
  const field = workField("Category", select);
  const status = h("small", { role: "status" });
  field.append(status);
  select.addEventListener("change", async () => {
    select.disabled = true;
    status.textContent = "Saving…";
    field.querySelector(".work-error")?.remove();
    try {
      const updated = await workPost(`/api/work/projects/${encodeURIComponent(project.id)}/category`, { category: select.value });
      saved = updated.category;
      status.textContent = "Category saved";
    } catch (err) {
      status.textContent = "";
      workMessage(field, err);
    } finally {
      select.value = saved;
      select.disabled = false;
    }
  });
  return field;
}
async function renderProjects(view) {
  const all = await api("/api/work");
  elementBase = all.element_url || elementBase;
  const board = projectWorkForViewer(all);
  clear(view);
  showWorkNotice(view);
  const [, projectFromLink, taskFromLink] = location.hash.slice(1).split("/");
  const projects = board.projects;
  if (projectFromLink) selectedProject = decodeURIComponent(projectFromLink);
  if (!projects.some(p => p.id === selectedProject)) selectedProject = projects[0]?.id || "";
  const project = projects.find(p => p.id === selectedProject);
  const linkedTask = taskFromLink && board.tasks.find(t => t.id === decodeURIComponent(taskFromLink) &&
    t.project_id === decodeURIComponent(projectFromLink));
  if (project && window.history.state?.projectId !== project.id) {
    window.history.replaceState({ ...window.history.state, projectId: project.id }, "");
  }
  const select = h("select", { "aria-label": "Project", onChange: e => { location.hash = workProjectLink(e.target.value); } },
    ...projects.map(p => h("option", { value: p.id, selected: p.id === selectedProject, text: p.title })));
  const toolbar = h("div", { class: "work-toolbar" }, h("h1", { text: "Build together" }), select);
  if (board.can_manage) toolbar.append(h("button", { text: "New project", onClick: () => {
    const title = h("input", { required: true, maxlength: 200 });
    const goal = h("textarea", { required: true, maxlength: 12000, rows: 3 });
    const brief = h("textarea", { maxlength: 12000, rows: 3 });
    const wing = h("input", { maxlength: 120, placeholder: "Leave blank to start a new collection" });
    workForm(view, "Start with an idea", [workField("Project name", title), workField("What should this achieve?", goal), workField("Design brief and constraints", brief), workField("Where to save this project’s notes (optional)", wing)],
      async () => { const p = await workPost("/api/work/projects", { title: title.value, goal: goal.value, brief: brief.value, memory_wing: wing.value }); selectedProject = p.id; location.hash = workProjectLink(p.id); });
  } }));
  view.append(toolbar);
  if (!project) {
    view.append(h("div", { class: "empty", text: "Start a project with a goal. Propose tasks, connect their dependencies, and review the team’s evidence here." }));
    return;
  }
  const tasks = board.tasks.filter(t => t.project_id === project.id);
  view.append(h("div", { class: "card project-brief" }, h("h2", { text: project.title }), h("p", { text: project.goal }),
    project.brief && h("p", { class: "dim work-prose", text: project.brief }),
    projectCategory(project, board.can_manage)));
  const phases = h("div", { class: "work-phases", "aria-label": "Project phase" });
  Object.entries(workPhases).forEach(([phase, label]) => {
    const button = h("button", { class: phase === project.phase ? "" : "secondary", text: label,
      "aria-pressed": phase === project.phase ? "true" : "false", disabled: !board.can_manage || phase === project.phase });
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await workPost(`/api/work/projects/${project.id}/phase`, { phase }); await render(); }
      catch (err) { workMessage(view, err); button.disabled = false; }
    });
    phases.append(button);
  });
  view.append(phases, h("div", { class: "tiles" },
    ...[[tasks.length, "Tasks"], [tasks.filter(t => t.state === "done").length, "Done"],
      [tasks.filter(t => t.waiting_on.length || t.state === "blocked").length, "Blocked or waiting"],
      [new Set(tasks.map(t => t.assignee).filter(Boolean)).size, "Agents involved"]].map(([value, label]) => tile(label, value))));
  const modes = h("div", { class: "work-toolbar" }, ...["board", "map", "team"].map(mode => h("button", {
    class: workMode === mode ? "" : "secondary", text: { board: "Task board", map: "Dependency map", team: "Team workload" }[mode],
    onClick: () => { workMode = mode; render(); }
  })));
  view.append(h("div", { class: "work-toolbar" }, h("button", { class: "secondary", text: "Propose task",
    onClick: () => proposeWorkTask(view, project, tasks, board.agents) }),
    h("details", null, h("summary", { text: "Agent details" }), modes)));
  view.append(h("p", { class: "dim", text: "Use Authorize work to let the assigned agent pick up a task. Use Accept to confirm a finished result." }));
  if (workMode === "map") view.append(workGraph(tasks, board));
  else if (workMode === "team") {
    const team = h("div", { class: "tiles" });
    [...new Set(tasks.map(t => t.assignee || "Unassigned"))].forEach(agent => {
      const assigned = tasks.filter(t => (t.assignee || "Unassigned") === agent);
      team.append(h("div", { class: "card" }, h("h3", { text: agent }),
        h("p", { class: "dim", text: `${assigned.filter(t => t.state === "running").length} in progress · ${assigned.filter(t => t.state === "review").length} need your review` }),
        ...assigned.map(t => workTaskCard(t, board))));
    });
    view.append(team);
  } else {
    if (board.can_manage && !tasks.length) view.append(h("p", { class: "empty", text: "No tasks in this project yet." }));
    view.append(h("div", { class: board.can_manage ? "work-board personal-board" : "work-board" }, ...workStates
      .filter(s => board.can_manage ? tasks.some(t => t.state === s) : s !== "cancelled" || tasks.some(t => t.state === s)).map(s => {
      const matching = tasks.filter(t => t.state === s);
      return h("section", { class: "work-column" }, h("h3", null, workLabels[s], " ", pill(matching.length)),
        ...matching.map(t => workTaskCard(t, board)), !matching.length && h("p", { class: "dim", text: "No tasks" }));
    })));
  }
  const activity = board.activity.filter(e => e.project_id === project.id);
  view.append(section("Work history", "", null, workActivity(activity, board)));
  if (linkedTask) openWorkTask(linkedTask, board);
  else if (taskFromLink) view.prepend(h("p", { class: "empty", role: "status", text: "This task is unavailable from your project view." }));
}
function proposeWorkTask(view, project, tasks, agents) {
  const title = h("input", { required: true, maxlength: 200 });
  const description = h("textarea", { rows: 3, maxlength: 12000 });
  const acceptance = h("textarea", { required: true, rows: 2, maxlength: 12000 });
  const assignee = h("select", null, h("option", { value: "", text: "Choose an agent", disabled: true, selected: true }),
    ...agents.map(a => h("option", { value: a, text: a })));
  assignee.required = true;
  const capability = capabilitySelect();
  const mode = modeSelect();
  const suggestions = assignmentSuggestions(assignee, capability, mode);
  const dependencies = h("select", { multiple: true, size: Math.max(2, Math.min(tasks.length, 6)) }, ...tasks.map(t => h("option", { value: t.id, text: t.title })));
  const memory = h("input", { placeholder: "drawer ids, separated by commas" });
  const room = h("input", { placeholder: "!room:server" });
  const thread = h("input", { placeholder: "$thread-event-id" });
  workForm(view, "Propose work for the team", [workField("Task", title), workField("Instructions", description), workField("Acceptance criteria", acceptance),
    workField("Main strength needed (optional)", capability), workField("Working style", mode), suggestions,
    workField("Agent", assignee), workField("Wait for these tasks (Ctrl/Cmd to select)", dependencies), workField("Relevant HM records", memory),
    workField("Existing conversation room (optional)", room), workField("Existing thread root (optional)", thread)], () => workPost(`/api/work/projects/${project.id}/tasks`, {
      title: title.value, description: description.value, acceptance: acceptance.value, assignee: assignee.value,
      capability: capability.value, work_mode: mode.value,
      dependencies: [...dependencies.selectedOptions].map(o => o.value), memory_ids: memory.value.split(",").map(s => s.trim()).filter(Boolean),
      room_id: room.value, thread_root: thread.value
    }));
}
function workTaskCard(task, board) {
  return h("a", { class: "work-task card", href: workTaskLink(task) },
    h("strong", { text: task.title }), h("span", { class: "dim", text: task.assignee || "Unassigned" }),
    task.waiting_on.length ? pill(`Waiting on ${task.waiting_on.length}`, "warn") : "",
    task.claim_expired && !board.can_manage ? pill("Claim expired", "bad") : "",
    task.state === "running" && !task.claim_expired && !board.can_manage ? h("span", { class: "dim", text: task.claim_surface || "surface not reported" }) : "",
    task.blocked_reason && h("span", { class: "bad", text: task.blocked_reason }));
}
function workGraph(tasks, board) {
  const holder = h("div", { class: "work-map" });
  if (!tasks.length) return h("div", { class: "empty", text: "Propose tasks to see their dependencies." });
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  const levels = new Map();
  const byId = new Map(tasks.map(t => [t.id, t]));
  function level(t) {
    if (!levels.has(t.id)) levels.set(t.id, t.dependencies.some(d => byId.has(d)) ? 1 + Math.max(...t.dependencies.filter(d => byId.has(d)).map(d => level(byId.get(d)))) : 0);
    return levels.get(t.id);
  }
  const counts = new Map(), positions = new Map();
  tasks.forEach(t => { const l = level(t), row = counts.get(l) || 0; counts.set(l, row + 1); positions.set(t.id, [20 + l * 250, 20 + row * 100]); });
  const width = 260 * (1 + Math.max(...levels.values()));
  const height = 100 * Math.max(...counts.values()) + 20;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.setAttribute("width", width); svg.setAttribute("height", height);
  svg.setAttribute("role", "group"); svg.setAttribute("aria-label", "Task dependencies. Arrows point from prerequisite to dependent task.");
  function shape(tag, attrs, content) { const el = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v)); if (content) el.textContent = content; return el; }
  tasks.forEach(t => t.dependencies.filter(dep => positions.has(dep)).forEach(dep => {
    const [x, y] = positions.get(dep), [tx, ty] = positions.get(t.id);
    svg.append(shape("path", { d: `M${x+210} ${y+35} C${x+235} ${y+35},${tx-25} ${ty+35},${tx} ${ty+35}`, class: "work-edge" }),
      shape("path", { d: `M${tx-7} ${ty+30} L${tx} ${ty+35} L${tx-7} ${ty+40}`, class: "work-edge" }));
  }));
  tasks.forEach(t => {
    const [x, y] = positions.get(t.id);
    const g = shape("g", { tabindex: "0", role: "button", "aria-label": `${t.title}, ${workLabels[t.state]}, ${t.assignee || "unassigned"}`, class: "work-node" });
    g.append(shape("rect", { x, y, width: 210, height: 70, rx: 10, class: `work-node-${t.state}` }),
      shape("text", { x: x+12, y: y+25 }, t.title.length > 27 ? t.title.slice(0,24)+"…" : t.title),
      shape("text", { x: x+12, y: y+49, class: "work-node-meta" }, `${t.assignee || "Unassigned"} · ${workLabels[t.state]}`), shape("title", {}, t.title));
    g.addEventListener("click", () => { location.hash = workTaskLink(t); });
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); location.hash = workTaskLink(t); } });
    svg.append(g);
  });
  holder.append(svg, h("p", { class: "dim", text: "Prerequisite → dependent. Select a task to inspect context and evidence." }));
  return holder;
}
const taskActions = {
  draft: [["ready", "Authorize work"]], blocked: [["ready", "Authorize work"]],
  review: [["accept", "Accept"], ["revise", "Request changes"]],
  ready: [["withdraw", "Withdraw approval"], ["cancel", "Cancel task"]],
  running: [["release", "Return to proposals"]], cancelled: [["reopen", "Reopen as proposed"]],
};
const actionResult = {
  ready: "Work approved. The assigned agent can now pick it up.",
  accept: "Result accepted. This task is done.",
  withdraw: "Approval withdrawn. The task is back in Proposed.",
  cancel: "Task cancelled. It is still in the project history.",
  reopen: "Task reopened as a proposal.",
  revise: "Changes requested. The task is back in Proposed.",
  release: "The task is back in Proposed.",
};
let workNotice;
function showWorkNotice(parent) {
  if (workNotice?.route === location.hash) parent.prepend(h("p", { class: "card work-notice", role: "status", text: workNotice.text }));
}
function workActionButton(task, action, label, parent) {
  const simple = action === "ready" || action === "accept";
  const button = h("button", { type: "button", class: simple ? "" : "secondary", text: label,
    disabled: action === "ready" && !task.assignee });
  async function submit(control, reason = "") {
    control.disabled = true;
    const route = location.hash;
    try {
      await workPost(`/api/work/tasks/${encodeURIComponent(task.id)}/action`, { action, reason, revision: task.revision });
      workNotice = { route, text: actionResult[action] };
      await render();
    } catch (error) { workMessage(parent, error); control.disabled = false; }
  }
  button.addEventListener("click", () => {
    if (simple) return submit(button);
    parent.querySelector(".work-reason")?.remove();
    const reason = h("textarea", { rows: 2, required: true, maxlength: 500 });
    const confirm = h("button", { type: "submit", text: label });
    const form = h("form", { class: "work-reason", onSubmit: event => {
      event.preventDefault();
      if (reason.value.trim()) submit(confirm, reason.value.trim());
    } }, workField("Reason", reason), h("div", { class: "work-toolbar" }, confirm,
      h("button", { type: "button", class: "secondary", text: "Go back", onClick: () => { form.remove(); startAutoRefresh(); button.focus(); } })));
    form.addEventListener("focusin", stopAutoRefresh);
    parent.append(form);
    reason.focus();
  });
  return button;
}
function closeWorkTask() {
  const parts = location.hash.slice(1).split("/");
  if (parts[0] === "projects" && parts.length === 3) location.hash = `#projects/${parts[1]}`;
  closeDetail();
}

function openWorkTask(task, board) {
  const detail = clear($("detail"));
  detail.classList.remove("hidden");
  showWorkNotice(detail);
  detail.append(h("button", { class: "secondary small", text: "Close", onClick: closeWorkTask }),
    h("h2", { text: task.title, tabindex: "-1" }),
    pill(workLabels[task.state], workTone(task.state)), h("p", { class: "dim", text: `Assigned to ${task.assignee || "nobody"}` }));
  if (board.can_manage && taskActions[task.state]) {
    const actions = h("div", { class: "work-toolbar task-actions" });
    actions.append(...taskActions[task.state].map(([action, label]) => workActionButton(task, action, label, actions)));
    detail.append(actions);
  }
  detail.append(h("h3", { text: "Instructions" }), h("p", { class: "work-prose", text: workPlainText(task.description) || "No extra instructions." }),
    h("h3", { text: "How we’ll know it’s done" }), h("p", { class: "work-prose", text: task.acceptance }));
  const technical = h("details", null, h("summary", { text: "Details for agents" }),
    h("a", { href: workTaskLink(task), text: "Direct link to this task" }));
  if (task.description && task.description !== workPlainText(task.description)) {
    technical.append(h("p", { class: "work-prose", text: task.description.slice(workPlainText(task.description).length).trim() }));
  }
  if (task.claim_expired) technical.append(h("p", { text: "Claim expired. The agent needs to check in before continuing." }));
  detail.querySelector("h2").focus({preventScroll: true});
  if (task.capability) technical.append(h("p", { class: "dim", text: `${capabilityLabels[task.capability]} · ${modeLabels[task.work_mode || "either"]}` }));
  if (task.dependencies.length) technical.append(h("h3", { text: "Dependencies" }), ...task.dependencies.map(id => {
    const dep = board.tasks.find(t => t.id === id);
    return h("button", { class: "link", text: `${dep?.title || id} · ${workLabels[dep?.state] || "unknown"}`, onClick: () => dep && openWorkTask(dep, board) });
  }));
  if (task.memory_ids.length) technical.append(h("h3", { text: "Shared memory" }), ...task.memory_ids.map(id => h("button", { class: "link", text: id, onClick: () => openDrawer(id) })));
  const context = h("div");
  technical.append(h("button", { class: "secondary", text: "Retrieve relevant HM lessons", onClick: async e => {
    e.target.disabled = true;
    try {
      const bundle = await api(`/api/work/tasks/${task.id}/context`);
      clear(context).append(h("p", { class: "dim work-prose", text: bundle.policy }));
      bundle.memory.forEach(m => context.append(h("div", { class: "work-note" },
        h("button", { class: "link", text: `${m.wing}/${m.room} · ${m.added_by}`, onClick: () => openDrawer(m.drawer_id) }),
        h("p", { class: "work-prose", text: m.content }), h("p", { class: "dim work-prose", text: `Source: ${m.source} · ${ago(m.created_at)}${m.content_truncated ? " · excerpt" : ""}` }))));
      if (!bundle.memory.length) context.append(h("p", { class: "dim", text: "No matching current sourced knowledge found." }));
      bundle.excluded_memory.forEach(m => context.append(h("p", { class: "warn", text: `${m.drawer_id || "Record"}: ${m.reason}` })));
    } catch (err) { workMessage(context, err); }
    finally { e.target.disabled = false; }
  } }), context);
  if (task.room_id) technical.append(h("p", null, h("a", { href: permalink(task.room_id, task.thread_root), target: "_blank", rel: "noopener", text: "Open team conversation in Hearth Chat" })));
  if (task.summary) detail.append(h("h3", { text: "Result" }), h("p", { class: "work-prose", text: workPlainText(task.summary) }));
  if (task.evidence?.length) technical.append(h("h3", { text: "Evidence" }),
    ...task.evidence.map(ref => /^https?:\/\//i.test(ref) ? h("p", null, h("a", { href: ref, target: "_blank", rel: "noopener", text: ref })) : h("p", { class: "mono work-prose", text: ref })));
  detail.append(technical);
  if (board.can_manage) {
    if (["draft", "blocked"].includes(task.state)) {
      const agent = h("select", { "aria-label": "Reassign agent" }, ...board.agents.map(a => h("option", { value: a, text: a, selected: a === task.assignee })));
      const capability = capabilitySelect(task.capability || "");
      const mode = modeSelect(task.work_mode || "either");
      capability.disabled = true; mode.disabled = true;
      detail.append(assignmentSuggestions(agent, capability, mode));
      detail.append(h("div", { class: "work-toolbar" }, agent, h("button", { class: "secondary", text: "Assign agent", onClick: async () => {
        try { await workPost(`/api/work/tasks/${task.id}/action`, { action: "assign", assignee: agent.value }); await render(); }
        catch (err) { workMessage(detail, err); }
      } })));
    }
    if (task.state === "done") detail.append(h("button", { class: "secondary", text: "Capture a durable HM lesson", onClick: () => {
      const content = h("textarea", { required: true, maxlength: 12000, rows: 4 });
      const kind = h("select", null, ...["lessons", "outcomes", "decisions"].map(k => h("option", { value: k, text: k })));
      const supersedes = h("input", { placeholder: "Current drawer id to correct (optional)" });
      const form = h("form", { class: "work-form" }, workField("Curated knowledge (search HM before saving)", content), workField("Kind", kind), workField("Supersedes", supersedes), h("button", { type: "submit", text: "Save to shared HM" }));
      form.addEventListener("focusin", stopAutoRefresh);
      form.addEventListener("submit", async e => { e.preventDefault(); const button = form.querySelector("button"); button.disabled = true;
        try { const saved = await workPost(`/api/work/tasks/${task.id}/remember`, { content: content.value, kind: kind.value, supersedes: supersedes.value });
          if (!saved.readback?.is_current) throw new Error("The saved record could not be confirmed current.");
          clear(form).append(h("p", { class: "ok", text: `Saved and read back: ${saved.drawer_id}` })); startAutoRefresh();
        } catch (err) { workMessage(form, err); button.disabled = false; }
      });
      detail.append(form); content.focus();
    } }));
  }
  detail.append(h("h3", { text: "Task discussion" }), h("p", { class: "dim", text: "Board notes are shared with humans and agents. Use the linked Hearth Chat thread for messages and notifications." }));
  const notes = board.activity.filter(e => e.task_id === task.id);
  for (const note of notes.filter(e => e.kind === "comment")) {
    detail.append(h("div", { class: "work-note" }, h("small", { class: "dim", text: `${historyActor(note.actor)} · ${when(note.at)}` }),
      h("p", { class: "work-prose", text: workPlainText(note.data.body) })));
  }
  detail.append(workActivity(notes, board));
  const body = h("textarea", { required: true, maxlength: 12000, rows: 3, "aria-label": "Task note" });
  const form = h("form", null, body, h("button", { type: "submit", text: "Add board note" }));
  form.addEventListener("focusin", stopAutoRefresh);
  form.addEventListener("submit", async e => { e.preventDefault(); const button = form.querySelector("button"); button.disabled = true;
    try { await workPost(`/api/work/tasks/${task.id}/comments`, { body: body.value }); body.value = ""; startAutoRefresh(); await render(); }
    catch (err) { workMessage(form, err); button.disabled = false; }
  });
  detail.append(form);
}
async function renderCommunication(view) {
  const data = await api("/api/work/communication");
  elementBase = data.element_url || elementBase;
  clear(view);
  view.append(h("h1", { text: "Team communication" }), h("p", { class: "dim", text: data.coverage }));
  const selected = h("select", { "aria-label": "Room" }, h("option", { value: "", text: "All observed rooms" }),
    ...Object.entries(data.rooms).map(([id, name]) => h("option", { value: id, text: name })));
  const results = h("div", { class: "work-history" });
  function show() {
    clear(results);
    const events = data.events.filter(e => !selected.value || e.room_id === selected.value).slice().reverse();
    events.forEach(e => results.append(h("div", { class: "card" }, h("p", { class: "dim", text: `${e.room} · ${e.sender} · ${when(e.ts)}` }),
      h("p", { class: "work-prose", text: e.body }), h("a", { href: permalink(e.room_id, e.thread_root || e.event_id), target: "_blank", rel: "noopener", text: "Open conversation" }),
      h("div", { class: "actions" }, actionBar({ ...e, kind: "conversation" })))));
    if (!events.length) results.append(h("div", { class: "empty", text: "No messages in this observed window." }));
  }
  selected.addEventListener("change", show);
  view.append(selected, results); show();
}
VIEWS.projects = renderProjects;
VIEWS.communication = renderCommunication;
ACTIONS_BY_KIND.conversation = [["reply", "Reply as you", "primary"]];
if (state.authed && ["projects", "communication"].includes(location.hash.slice(1))) render();
