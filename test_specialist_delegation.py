import importlib
import inspect
import unittest
from unittest.mock import Mock, patch


class StructuredSpecialistDelegationTests(unittest.TestCase):
    def setUp(self):
        import specialist_delegation
        self.delegation = importlib.reload(specialist_delegation)
        self.request = {
            "request_id": "req-specialist-1",
            "specialist": "juan_whey",
            "task": "Find flight options for November.",
            "relevant_context": {"destination": "Lisbon"},
            "constraints": ["Avoid red-eyes"],
            "authority_scope": "read",
        }

    def test_fixed_registry_reaches_juan_and_richard_stubs(self):
        self.assertIsNotNone(self.delegation.get_specialist("juan_whey"))
        self.assertIsNotNone(self.delegation.get_specialist("richard"))
        for specialist in ("juan_whey", "richard"):
            with self.subTest(specialist=specialist):
                result = self.delegation.execute({**self.request, "specialist": specialist})
                self.assertEqual(result["status"], "succeeded")
                self.assertEqual(result["authoritative_source"], f"specialist_boundary:{specialist}")
                self.assertTrue(result["result"]["boundary_reached"])
                self.assertFalse(result["result"]["external_action_performed"])

    def test_malformed_requests_fail_structurally(self):
        cases = (
            ({**self.request, "request_id": ""}, "request_id"),
            ({**self.request, "specialist": ""}, "specialist"),
            ({**self.request, "task": ""}, "task"),
            ({**self.request, "relevant_context": "not an object"}, "relevant_context"),
            ({**self.request, "constraints": "not a list"}, "constraints"),
            ({**self.request, "specialist": "unknown"}, "Unsupported specialist"),
            ({**self.request, "authority_scope": "admin"}, "authority_scope"),
            ({**self.request, "authority_scope": "write"}, "read authority"),
        )
        for request, expected in cases:
            with self.subTest(expected=expected):
                result = self.delegation.execute(request)
                self.assertEqual(result["status"], "failed")
                self.assertIn(expected, result["errors"][0])

    def test_adapter_receives_only_structured_contract_and_failures_are_contained(self):
        adapter = Mock(return_value={"boundary_reached": True})
        with patch.object(self.delegation, "get_specialist", return_value=adapter):
            result = self.delegation.execute(self.request)
        self.assertEqual(result["status"], "succeeded")
        adapter.assert_called_once_with(self.request)

        with patch.object(self.delegation, "get_specialist", return_value=Mock(side_effect=RuntimeError("private"))):
            failed = self.delegation.execute(self.request)
        self.assertEqual(failed["status"], "failed")
        self.assertNotIn("private", failed["errors"][0])

        with patch.object(self.delegation, "get_specialist", return_value=Mock(return_value="invalid")):
            invalid = self.delegation.execute(self.request)
        self.assertEqual(invalid["status"], "failed")

    def test_structured_specialist_request_bypasses_task_persistence_and_sensitive_context(self):
        import delegation
        sensitive_context = {
            "sam2_facts": ["never persist"],
            "user_profile": {"name": "Example"},
            "conversation_history": ["never persist"],
        }
        with patch.object(delegation, "create_task") as create_task:
            result = delegation.handle_message(
                "Find flight options for November.",
                context=sensitive_context,
                metadata={
                    "request_id": "req-specialist-2",
                    "specialist": "juan_whey",
                    "constraints": ["Avoid red-eyes"],
                    "authority_scope": "read",
                },
            )
        self.assertEqual(result["status"], "succeeded")
        create_task.assert_not_called()
        self.assertIsNone(result["durable_memory_candidate"])

    def test_structured_specialist_boundary_has_no_sam2_or_provider_dependency(self):
        source = inspect.getsource(self.delegation).lower()
        self.assertNotIn("sam2", source)
        self.assertNotIn("oauth", source)
        self.assertNotIn("credential", source)


if __name__ == "__main__":
    unittest.main()
