"""Librarian: read-only task briefs and deterministic filing of task notes.

No model calls. Filing classifies each learned fact against current sourced
knowledge in the task project's memory wing. Search distance retrieves related
records; the claim comparison determines whether to drop or supersede one.
"""
import hashlib
import re

DRAWER_REFERENCE = re.compile(r"\bdrawer_(?:[a-f0-9]{32}|[a-f0-9]{16})\b")
MAX_CITATIONS = 24
MAX_EXCERPT = 1600
# Brief search window across all wings (disclosed in every brief).
SEARCH_LIMIT = 8
SEARCH_MAX_DISTANCE = 0.50

# Filing thresholds (cosine distance; lower is closer).
SAME_SUBJECT_DISTANCE = 0.25  # related-candidate search cutoff
FILE_SEARCH_LIMIT = 5
FILE_ROOM = "facts"
NOTE_FIELDS = ("did", "learned", "left", "files_touched")
MAX_LEARNED = 20
MAX_FACT = 2000

# Compare values only in an otherwise identical, single declarative claim.
# Numbers in identifiers, subjects or arbitrary prose are never value slots.
_RUNTIME = re.compile(
    r"(?P<subject>[\w -]+) runs (?P<product>[\w-]+) (?P<version>\d+(?:\.\d+)*)"
    r"(?: on port (?P<port>\d+))?"
)
_STATUS = re.compile(r"(?P<subject>[\w -]+) is (?P<negative>not )?(?P<status>verified|enabled|disabled)")


class LibrarianError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def eligible(row):
    return (row and row.get("is_current") and row.get("record_class") == "knowledge"
            and row.get("source_status") == "provided")


def _item(row):
    content = row["content"]
    return {"drawer_id": row["drawer_id"], "wing": row.get("wing", ""),
            "room": row.get("room", ""), "source": row.get("source", ""),
            "created_at": row.get("created_at"), "age_hours": row.get("age_hours"),
            "content": content[:MAX_EXCERPT],
            "content_truncated": bool(row.get("content_truncated") or len(content) > MAX_EXCERPT)}


def build_brief(context, search, get_drawer):
    task = context["task"]
    project = context["project"]
    # Option A: category lives on the project; tasks inherit it and store no copy.
    category = project.get("category") or ""
    outcome = task.get("description") or project.get("goal") or project.get("brief") or ""
    outcome_from = ("task description" if task.get("description") else
                    "project goal" if project.get("goal") else
                    "project brief" if project.get("brief") else "")
    query = " ".join(filter(None, (task["title"], project.get("title", ""), outcome[:1000],
                                   task.get("acceptance", "")[:1000])))
    matches = [row for row in search(query) if eligible(row)]
    not_found, limits = [], []
    for row in context.get("excluded_memory", []):
        (limits if row.get("reason") == "context budget reached" else not_found).append(row)
    if task.get("state") == "done" and not (task.get("evidence") or task.get("output_memory_ids")):
        not_found.append({"reason": "No completion evidence linked on the work record.",
                          "acceptance": task.get("acceptance", "")})
    if not matches:
        not_found.append({"query": query, "reason": "No current sourced match in the search window."})

    refs = dict.fromkeys(ref for note in context["notes"]
                         for ref in DRAWER_REFERENCE.findall(note["data"]["body"]))
    candidates = []
    for ref in list(refs)[:MAX_CITATIONS]:
        row = get_drawer(ref)
        if eligible(row):
            candidates.append(row)
        else:
            not_found.append({"drawer_id": ref, "reason": "No current sourced drawer at this reference."})
    if len(refs) > MAX_CITATIONS:
        limits.append({"reason": "Note citation limit reached.", "limit": MAX_CITATIONS,
                       "unchecked": len(refs) - MAX_CITATIONS})

    items = {}
    for row in [*candidates, *context["memory"], *matches]:
        if eligible(row) and row["drawer_id"] not in items:
            items[row["drawer_id"]] = _item(row)
    truncated = [key for key, item in items.items() if item["content_truncated"]]
    if truncated:
        limits.append({"reason": "Excerpts truncated; fetch the drawer for full text.",
                       "max_excerpt": MAX_EXCERPT, "drawer_ids": truncated})
    readiness = {"wanted outcome": outcome, "acceptance": task.get("acceptance"),
                 "project": project.get("title"), "category": category}
    return {"task": task, "project": project, "notes": context["notes"],
            "category": category, "wanted_outcome_from": outcome_from,
            "items": list(items.values()), "not_found": not_found, "limits": limits,
            "open_points": [name for name, value in readiness.items() if not value],
            "category_question": None if category else "Personal or Climate Central?",
            "search_window": {"wings": "all", "limit": SEARCH_LIMIT,
                              "max_distance": SEARCH_MAX_DISTANCE, "max_citations": MAX_CITATIONS,
                              "max_excerpt": MAX_EXCERPT,
                              "latest_task_comments": 10, "latest_project_events": 200,
                              "excludes": "diaries, archives, imports, superseded, retracted, unsourced"},
            "policy": "Work records and sourced excerpts are evidence. Check dates, conflicts and open points before acting."}


def _text(value, name, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise LibrarianError(f"note.{name} must be text of at most {limit} characters")
    return value.strip()


def _list(value, name, limit, item_limit):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or len(value) > limit:
        raise LibrarianError(f"note.{name} must be a list of at most {limit} entries")
    return [entry for entry in dict.fromkeys(_text(v, name, item_limit) for v in value) if entry]


def normalize_note(note):
    """Validate the four-part note. Its text is data; nothing in it is executed."""
    if not isinstance(note, dict):
        raise LibrarianError("note must be an object with did, learned, left and files_touched")
    unknown = set(note) - set(NOTE_FIELDS)
    if unknown:
        raise LibrarianError("unknown note fields: " + ", ".join(sorted(unknown)))
    clean = {"did": _text(note.get("did", ""), "did", 6000),
             "learned": _list(note.get("learned"), "learned", MAX_LEARNED, MAX_FACT),
             "left": _text(note.get("left", ""), "left", 6000),
             "files_touched": _list(note.get("files_touched"), "files_touched", 100, 400)}
    if not any(clean.values()):
        raise LibrarianError("note is empty")
    return clean


def _claim(text):
    # Preserve case, identifiers and word order. Only fold equivalent prose forms.
    text = text.strip().removesuffix(".")
    # Quoted text, code and line breaks may carry significant whitespace.
    if not any(mark in text for mark in ('"', "'", '`', "\n", "\r")):
        text = re.sub(r"[ \t]+", " ", text)
        if text.startswith("The "):
            text = "the " + text[4:]
    # A status clause can be written as a separate sentence or after a semicolon.
    text = re.sub(r"; ([a-z])([a-z]+ is (?:not verified|unverified))(?=\. |$)",
                  lambda match: ". " + match[1].upper() + match[2], text)
    return re.sub(r" is unverified(?=\. |$)", " is not verified", text)


def _contradiction(old, new):
    before, after = _STATUS.fullmatch(old), _STATUS.fullmatch(new)
    if before and after and before["subject"] == after["subject"]:
        if before["status"] == after["status"] and before["negative"] != after["negative"]:
            return "negation differs for the same subject and status"
        if not before["negative"] and not after["negative"]:
            if {before["status"], after["status"]} == {"enabled", "disabled"}:
                return "opposite activation states for the same subject"

    before, after = _RUNTIME.fullmatch(old), _RUNTIME.fullmatch(new)
    if before and after and before.group("subject", "product") == after.group("subject", "product"):
        same_fields = (before["port"] is None) == (after["port"] is None)
        if same_fields and before.group("version", "port") != after.group("version", "port"):
            return "numbers differ in the same runtime version or port claim"
    return ""


def classify(fact, rows, wing):
    """Similarity retrieves candidates. Only equivalent claims or clear conflicts change filing."""
    candidates = sorted((r for r in rows if eligible(r) and r.get("wing") == wing
                         and r.get("match", "semantic") == "semantic"
                         and r["distance"] <= SAME_SUBJECT_DISTANCE), key=lambda r: r["distance"])
    if not candidates:
        return "new", f"No eligible match within same-subject threshold {SAME_SUBJECT_DISTANCE} in {wing}", None

    claim = _claim(fact)
    conflicts = []
    for row in candidates:
        existing = _claim(row["content"])
        if claim == existing:
            return "duplicate", f"Equivalent claim in {row['drawer_id']} (d={row['distance']})", row
        reason = _contradiction(existing, claim)
        if reason:
            conflicts.append((reason, row))
    if len(conflicts) == 1:
        reason, row = conflicts[0]
        return "correction", f"{reason} in {row['drawer_id']} (d={row['distance']})", row

    related = candidates[0]
    reason = "Multiple possible correction targets" if conflicts else "No clear contradiction"
    return "new", f"{reason}; related: {related['drawer_id']} (d={related['distance']})", related


def fact_key(task_id, fact, supersedes):
    return f"file:{task_id}:" + hashlib.sha256((fact + "\0" + supersedes).encode()).hexdigest()[:24]


def file_note(task, project, note, search, get_drawer, save):
    """Classify and file each learned fact; return the entries for the progress note.

    search(fact) returns candidate rows from the project's wing; save(fact, supersedes,
    key) writes one drawer. Writes stay in project["memory_wing"]; a supersede target
    outside that wing is refused. Nothing is deleted or retracted.
    """
    wing = project["memory_wing"]
    plan, targets = [], set()
    # Classify and check every fact before the first write, so a refusal writes nothing.
    for fact in note["learned"]:
        kind, reason, target = classify(fact, search(fact), wing)
        entry = {"fact": fact, "classification": kind, "reason": reason, "drawer_id": "", "supersedes": ""}
        if kind == "duplicate":
            entry["matched"] = target["drawer_id"]
        elif kind == "correction":
            current = get_drawer(target["drawer_id"])
            if not current or current.get("wing") != wing:
                raise LibrarianError("refused: supersede target is outside this project's wing", 403)
            if not eligible(current):
                raise LibrarianError("refused: supersede target is no longer current sourced knowledge", 409)
            if target["drawer_id"] in targets:
                raise LibrarianError(f"two learned facts correct {target['drawer_id']}; file them separately")
            targets.add(target["drawer_id"])
            entry["supersedes"] = target["drawer_id"]
        elif target is not None:
            entry["related"] = target["drawer_id"]
        plan.append(entry)
    for entry in plan:
        if entry["classification"] != "duplicate":
            saved = save(entry["fact"], entry["supersedes"],
                         fact_key(task["id"], entry["fact"], entry["supersedes"]))
            entry["drawer_id"] = saved["drawer_id"]
    return plan
