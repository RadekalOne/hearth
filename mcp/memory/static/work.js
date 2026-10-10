/* Durable work views. The existing dashboard owns authentication and Matrix actions. */
"use strict";
let selectedProject = "";
let workMode = "board";
const workStates = ["draft", "ready", "running", "blocked", "review", "done"];
const workLabels = { draft: "Proposed", ready: "Authorized", running: "Claimed", blocked: "Blocked", review: "Needs review", done: "Verified done" };
const workPhases = ["idea", "design", "build", "validate", "shipped"];
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
        h("p", { class: "dim", text: `${p.workload.running} claimed · ${p.workload.ready} queued · ${p.workload.review} in review · ${p.workload.blocked} blocked` }));
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
async function renderProjects(view) {
  const board = await api("/api/work");
  elementBase = board.element_url || elementBase;
  clear(view);
  const projects = board.projects;
  if (!projects.some(p => p.id === selectedProject)) selectedProject = projects[0]?.id || "";
  const project = projects.find(p => p.id === selectedProject);
  const select = h("select", { "aria-label": "Project", onChange: e => { selectedProject = e.target.value; render(); } },
    ...projects.map(p => h("option", { value: p.id, selected: p.id === selectedProject, text: p.title })));
  const toolbar = h("div", { class: "work-toolbar" }, h("h1", { text: "Build together" }), select);
  if (board.can_manage) toolbar.append(h("button", { text: "New project", onClick: () => {
    const title = h("input", { required: true, maxlength: 200 });
    const goal = h("textarea", { required: true, maxlength: 12000, rows: 3 });
    const brief = h("textarea", { maxlength: 12000, rows: 3 });
    const wing = h("input", { maxlength: 120, placeholder: "Existing HM project, e.g. hearth; blank creates a new project namespace" });
    workForm(view, "Start with an idea", [workField("Project name", title), workField("What should this achieve?", goal), workField("Design brief and constraints", brief), workField("Shared memory project", wing)],
      async () => { const p = await workPost("/api/work/projects", { title: title.value, goal: goal.value, brief: brief.value, memory_wing: wing.value }); selectedProject = p.id; });
  } }));
  view.append(toolbar);
  if (!project) {
    view.append(h("div", { class: "empty", text: "Start a project with a goal. Propose tasks, connect their dependencies, and review the team’s evidence here." }));
    return;
  }
  const tasks = board.tasks.filter(t => t.project_id === project.id);
  view.append(h("div", { class: "card project-brief" }, h("h2", { text: project.title }), h("p", { text: project.goal }),
    project.brief && h("p", { class: "dim work-prose", text: project.brief })));
  const phases = h("div", { class: "work-phases", "aria-label": "Project phase" });
  workPhases.forEach(phase => {
    const button = h("button", { class: phase === project.phase ? "" : "secondary", text: phase,
      "aria-pressed": phase === project.phase ? "true" : "false", disabled: !board.can_manage || phase === project.phase });
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await workPost(`/api/work/projects/${project.id}/phase`, { phase }); await render(); }
      catch (err) { workMessage(view, err); button.disabled = false; }
    });
    phases.append(button);
  });
  view.append(phases, h("div", { class: "tiles" },
    ...[[tasks.length, "Tasks"], [tasks.filter(t => t.state === "done").length, "Reviewed complete"],
      [tasks.filter(t => t.waiting_on.length || t.state === "blocked").length, "Blocked or waiting"],
      [new Set(tasks.map(t => t.assignee).filter(Boolean)).size, "Agents involved"]].map(([value, label]) => tile(label, value))));
  const modes = h("div", { class: "work-toolbar" }, ...["board", "map", "team"].map(mode => h("button", {
    class: workMode === mode ? "" : "secondary", text: { board: "Task board", map: "Dependency map", team: "Team workload" }[mode],
    onClick: () => { workMode = mode; render(); }
  })), h("button", { class: "secondary", text: "Propose task", onClick: () => proposeWorkTask(view, project, tasks, board.agents) }));
  view.append(modes, h("p", { class: "dim", text: "Authorization queues work. An agent must claim it through its tools; claims expire after 15 minutes without renewal. Completion requires evidence and human review." }));
  if (workMode === "map") view.append(workGraph(tasks, board));
  else if (workMode === "team") {
    const team = h("div", { class: "tiles" });
    [...new Set(tasks.map(t => t.assignee || "Unassigned"))].forEach(agent => {
      const assigned = tasks.filter(t => (t.assignee || "Unassigned") === agent);
      team.append(h("div", { class: "card" }, h("h3", { text: agent }),
        h("p", { class: "dim", text: `${assigned.filter(t => t.state === "running").length} claimed · ${assigned.filter(t => t.state === "review").length} awaiting review` }),
        ...assigned.map(t => workTaskCard(t, board))));
    });
    view.append(team);
  } else {
    view.append(h("div", { class: "work-board" }, ...workStates.map(s => {
      const matching = tasks.filter(t => t.state === s);
      return h("section", { class: "work-column" }, h("h3", null, workLabels[s], " ", pill(matching.length)),
        ...matching.map(t => workTaskCard(t, board)), !matching.length && h("p", { class: "dim", text: "No tasks" }));
    })));
  }
  const activity = board.activity.filter(e => e.project_id === project.id).slice(0, 15);
  const history = h("div", { class: "work-history" }, ...activity.map(e => h("div", { class: "card" },
    h("span", { class: "dim", text: `${when(e.at)} · ${e.actor} · ${e.kind.replaceAll("_", " ")}` }),
    h("p", { class: "work-prose", text: e.data.body || e.data.summary || e.data.reason || e.data.title || e.data.phase || "" }))));
  view.append(section("Work history", "Attributed changes and handoffs", activity.length, history));
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
  return h("button", { class: "work-task card", onClick: () => openWorkTask(task, board) },
    h("strong", { text: task.title }), h("span", { class: "dim", text: task.assignee || "Unassigned" }),
    task.waiting_on.length ? pill(`Waiting on ${task.waiting_on.length}`, "warn") : "",
    task.claim_expired ? pill("Claim expired", "bad") : "",
    task.state === "running" && !task.claim_expired ? h("span", { class: "dim", text: task.claim_surface || "surface not reported" }) : "",
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
    if (!levels.has(t.id)) levels.set(t.id, t.dependencies.length ? 1 + Math.max(...t.dependencies.map(d => level(byId.get(d)))) : 0);
    return levels.get(t.id);
  }
  const counts = new Map(), positions = new Map();
  tasks.forEach(t => { const l = level(t), row = counts.get(l) || 0; counts.set(l, row + 1); positions.set(t.id, [20 + l * 250, 20 + row * 100]); });
  const width = 260 * (1 + Math.max(...levels.values()));
  const height = 100 * Math.max(...counts.values()) + 20;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.setAttribute("width", width); svg.setAttribute("height", height);
  svg.setAttribute("role", "group"); svg.setAttribute("aria-label", "Task dependencies. Arrows point from prerequisite to dependent task.");
  function shape(tag, attrs, content) { const el = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v)); if (content) el.textContent = content; return el; }
  tasks.forEach(t => t.dependencies.forEach(dep => {
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
    g.addEventListener("click", () => openWorkTask(t, board));
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openWorkTask(t, board); } });
    svg.append(g);
  });
  holder.append(svg, h("p", { class: "dim", text: "Prerequisite → dependent. Select a task to inspect context and evidence." }));
  return holder;
}
function openWorkTask(task, board) {
  const detail = clear($("detail"));
  detail.classList.remove("hidden");
  detail.append(h("button", { class: "secondary small", text: "Close", onClick: closeDetail }), h("h2", { text: task.title }),
    pill(workLabels[task.state], workTone(task.state)), h("p", { class: "dim", text: `Assigned to ${task.assignee || "nobody"}` }),
    h("h3", { text: "Instructions" }), h("p", { class: "work-prose", text: task.description || "No extra instructions." }),
    h("h3", { text: "Acceptance criteria" }), h("p", { class: "work-prose", text: task.acceptance }));
  if (task.capability) detail.append(h("p", { class: "dim", text: `${capabilityLabels[task.capability]} · ${modeLabels[task.work_mode || "either"]}` }));
  if (task.dependencies.length) detail.append(h("h3", { text: "Dependencies" }), ...task.dependencies.map(id => {
    const dep = board.tasks.find(t => t.id === id);
    return h("button", { class: "link", text: `${dep?.title || id} · ${workLabels[dep?.state] || "unknown"}`, onClick: () => dep && openWorkTask(dep, board) });
  }));
  if (task.memory_ids.length) detail.append(h("h3", { text: "Shared memory" }), ...task.memory_ids.map(id => h("button", { class: "link", text: id, onClick: () => openDrawer(id) })));
  const context = h("div");
  detail.append(h("button", { class: "secondary", text: "Retrieve relevant HM lessons", onClick: async e => {
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
  if (task.room_id) detail.append(h("p", null, h("a", { href: permalink(task.room_id, task.thread_root), target: "_blank", rel: "noopener", text: "Open team conversation in Hearth Chat" })));
  if (task.summary) detail.append(h("h3", { text: "Handoff and evidence" }), h("p", { class: "work-prose", text: task.summary }),
    ...task.evidence.map(ref => /^https?:\/\//i.test(ref) ? h("p", null, h("a", { href: ref, target: "_blank", rel: "noopener", text: ref })) : h("p", { class: "mono work-prose", text: ref })));
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
    const actions = task.state === "draft" || task.state === "blocked" ? [["ready", "Authorize work"]]
      : task.state === "review" ? [["accept", "Accept evidence and complete"], ["revise", "Request revision"]]
      : task.state === "running" ? [["release", "Release claim and return to proposal"]] : [];
    actions.forEach(([action, label]) => detail.append(h("button", { text: label, onClick: async e => {
      let reason = "";
      if (action === "revise" || action === "release") { reason = window.prompt("Reason for this change:") || ""; if (!reason.trim()) return; }
      e.target.disabled = true;
      try { await workPost(`/api/work/tasks/${task.id}/action`, { action, reason }); await render(); }
      catch (err) { workMessage(detail, err); e.target.disabled = false; }
    } })));
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
  const notes = board.activity.filter(e => e.task_id === task.id).slice().reverse();
  notes.forEach(e => detail.append(h("div", { class: "work-note" }, h("small", { class: "dim", text: `${e.actor} · ${when(e.at)} · ${e.kind}` }),
    h("p", { class: "work-prose", text: e.data.body || e.data.summary || e.data.reason || "" }))));
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
