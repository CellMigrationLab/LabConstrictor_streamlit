"""Tests for initializer: initialising the real LabConstrictor template leaves no placeholder behind (LabConstrictor#40).

The template is read from LC_TEMPLATE_DIR when it is set (a checkout of CellMigrationLab/LabConstrictor), otherwise downloaded
from the template's main branch. The tests that need it are skipped when neither is available (offline), never failed.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import initializer  # noqa: E402

TEMPLATE_ZIP = "https://github.com/CellMigrationLab/LabConstrictor/archive/refs/heads/main.zip"
PROJECT = "My Cool-App 2.0"
PACKAGE = "my_cool_app_2_0"

# Placeholders that initialisation must replace (the keys of placeholder_map, plus the launcher icon paths it fills in itself).
INIT_PLACEHOLDERS = (
    "LOWER_PROJ_NAME",
    "PYTHON_PROJ_NAME",
    "UNDERSCORED_PROJECT_NAME",
    "PROJECT_NAME",
    "VERSION_NUMBER",
    "WELCOME_IMAGE",
    "HEADER_IMAGE",
    "ICON_IMAGE",
    "GITHUB_OWNER",
    "GITHUB_REPO_NAME",
    "HIDE_CODE_DISABLED",
    "ICON_IMAGE_PATH",
    "ICON_ICO_IMAGE_PATH",
    "ICON_ICNS_IMAGE_PATH",
)
# Not shipped by the installer, or about placeholders rather than holding one.
SKIPPED_PREFIXES = (".git/", ".template_sync/", "tests/", ".tools/docs/")
# Placeholders the template fills in later, at release time, on purpose: (file, placeholder).
LATER = {
    (".tools/templates/download_executable_template.md", "VERSION_NUMBER"),  # bump_version.py
    (".tools/templates/Welcome_template.ipynb", "GITHUB_OWNER"),  # bump_Welcome_notebook.py
    (".tools/templates/Welcome_template.ipynb", "GITHUB_REPO_NAME"),
    (".tools/templates/hide_code_cells.py", "HIDE_CODE_DISABLED"),  # the template copy; the app copy is filled in
    (".tools/python/bump_version.py", "VERSION_NUMBER"),  # the scripts that do the release-time replacing
    (".tools/python/bump_Welcome_notebook.py", "GITHUB_OWNER"),
    (".tools/python/bump_Welcome_notebook.py", "GITHUB_REPO_NAME"),
}


def placeholder_pattern(name: str) -> re.Pattern[str]:
    """A placeholder on its own or followed by '_' (PYTHON_PROJ_NAME_lc_tools), never inside a longer name (UNDERSCORED_PROJECT_NAME)."""
    return re.compile(r"(?<![A-Za-z0-9_])" + name + r"(?![A-Za-z0-9])")


def leftover_placeholders(repo: Path) -> list[str]:
    found = []
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo).as_posix()
        if not path.is_file() or rel.startswith(SKIPPED_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in INIT_PLACEHOLDERS:
            if (rel, name) not in LATER and placeholder_pattern(name).search(text):
                found.append(f"{rel}: {name}")
    return found


def template_source() -> Path | None:
    """The template folder: LC_TEMPLATE_DIR, or main downloaded once into a temporary folder (None when offline)."""
    given = os.environ.get("LC_TEMPLATE_DIR")
    if given:
        return Path(given)
    if getattr(template_source, "cache", None):
        return template_source.cache  # type: ignore[attr-defined]
    try:
        with urllib.request.urlopen(TEMPLATE_ZIP, timeout=60) as response:
            data = response.read()
    except OSError:
        return None
    target = Path(tempfile.mkdtemp(prefix="lc_template_"))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(target)
    (root,) = [p for p in target.iterdir() if p.is_dir()]
    template_source.cache = root  # type: ignore[attr-defined]
    return root


class PlaceholderMapTests(unittest.TestCase):
    """Offline checks of the map itself."""

    def setUp(self) -> None:
        self.mapping = initializer.placeholder_map(
            project_name=PROJECT, version="0.0.1", hide_code=False, welcome_image_path=None, header_image_path=None,
            icon_image_path=None, github_owner="someone", github_repo_name="my-cool-app",
        )

    def test_the_post_install_scripts_get_the_package_name(self) -> None:
        for script in ("app/bash_bat_scripts/post_install.sh", "app/bash_bat_scripts/post_install.bat"):
            self.assertEqual(self.mapping["PYTHON_PROJ_NAME"][script], PACKAGE)

    def test_the_launcher_gets_the_display_name(self) -> None:
        self.assertEqual(self.mapping["PROJECT_NAME"]["app/python_scripts/launch_jupyter.py"], PROJECT)

    def test_underscored_project_name_is_replaced_before_project_name(self) -> None:
        keys = list(self.mapping)
        self.assertLess(keys.index("UNDERSCORED_PROJECT_NAME"), keys.index("PROJECT_NAME"))


class RealTemplateTests(unittest.TestCase):
    """Initialise the current template exactly as the web form does, then look for what was left."""

    repo: Path

    @classmethod
    def setUpClass(cls) -> None:
        source = template_source()
        if source is None:
            raise unittest.SkipTest("the LabConstrictor template is not available offline: set LC_TEMPLATE_DIR")
        cls._tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls._tmp.name) / "repo"
        shutil.copytree(source, cls.repo, ignore=shutil.ignore_patterns(".git"))
        initializer.initialize_project(
            repo_path=cls.repo, project_name=PROJECT, version="0.0.1", hide_code=False,
            welcome_image_path=None, header_image_path=None, icon_image_path=None, ico_image_path=None, icns_image_path=None,
            github_owner="someone", github_repo_name="my-cool-app",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_no_placeholder_is_left(self) -> None:
        self.assertEqual(leftover_placeholders(self.repo), [], "add these files to placeholder_map in initializer.py")

    def test_the_installer_imports_the_package_that_src_holds(self) -> None:
        self.assertTrue((self.repo / "src" / PACKAGE / "__init__.py").is_file())
        sh = (self.repo / "app/bash_bat_scripts/post_install.sh").read_text(encoding="utf-8")
        bat = (self.repo / "app/bash_bat_scripts/post_install.bat").read_text(encoding="utf-8")
        for text in (sh, bat):
            self.assertIn(f"import {PACKAGE};", text)
            self.assertIn(f"{PACKAGE}_lc_tools", text)
        self.assertRegex((self.repo / "setup.py").read_text(encoding="utf-8"), rf"name\s*=\s*[\"']{PACKAGE}[\"']")

    def test_the_launcher_names_the_app(self) -> None:
        text = (self.repo / "app/python_scripts/launch_jupyter.py").read_text(encoding="utf-8")
        self.assertIn(f'PROJECT_DISPLAY_NAME = "{PROJECT}"', text)

    def test_the_bat_files_keep_their_line_endings(self) -> None:
        source = template_source()
        assert source is not None
        for rel in ("app/bash_bat_scripts/post_install.bat", "app/bash_bat_scripts/pre_uninstall.bat"):
            before = (source / rel).read_bytes()
            after = (self.repo / rel).read_bytes()
            self.assertEqual(b"\r\n" in before, b"\r\n" in after, rel)


class LeftoverDetectionTests(unittest.TestCase):
    """The detector itself: what it reports and what it leaves alone."""

    def test_it_reports_a_placeholder_and_its_lc_tools_form_but_not_longer_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "app").mkdir()
            (repo / "app/a.sh").write_text('M="PYTHON_PROJ_NAME_lc_tools"\n', encoding="utf-8")
            (repo / "app/b.bat").write_text("SET X=UNDERSCORED_PROJECT_NAME\n", encoding="utf-8")
            (repo / "app/c.txt").write_text("PROJECT_ROOT and MY_PROJECT_NAME_X are fine\n", encoding="utf-8")
            (repo / ".tools/docs").mkdir(parents=True)
            (repo / ".tools/docs/x.md").write_text("PYTHON_PROJ_NAME is explained here\n", encoding="utf-8")
            self.assertEqual(leftover_placeholders(repo), ["app/a.sh: PYTHON_PROJ_NAME", "app/b.bat: UNDERSCORED_PROJECT_NAME"])


if __name__ == "__main__":
    unittest.main()
