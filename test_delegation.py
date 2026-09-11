import importlib
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch


class DelegationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "center.db")
        os.environ["CENTER_DB_PATH"] = self.db_path

        import config
        import intake
        import delegation

        self.config = importlib.reload(config)
        self.intake = importlib.reload(intake)
        self.delegation = importlib.reload(delegation)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_handle_message_legacy_call_still_works(self):
        outcome = self.delegation.handle_message(
            "Should I bump my Roth contributions before year-end?"
        )

        self.assertEqual(outcome["owner"], "richard")
        self.assertEqual(outcome["status"], "in_progress")
        self.assertIn("task_id", outcome)
        self.assertEqual(len(self.intake.list_tasks()), 1)

        task = self.intake.list_tasks()[0]
        self.assertEqual(task["owner"], "richard")
        self.assertEqual(task["status"], "in_progress")

    def test_handle_message_accepts_context_and_metadata(self):
        captured = {}

        def fake_specialist(task):
            captured["task"] = task
            return {"result": "ok"}

        self.delegation.SPECIALISTS = {"juan_whey": fake_specialist}

        outcome = self.delegation.handle_message(
            "Book me a trip to the Dominican Republic",
            context={"travel_preferences": "window seat"},
            metadata={"conversation_id": "abc-123"},
        )

        self.assertEqual(outcome["result"], "ok")
        self.assertEqual(outcome["status"], "in_progress")

        task = self.intake.list_tasks()[0]
        self.assertEqual(captured["task"]["context"]["travel_preferences"], "window seat")
        self.assertEqual(captured["task"]["metadata"]["conversation_id"], "abc-123")

        stored_metadata = json.loads(task["metadata"])
        self.assertEqual(stored_metadata["context"]["travel_preferences"], "window seat")
        self.assertEqual(stored_metadata["metadata"]["conversation_id"], "abc-123")

    def test_context_reaches_specialist_via_task_payload(self):
        captured = {}

        def fake_specialist(task):
            captured["task"] = task
            return {"result": "done"}

        self.delegation.SPECIALISTS = {"richard": fake_specialist}

        self.delegation.handle_message(
            "Need advice on taxes",
            context={"user_profile": {"risk_tolerance": "moderate"}},
            metadata={"source": "sheila"},
        )

        self.assertEqual(captured["task"]["context"]["user_profile"]["risk_tolerance"], "moderate")
        self.assertEqual(captured["task"]["metadata"]["source"], "sheila")

    def test_center_does_not_depend_on_sam2(self):
        with open(self.delegation.__file__, "r", encoding="utf-8") as fh:
            source = fh.read().lower()
        self.assertNotIn("sam2", source)
        self.assertNotIn("from sam2", source)
        self.assertNotIn("import sam2", source)

    def test_dispatch_task_rejects_malformed_task(self):
        outcome = self.delegation.dispatch_task({})

        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["error"]["code"], "invalid_task")

    def test_dispatch_task_rejects_unknown_specialist(self):
        outcome = self.delegation.dispatch_task({"owner": "unknown"})

        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["error"]["code"], "unknown_specialist")

    def test_dispatch_task_returns_specialist_success(self):
        specialist = Mock(return_value={"answer": "done"})
        self.delegation.SPECIALISTS = {"richard": specialist}

        outcome = self.delegation.dispatch_task({"owner": "richard", "title": "Tax"})

        specialist.assert_called_once_with({"owner": "richard", "title": "Tax"})
        self.assertEqual(outcome, {
            "ok": True,
            "owner": "richard",
            "result": {"answer": "done"},
            "error": None,
        })

    def test_dispatch_task_contains_specialist_failure(self):
        specialist = Mock(side_effect=RuntimeError("secret details"))
        self.delegation.SPECIALISTS = {"richard": specialist}

        outcome = self.delegation.dispatch_task({"owner": "richard"})

        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["error"]["code"], "specialist_error")
        self.assertNotIn("secret details", outcome["error"]["message"])

    def test_dee_gmail_routing_returns_adapter_envelope(self):
        envelope = {
            "ok": True,
            "operation": "search_gmail",
            "account": "personal",
            "data": [],
            "error": None,
        }
        specialist = Mock(return_value=envelope)
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}

        with patch.object(
            self.delegation,
            "classify",
            return_value={
                "category": "research",
                "title": "Search Gmail",
                "brief": "Find matching mail",
                "owner": "dee_gmail",
                "priority": "normal",
            },
        ):
            outcome = self.delegation.handle_message("Search Gmail")

        self.assertEqual(outcome["result"], envelope)


if __name__ == "__main__":
    unittest.main()
