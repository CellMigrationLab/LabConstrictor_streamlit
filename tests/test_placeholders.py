"""Tests for placeholders: the table fills every placeholder an installer ships, and line endings survive.

The template test needs a copy of the LabConstrictor template: set LC_TEMPLATE_DIR to its folder (a clone of
https://github.com/CellMigrationLab/LabConstrictor), or the test is skipped with that reason.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import placeholders  # noqa: E402

TEMPLATE = Path(os.environ["LC_TEMPLATE_DIR"]) if os.environ.get("LC_TEMPLATE_DIR") else None
ARGS = dict(project_name="Cool App-2", version="0.1.0", hide_code="False", welcome_image_path="app/logo/w.png",
            header_image_path="app/logo/h.png", icon_image_path="app/logo/i.png", github_owner="someone",
            github_repo_name="CoolApp")


def initialise(repo: Path) -> None:
    """Apply the conversion table to *repo*, as app.initialize_project does."""
    shutil.copyfile(repo / ".tools/templates/hide_code_cells.py", repo / "app/python_scripts/hide_code_cells.py")
    for placeholder, files in placeholders.conversion_table(**ARGS).items():
        for name, value in files.items():
            placeholders.replace_in_file(repo / name, placeholder, value)


class ReplaceInFileTests(unittest.TestCase):
    def test_crlf_and_lf_line_endings_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bat, sh = Path(folder) / "a.bat", Path(folder) / "a.sh"
            bat.write_bytes(b"echo PROJECT_NAME\r\nGOTO :fail\r\n:fail\r\n")
            sh.write_bytes(b"echo PROJECT_NAME\nexit 0\n")
            placeholders.replace_in_file(bat, "PROJECT_NAME", "Cool")
            placeholders.replace_in_file(sh, "PROJECT_NAME", "Cool")
            self.assertEqual(bat.read_bytes(), b"echo Cool\r\nGOTO :fail\r\n:fail\r\n")
            self.assertEqual(sh.read_bytes(), b"echo Cool\nexit 0\n")

    def test_python_name_of_a_project(self) -> None:
        self.assertEqual(placeholders.to_python_project_name("Cool App-2.x"), "cool_app_2_x")


class LeftoverTests(unittest.TestCase):
    def test_a_leftover_in_a_shipped_file_is_reported_and_others_are_not(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            (repo / "app").mkdir()
            (repo / "app/post_install.sh").write_text("import PYTHON_PROJ_NAME_lc_tools\n", encoding="utf-8")
            (repo / "app/logo.png").write_bytes(b"\x89PNG\xff\xfe")
            (repo / ".tools").mkdir()
            (repo / ".tools/bump_version.py").write_text("VERSION_NUMBER\n", encoding="utf-8")
            self.assertEqual(placeholders.leftover_placeholders(repo), ["app/post_install.sh: PYTHON_PROJ_NAME"])


@unittest.skipUnless(TEMPLATE, "set LC_TEMPLATE_DIR to a clone of the LabConstrictor template")
class TemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repo = Path(self.folder.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo, ignore=shutil.ignore_patterns(".git"))

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_no_placeholder_is_left_in_what_the_installer_ships(self) -> None:
        initialise(self.repo)
        self.assertEqual(placeholders.leftover_placeholders(self.repo), [])

    def test_the_installer_checks_and_registers_the_package(self) -> None:
        initialise(self.repo)
        for script in ("post_install.sh", "post_install.bat"):
            text = (self.repo / "app/bash_bat_scripts" / script).read_text(encoding="utf-8")
            self.assertIn("import cool_app_2", text, script)
            self.assertIn("cool_app_2_lc_tools", text, script)

    def test_line_endings_of_every_changed_file_are_kept(self) -> None:
        names = {name for files in placeholders.conversion_table(**ARGS).values() for name in files}
        shutil.copyfile(self.repo / ".tools/templates/hide_code_cells.py", self.repo / "app/python_scripts/hide_code_cells.py")
        before = {name: (self.repo / name).read_bytes().count(b"\r\n") for name in names}
        initialise(self.repo)
        for name in sorted(names):
            self.assertEqual((self.repo / name).read_bytes().count(b"\r\n"), before[name], name)


if __name__ == "__main__":
    unittest.main()
