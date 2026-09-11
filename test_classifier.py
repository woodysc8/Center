import unittest

from classifier import classify


class RuleBasedClassifierTests(unittest.TestCase):
    def assert_route(self, message, category, owner):
        result = classify(message)
        self.assertEqual(result["category"], category)
        self.assertEqual(result["owner"], owner)

    def test_gmail_search_routes_to_dee(self):
        self.assert_route(
            "Search my personal Gmail for emails from the last 7 days",
            "gmail",
            "dee_gmail",
        )

    def test_gmail_search_short_request_routes_to_dee(self):
        self.assert_route("Search my Gmail", "gmail", "dee_gmail")

    def test_inbox_request_routes_to_dee(self):
        self.assert_route("Check my inbox", "gmail", "dee_gmail")

    def test_reminder_to_email_stays_with_sheila(self):
        self.assert_route("Remind me to email Nora tomorrow", "reminder", "sheila")

    def test_existing_categories_are_unchanged(self):
        self.assert_route("Need advice on taxes", "finance", "richard")
        self.assert_route("Find me flights to Lisbon in October", "travel", "juan_whey")
        self.assert_route("Research the latest fintech news", "research", "unassigned")


if __name__ == "__main__":
    unittest.main()
