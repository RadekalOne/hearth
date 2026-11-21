"""Librarian retrieval cases drawn from the video-ad work record."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp" / "memory"))
import librarian


class BriefTests(unittest.TestCase):
    def test_cited_decision_survives_empty_project_search(self):
        ref = "drawer_9dfb5be05f60a771e71f3c3c30c08e75"
        context = {
            "task": {"id": "video", "title": "Manage the project", "state": "ready",
                     "description": "Deliver a plan", "acceptance": "A working video"},
            "project": {"title": "Video ad"}, "memory": [],
            "notes": [{"data": {"body": "Rad dropped the task. See " + ref}}],
        }
        decision = {"drawer_id": ref, "content": "Drop the task", "is_current": True,
                    "record_class": "knowledge", "source_status": "provided"}
        queries = []
        def search(query):
            queries.append(query)
            return []
        result = librarian.build_brief(context, search, {ref: decision}.get)
        self.assertEqual([row["drawer_id"] for row in result["items"]], [ref])
        self.assertEqual(result["task"]["state"], "ready")
        self.assertIn("Video ad", queries[0])
        self.assertTrue(result["not_found"])
        self.assertEqual(result["category_question"], "Personal or Climate Central?")

    def test_no_eligible_search_hits_and_ineligible_citation_are_reported(self):
        ref = "drawer_1234567890abcdef"
        context = {"task": {"title": "Confirm membership", "category": "Climate Central"},
                   "project": {"title": "Test"}, "notes": [{"data": {"body": ref}}],
                   "memory": []}
        record = {"drawer_id": ref, "is_current": False}
        result = librarian.build_brief(context, lambda query: [record], lambda key: record)
        self.assertEqual(result["items"], [])
        self.assertTrue(any(row.get("drawer_id") == ref for row in result["not_found"]))
        self.assertTrue(any("query" in row for row in result["not_found"]))
        self.assertIsNone(result["category_question"])
