import importlib
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


class CenterExecutionTests(unittest.TestCase):
    def setUp(self):
        import execution
        self.execution = importlib.reload(execution)
        self.request = {
            "request_id": "req-calendar-1",
            "capability": "calendar_read",
            "authority_scope": "read",
        }

    def test_calendar_read_dispatches_to_injected_google_boundary(self):
        reader = Mock(return_value=[{"id": "g-1", "title": "Dentist"}])
        result = self.execution.execute("Check my calendar for tomorrow.", {}, {**self.request, "calendar_reader": reader})
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["authoritative_source"], "google_calendar")
        self.assertEqual(result["result"]["count"], 1)
        self.assertEqual(result["side_effects"], [])
        self.assertIsNone(result["durable_memory_candidate"])
        reader.assert_called_once()

    def test_delegation_import_does_not_require_dee_klutter(self):
        """Calendar-capability imports must not pull in optional specialists."""
        completed = subprocess.run(
            [sys.executable, "-c", "import delegation; print('center-imported')"],
            cwd=Path(__file__).resolve().parent,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("center-imported", completed.stdout)

    def test_empty_calendar_is_successful(self):
        result = self.execution.execute("Check my calendar for tomorrow.", {}, {**self.request, "calendar_reader": Mock(return_value=[])})
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["result"], {"events": [], "count": 0})

    def test_google_failure_never_fabricates_events(self):
        result = self.execution.execute("Check my calendar for tomorrow.", {}, {**self.request, "calendar_reader": Mock(side_effect=RuntimeError("private"))})
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["result"])
        self.assertEqual(result["authoritative_source"], "google_calendar")

    def test_malformed_and_unsupported_requests_fail_structurally(self):
        missing = self.execution.execute("Check my calendar", {}, {"capability": "calendar_read"})
        unsupported = self.execution.execute("Do something", {}, {**self.request, "capability": "calendar_write"})
        self.assertEqual(missing["status"], "failed")
        self.assertIn("request_id", missing["errors"][0])
        self.assertEqual(unsupported["status"], "failed")
        self.assertIn("Unsupported", unsupported["errors"][0])

    def test_calendar_read_rejects_write_scope_and_never_persists(self):
        result = self.execution.execute("Check my calendar", {}, {**self.request, "authority_scope": "write", "calendar_reader": Mock()})
        self.assertEqual(result["status"], "failed")
        self.assertIn("read authority", result["errors"][0])

    def test_calendar_execution_neither_requires_sam2_nor_has_side_effects(self):
        reader = Mock(return_value=[])
        result = self.execution.execute(
            "Check my calendar for tomorrow.",
            {},
            {**self.request, "calendar_reader": reader},
        )
        self.assertEqual(result["side_effects"], [])
        self.assertIsNone(result["durable_memory_candidate"])
        reader.assert_called_once()

    def test_structured_calendar_request_bypasses_task_persistence(self):
        import delegation
        with patch.object(delegation, "create_task") as create_task:
            result = delegation.handle_message(
                "Check my calendar for tomorrow.",
                context={},
                metadata={**self.request, "calendar_reader": Mock(return_value=[])},
            )
        self.assertEqual(result["status"], "succeeded")
        create_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
