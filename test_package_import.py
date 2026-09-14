import subprocess
import sys
import tempfile
import unittest
import zipfile
from shutil import copytree, ignore_patterns
from pathlib import Path


class PackageImportTests(unittest.TestCase):
    def test_wheel_contains_runtime_modules_and_imports_without_dee(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source = temporary_path / "source"
            copytree(root, source, ignore=ignore_patterns(".git", "build", "*.egg-info", "__pycache__", ".pytest_cache"))
            wheel_dir = temporary_path / "wheel"
            completed = subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheel_dir), "."],
                cwd=source,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            wheel = next(wheel_dir.glob("center-*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                names = set(archive.namelist())
                self.assertTrue({"config.py", "intake.py", "delegation.py", "execution.py", "specialist_delegation.py", "capabilities/calendar_read.py", "capabilities/gmail_read.py", "capabilities/registry.py", "center/__init__.py"}.issubset(names))
                metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
                metadata = archive.read(metadata_name).decode("utf-8")
                self.assertIn("Requires-Python: >=3.10", metadata)
                archive.extractall(temporary_path / "runtime")

            imported = subprocess.run(
                [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import execution, delegation, specialist_delegation; from capabilities import calendar_read; import center; print('ok')", str(temporary_path / "runtime")],
                cwd=temporary_path,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertIn("ok", imported.stdout)


if __name__ == "__main__":
    unittest.main()
