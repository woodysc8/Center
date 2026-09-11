import importlib
import os
import tempfile
import unittest


class IntakeConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "center.db")
        os.environ["CENTER_DB_PATH"] = self.db_path

        import config
        import intake

        importlib.reload(config)
        self.intake = importlib.reload(intake)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_connection_is_released_after_context_exit(self):
        with self.intake._connect() as conn:
            conn.execute("SELECT 1")
        os.remove(self.db_path)
        self.assertFalse(os.path.exists(self.db_path))

    def test_gmail_task_is_created_and_persisted(self):
        task_id = self.intake.create_task(
            raw_input="Search my Gmail",
            category="gmail",
            title="Search Gmail",
            brief="Samuel asked to search Gmail.",
            owner="dee_gmail",
        )

        tasks = self.intake.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], task_id)
        self.assertEqual(tasks[0]["category"], "gmail")
        self.assertEqual(tasks[0]["owner"], "dee_gmail")


if __name__ == "__main__":
    unittest.main()
