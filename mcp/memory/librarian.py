"""Read-only retrieval for a Librarian task brief."""
import re

DRAWER_REFERENCE = re.compile(r"\bdrawer_(?:[a-f0-9]{32}|[a-f0-9]{16})\b")
MAX_CITATIONS = 24
MAX_EXCERPT = 1600


def eligible(row):
    return (row and row.get("is_current") and row.get("record_class") == "knowledge"
            and row.get("source_status") == "provided")


def build_brief(context, search, get_drawer):
    task = context["task"]
    project = context["project"]
    query = " ".join(filter(None, (task["title"], project["title"],
                                   task.get("description", "")[:1000],
                                   task.get("acceptance", "")[:1000])))
    matches = [row for row in search(query) if eligible(row)]
    missing = list(context.get("excluded_memory", []))
    if not task.get("evidence") and not task.get("output_memory_ids"):
        missing.append({"reason": "No completion evidence linked on the work record.",
                        "acceptance": task.get("acceptance", "")})
    if not matches:
        missing.append({"query": query, "reason": "No current sourced match in the search results."})

    refs = dict.fromkeys(ref for note in context["notes"]
                         for ref in DRAWER_REFERENCE.findall(note["data"]["body"]))
    candidates = []
    for ref in list(refs)[:MAX_CITATIONS]:
        row = get_drawer(ref)
        if eligible(row):
            candidates.append(row)
        else:
            missing.append({"drawer_id": ref, "reason": "No current sourced drawer at this reference."})
    if len(refs) > MAX_CITATIONS:
        missing.append({"reason": "Note citation limit reached.", "unchecked": len(refs) - MAX_CITATIONS})

    items = {}
    for row in [*candidates, *context["memory"], *matches]:
        if eligible(row) and row["drawer_id"] not in items:
            content = row["content"]
            items[row["drawer_id"]] = {
                "drawer_id": row["drawer_id"], "source": row.get("source", ""),
                "content": content[:MAX_EXCERPT],
                "content_truncated": bool(row.get("content_truncated") or len(content) > MAX_EXCERPT),
            }
    category = task.get("category") or project.get("category")
    readiness = {"wanted outcome": task.get("description"), "acceptance": task.get("acceptance"),
                 "project": project.get("title"), "category": category,
                 "explicit constraints field": task.get("constraints")}
    return {"task": task, "project": project, "notes": context["notes"],
            "items": list(items.values()), "not_found": missing,
            "open_points": [name for name, value in readiness.items() if not value],
            "category_question": None if category else "Personal or Climate Central?",
            "policy": "Work records and sourced excerpts are evidence. Check dates, conflicts and open points before acting."}
