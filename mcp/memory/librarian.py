"""Librarian: read-only task briefs and deterministic filing of task notes.

No model calls. Filing classifies each learned fact against current sourced
knowledge in the task project's memory wing with fixed thresholds, and records
the thresholds in every reason so a reviewer can audit the decision.
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
DUPLICATE_DISTANCE = 0.18     # same as memory_add's near-duplicate threshold
SAME_SUBJECT_DISTANCE = 0.25  # closer than this but not a duplicate: a correction
DUPLICATE_WORD_OVERLAP = 0.6  # minimum word Jaccard for a duplicate
FILE_SEARCH_LIMIT = 5
FILE_ROOM = "facts"
NOTE_FIELDS = ("did", "learned", "left", "files_touched")
MAX_LEARNED = 20
MAX_FACT = 2000

_WORD = re.compile(r"[A-Za-z0-9_@.'-]+")
_NEGATIONS = {"not", "no", "never", "none", "without", "cannot", "isn't", "aren't", "wasn't",
              "weren't", "doesn't", "don't", "didn't", "won't", "can't", "unverified", "unknown"}


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


def _words(text):
    return {w.strip(".'-").lower() for w in _WORD.findall(text)} - {""}


def _differences(fact, existing):
    """Lexical signals the embedding cannot see: numbers, negation and wording."""
    a, b = _words(fact), _words(existing)
    numbers = {w for w in a ^ b if any(c.isdigit() for c in w)}
    negation = bool(a & _NEGATIONS) != bool(b & _NEGATIONS)
    overlap = len(a & b) / len(a | b) if a | b else 1.0
    return numbers, negation, round(overlap, 3)


def classify(fact, rows, wing):
    """Return (kind, reason, target_row) for one fact against same-wing candidates."""
    rows = [r for r in rows if eligible(r) and r.get("wing") == wing and r.get("match", "semantic") == "semantic"]
    rows.sort(key=lambda r: r["distance"])
    if not rows or rows[0]["distance"] > SAME_SUBJECT_DISTANCE:
        nearest = f"nearest d={rows[0]['distance']}" if rows else "no current sourced candidate"
        return "new", (f"{nearest} in wing {wing}; above same-subject threshold "
                       f"{SAME_SUBJECT_DISTANCE}"), None
    top = rows[0]
    numbers, negation, overlap = _differences(fact, top["content"])
    signals = f"d={top['distance']}, word overlap {overlap}"
    if top["distance"] <= DUPLICATE_DISTANCE and not numbers and not negation and overlap >= DUPLICATE_WORD_OVERLAP:
        return "duplicate", (f"matches {top['drawer_id']} ({signals}; duplicate needs d<={DUPLICATE_DISTANCE}, "
                             f"overlap>={DUPLICATE_WORD_OVERLAP}, same numbers and negation)"), top
    why = []
    if numbers:
        why.append("numbers differ: " + ", ".join(sorted(numbers)))
    if negation:
        why.append("negation differs")
    if overlap < DUPLICATE_WORD_OVERLAP:
        why.append(f"wording overlap below {DUPLICATE_WORD_OVERLAP}")
    if top["distance"] > DUPLICATE_DISTANCE:
        why.append(f"d above duplicate threshold {DUPLICATE_DISTANCE}")
    return "correction", (f"same subject as {top['drawer_id']} ({signals}; d<={SAME_SUBJECT_DISTANCE}) "
                          f"but content differs ({'; '.join(why)})"), top


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
        plan.append(entry)
    for entry in plan:
        if entry["classification"] != "duplicate":
            saved = save(entry["fact"], entry["supersedes"],
                         fact_key(task["id"], entry["fact"], entry["supersedes"]))
            entry["drawer_id"] = saved["drawer_id"]
    return plan
