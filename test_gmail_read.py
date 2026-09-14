import importlib
import unittest
from unittest.mock import Mock, patch


class GmailReadCapabilityTests(unittest.TestCase):
    def setUp(self):
        import execution
        self.execution = importlib.reload(execution)
        self.request = {
            "request_id": "req-gmail-1",
            "capability": "gmail_read",
            "authority_scope": "read",
        }

    def _execute(self, gmail_request, reader):
        return self.execution.execute(
            "Read my Gmail.",
            {},
            {**self.request, "capability_input": gmail_request, "gmail_reader": reader},
        )

    def test_gmail_read_is_registered(self):
        from capabilities import gmail_read
        from capabilities.registry import get_capability

        self.assertIs(get_capability("gmail_read"), gmail_read.execute)

    def test_search_gmail_uses_injected_dee_adapter(self):
        dee_result = {"ok": True, "operation": "search_gmail", "account": "personal", "data": [], "error": None}
        reader = Mock(return_value=dee_result)
        gmail_request = {"operation": "search_gmail", "account": "personal", "query": "from:nick"}

        result = self._execute(gmail_request, reader)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["authoritative_source"], "dee_klutter")
        self.assertIs(result["result"], dee_result)
        reader.assert_called_once_with({"metadata": {"gmail_request": gmail_request}})

    def test_get_message_and_thread_succeed(self):
        for gmail_request in (
            {"operation": "get_message", "account": "personal", "message_id": "m1"},
            {"operation": "get_thread", "account": "school", "thread_id": "t1"},
        ):
            with self.subTest(operation=gmail_request["operation"]):
                result = self._execute(gmail_request, Mock(return_value={"ok": True, "data": {}}))
                self.assertEqual(result["status"], "succeeded")

    def test_invalid_operation_or_required_input_fails_without_calling_dee(self):
        for gmail_request in (
            {"operation": "delete_message", "account": "personal", "message_id": "m1"},
            {"operation": "get_message", "account": "personal"},
            None,
        ):
            with self.subTest(gmail_request=gmail_request):
                reader = Mock()
                result = self._execute(gmail_request, reader)
                self.assertEqual(result["status"], "failed")
                reader.assert_not_called()

    def test_write_authority_and_dee_failure_return_structured_failures(self):
        gmail_request = {"operation": "search_gmail", "account": "personal", "query": "in:inbox"}
        reader = Mock(return_value={"ok": False, "error": {"message": "Dee is unavailable"}})
        write = self.execution.execute("Read my Gmail.", {}, {**self.request, "authority_scope": "write", "capability_input": gmail_request, "gmail_reader": reader})
        failed = self._execute(gmail_request, reader)
        raised = self._execute(gmail_request, Mock(side_effect=RuntimeError("private adapter error")))
        self.assertEqual(write["status"], "failed")
        self.assertIn("read authority", write["errors"][0])
        reader.assert_called_once()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["authoritative_source"], "dee_klutter")
        self.assertEqual(raised["status"], "failed")
        self.assertEqual(raised["errors"], ["Dee-Klutter could not read Gmail."])

    def test_structured_gmail_bypasses_task_persistence_with_sensitive_context(self):
        import delegation
        gmail_request = {"operation": "search_gmail", "account": "personal", "query": "in:inbox"}
        with patch.object(delegation, "create_task") as create_task:
            result = delegation.handle_message(
                "Read my Gmail.",
                context={"sam2_facts": ["never persist"], "user_profile": {"name": "Example"}, "conversation_history": ["never persist"]},
                metadata={**self.request, "capability_input": gmail_request, "gmail_reader": Mock(return_value={"ok": True, "data": []})},
            )
        self.assertEqual(result["status"], "succeeded")
        create_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
