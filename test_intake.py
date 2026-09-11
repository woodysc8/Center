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


if __name__ == "__main__":
    unittest.main()
