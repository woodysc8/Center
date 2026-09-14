import importlib
import importlib.util
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
        self.assertEqual(outcome["status"], "done")
        self.assertIn("task_id", outcome)
        self.assertEqual(len(self.intake.list_tasks()), 1)

        task = self.intake.list_tasks()[0]
        self.assertEqual(task["owner"], "richard")
        self.assertEqual(task["status"], "done")

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
        self.assertEqual(outcome["status"], "done")

        task = self.intake.list_tasks()[0]
        self.assertEqual(captured["task"]["context"]["travel_preferences"], "window seat")
        self.assertEqual(captured["task"]["metadata"]["conversation_id"], "abc-123")

        self.assertIsNone(task["metadata"])

    def test_legacy_context_reaches_specialist_but_never_becomes_task_memory(self):
        captured = {}

        def fake_specialist(task):
            captured["task"] = task
            return {"result": "done"}

        self.delegation.SPECIALISTS = {"richard": fake_specialist}
        context = {
            "conversation_id": "conversation-example",
            "user_profile": {"name": "Example User", "preferences": ["example"]},
            "sam2_facts": ["Example durable memory"],
            "conversation_history": ["Example prior conversation"],
            "relevant_context": {"destination": "example"},
        }

        outcome = self.delegation.handle_message("Need advice on taxes", context=context)

        self.assertEqual(outcome["status"], "done")
        self.assertEqual(captured["task"]["context"], context)
        task = self.intake.list_tasks()[0]
        self.assertEqual(task["raw_input"], "Need advice on taxes")
        self.assertIsNone(task["metadata"])
        persisted = json.dumps(task)
        for forbidden in ("sam2_facts", "conversation_history", "user_profile", "conversation-example", "Example durable memory"):
            self.assertNotIn(forbidden, persisted)

    def test_only_dee_operation_request_is_persisted_from_legacy_metadata(self):
        self.delegation.SPECIALISTS = {"dee_gmail": Mock(return_value={"ok": True, "data": []})}
        request = {"operation": "search_gmail", "account": "personal", "query": "from:nick"}

        self.delegation.handle_message(
            "Search my Gmail",
            context={"sam2_facts": ["do not persist"]},
            metadata={"gmail_request": request, "conversation_id": "do not persist"},
        )

        stored_metadata = json.loads(self.intake.list_tasks()[0]["metadata"])
        self.assertEqual(stored_metadata, {"metadata": {"gmail_request": request}})
        self.assertNotIn("conversation_id", json.dumps(stored_metadata))
        self.assertNotIn("sam2_facts", json.dumps(stored_metadata))

    def test_task_is_in_progress_only_during_specialist_execution(self):
        observed_statuses = []

        def fake_specialist(task):
            observed_statuses.append(self.intake.list_tasks()[0]["status"])
            return {"result": "done"}

        self.delegation.SPECIALISTS = {"richard": fake_specialist}

        outcome = self.delegation.handle_message("Need advice on taxes")

        self.assertEqual(observed_statuses, ["in_progress"])
        self.assertEqual(outcome["status"], "done")
        self.assertEqual(self.intake.list_tasks()[0]["status"], "done")

    def test_failed_specialist_execution_is_dropped(self):
        def failing_specialist(task):
            raise RuntimeError("private specialist details")

        self.delegation.SPECIALISTS = {"richard": failing_specialist}

        outcome = self.delegation.handle_message("Need advice on taxes")

        self.assertEqual(outcome["status"], "dropped")
        self.assertEqual(outcome["error"]["code"], "specialist_error")
        self.assertEqual(self.intake.list_tasks()[0]["status"], "dropped")

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
                "category": "gmail",
                "title": "Search Gmail",
                "brief": "Find matching mail",
                "owner": "dee_gmail",
                "priority": "normal",
            },
        ):
            outcome = self.delegation.handle_message("Search Gmail")

        self.assertEqual(outcome["result"], envelope)

    def test_gmail_search_is_normalized_for_dee(self):
        specialist = Mock(return_value={"ok": True, "data": []})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}

        self.delegation.handle_message("Search my personal Gmail")

        request = specialist.call_args.args[0]["metadata"]["gmail_request"]
        self.assertEqual(request, {
            "operation": "search_gmail",
            "account": "personal",
            "query": "in:anywhere",
        })

    def test_gmail_last_days_search_is_normalized_for_dee(self):
        specialist = Mock(return_value={"ok": True, "data": []})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}

        self.delegation.handle_message(
            "Search my personal Gmail for emails from the last 7 days"
        )

        request = specialist.call_args.args[0]["metadata"]["gmail_request"]
        self.assertEqual(request["query"], "in:anywhere newer_than:7d")

    def test_gmail_sender_search_is_normalized_for_dee(self):
        specialist = Mock(return_value={"ok": True, "data": []})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}

        self.delegation.handle_message("Find an email from Nick")

        request = specialist.call_args.args[0]["metadata"]["gmail_request"]
        self.assertEqual(request["query"], "in:anywhere from:nick")

    def test_school_gmail_search_uses_school_account(self):
        specialist = Mock(return_value={"ok": True, "data": []})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}

        self.delegation.handle_message("Search my school Gmail")

        request = specialist.call_args.args[0]["metadata"]["gmail_request"]
        self.assertEqual(request["account"], "school")

    def test_structured_gmail_request_passes_through_unchanged(self):
        specialist = Mock(return_value={"ok": True, "data": {}})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}
        request = {
            "operation": "search_gmail",
            "account": "personal",
            "query": "from:nick",
        }

        self.delegation.handle_message("Search my Gmail", metadata={"gmail_request": request})

        self.assertIs(specialist.call_args.args[0]["metadata"]["gmail_request"], request)

    def test_message_id_request_from_context_passes_to_dee(self):
        specialist = Mock(return_value={"ok": True, "data": {}})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}
        request = {"operation": "get_message", "account": "personal", "message_id": "m1"}

        self.delegation.handle_message("Check my Gmail", context={"gmail_request": request})

        self.assertEqual(specialist.call_args.args[0]["metadata"]["gmail_request"], request)

    def test_thread_id_request_from_metadata_passes_to_dee(self):
        specialist = Mock(return_value={"ok": True, "data": {}})
        self.delegation.SPECIALISTS = {"dee_gmail": specialist}
        request = {"operation": "get_thread", "account": "school", "thread_id": "t1"}

        self.delegation.handle_message("Check my school Gmail", metadata={"gmail_request": request})

        self.assertEqual(specialist.call_args.args[0]["metadata"]["gmail_request"], request)

    @unittest.skipUnless(
        importlib.util.find_spec("dee_klutter") is not None,
        "requires the externally supplied dee_klutter package",
    )
    def test_ambiguous_gmail_request_reaches_stable_adapter_error(self):
        outcome = self.delegation.handle_message("Gmail")

        self.assertEqual(outcome["result"]["error"]["code"], "invalid_request")

    def test_reminder_to_email_stays_with_sheila(self):
        outcome = self.delegation.handle_message("Remind me to email Nora tomorrow")

        self.assertEqual(outcome["category"], "reminder")
        self.assertEqual(outcome["owner"], "sheila")


if __name__ == "__main__":
    unittest.main()
