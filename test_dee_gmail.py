import unittest
from unittest.mock import patch

from specialists import dee_gmail


class DeeGmailSpecialistTests(unittest.TestCase):
    def task(self, request):
        return {"metadata": {"gmail_request": request}}

    def test_registered_in_specialists(self):
        import delegation

        self.assertIs(delegation.SPECIALISTS["dee_gmail"], dee_gmail.handle_task)

    def test_search_request_calls_dee_and_returns_success_envelope(self):
        data = [{"message_id": "m1"}]
        with patch.object(dee_gmail, "search_gmail", return_value=data) as call:
            result = dee_gmail.handle_task(self.task({
                "operation": "search_gmail",
                "account": "personal",
                "query": "from:nick boston",
                "max_results": 20,
            }))

        call.assert_called_once_with(
            query="from:nick boston", account="personal", max_results=20
        )
        self.assertEqual(result, {
            "ok": True,
            "operation": "search_gmail",
            "account": "personal",
            "data": data,
            "error": None,
        })

    def test_get_message_request_calls_dee(self):
        data = {"message_id": "m1", "body": "hello"}
        with patch.object(dee_gmail, "get_message", return_value=data) as call:
            result = dee_gmail.handle_task(self.task({
                "operation": "get_message",
                "account": "personal",
                "message_id": "m1",
            }))

        call.assert_called_once_with(message_id="m1", account="personal")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], data)

    def test_get_thread_request_calls_dee(self):
        data = {"thread_id": "t1", "messages": []}
        with patch.object(dee_gmail, "get_thread", return_value=data) as call:
            result = dee_gmail.handle_task(self.task({
                "operation": "get_thread",
                "account": "school",
                "thread_id": "t1",
            }))

        call.assert_called_once_with(thread_id="t1", account="school")
        self.assertTrue(result["ok"])
        self.assertEqual(result["account"], "school")

    def test_missing_required_field_rejected_without_calling_dee(self):
        with patch.object(dee_gmail, "get_message") as call:
            result = dee_gmail.handle_task(self.task({
                "operation": "get_message",
                "account": "personal",
            }))

        call.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_unsupported_operation_rejected_without_calling_dee(self):
        with patch.object(dee_gmail, "search_gmail") as call:
            result = dee_gmail.handle_task(self.task({
                "operation": "delete_message",
                "account": "personal",
                "message_id": "m1",
            }))

        call.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_dee_error_becomes_stable_error_envelope(self):
        error = dee_gmail.NotFoundError("Gmail resource was not found", account="personal")
        with patch.object(dee_gmail, "get_message", side_effect=error):
            result = dee_gmail.handle_task(self.task({
                "operation": "get_message",
                "account": "personal",
                "message_id": "missing",
            }))

        self.assertEqual(result, {
            "ok": False,
            "operation": "get_message",
            "account": "personal",
            "data": None,
            "error": {"code": "not_found", "message": "Gmail resource was not found"},
        })

    def test_malformed_task_metadata_is_rejected(self):
        result = dee_gmail.handle_task({"metadata": {"gmail_request": "not-an-object"}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
