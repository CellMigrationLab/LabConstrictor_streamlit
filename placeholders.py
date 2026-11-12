"""Template placeholders: which file gets which value when a repository is initialised, and the rewriting itself.

Kept apart from app.py (which builds the Streamlit page when it is imported) so that tests can check the table
against a real copy of the LabConstrictor template.
"""

from __future__ import annotations

import re
from pathlib import Path

# Placeholders that must not survive initialisation in the files an installer ships (app/, setup.py, construct.yaml).
# A leftover one breaks the installed app: template 0.1.16+ post_install scripts ran `import PYTHON_PROJ_NAME`.
SHIPPED_PLACEHOLDERS = ("PYTHON_PROJ_NAME", "UNDERSCORED_PROJECT_NAME", "LOWER_PROJ_NAME", "PROJECT_NAME", "VERSION_NUMBER",
                        "GITHUB_OWNER", "GITHUB_REPO_NAME", "HIDE_CODE_DISABLED")
SHIPPED_PATHS = ("app", "setup.py", "construct.yaml")


def to_python_project_name(project_name: str) -> str:
    """Return the Python package name for a project name ("Cool App-2" -> "cool_app_2")."""
    return project_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def conversion_table(project_name: str, version: str, hide_code: str, welcome_image_path: object, header_image_path: object,
                     icon_image_path: object, github_owner: str, github_repo_name: str) -> dict[str, dict[str, object]]:
    """Return {placeholder: {file relative to the repository: value}}, in the order the placeholders must be replaced.

    Longer placeholders come before the ones they contain (UNDERSCORED_PROJECT_NAME before PROJECT_NAME).
    """
    lower = project_name.lower()
    python_name = to_python_project_name(project_name)
    underscored = project_name.replace(" ", "_")
    return {
        "LOWER_PROJ_NAME": {
            "environment.yaml": lower,
            ".tools/templates/download_executable_template.md": lower,
        },
        "PYTHON_PROJ_NAME": {
            "setup.py": python_name,
            ".tools/docs/external_code_upload.md": python_name,
            ".tools/templates/Welcome_template.ipynb": python_name,
            # The import check and the <package>_lc_tools registration of the installer (template 0.1.16+).
            "app/bash_bat_scripts/post_install.sh": python_name,
            "app/bash_bat_scripts/post_install.bat": python_name,
        },
        "UNDERSCORED_PROJECT_NAME": {
            "construct.yaml": underscored,
            "app/bash_bat_scripts/pre_uninstall.bat": underscored,
            "app/bash_bat_scripts/post_install.bat": underscored,
        },
        "PROJECT_NAME": {
            "construct.yaml": project_name,
            "app/menuinst/notebook_launcher.json": project_name,
            "app/bash_bat_scripts/post_install.bat": project_name,
            "app/bash_bat_scripts/post_install.sh": project_name,
            "app/bash_bat_scripts/pre_uninstall.bat": project_name,
            "app/bash_bat_scripts/pre_uninstall.sh": project_name,
            "app/bash_bat_scripts/uninstall.sh": project_name,
            "app/python_scripts/launch_jupyter.py": project_name,
            ".tools/templates/Welcome_template.ipynb": project_name,
            ".tools/templates/download_executable_template.md": project_name,
            ".tools/python/bump_constructor.py": project_name,
        },
        "VERSION_NUMBER": {
            "construct.yaml": version,
            "app/bash_bat_scripts/post_install.bat": version,
            "setup.py": version,
        },
        "WELCOME_IMAGE": {"construct.yaml": welcome_image_path},
        "HEADER_IMAGE": {"construct.yaml": header_image_path},
        "ICON_IMAGE": {"construct.yaml": icon_image_path},
        "GITHUB_OWNER": {
            "app/bash_bat_scripts/post_install.bat": github_owner,
            ".tools/templates/download_executable_template.md": github_owner,
        },
        "GITHUB_REPO_NAME": {".tools/templates/download_executable_template.md": github_repo_name},
        "HIDE_CODE_DISABLED": {"app/python_scripts/hide_code_cells.py": hide_code},
    }


def replace_in_file(file_path: Path, old: str, new: object) -> None:
    """Replace *old* by *new* in a text file, keeping its line endings.

    newline="" reads and writes the bytes of each line ending unchanged: the Windows scripts of the template use
    CR LF, and cmd.exe can miss GOTO/CALL labels in a batch file whose lines end in LF only.
    """
    with open(file_path, encoding="utf-8", newline="") as handle:
        content = handle.read()
    with open(file_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(content.replace(old, str(new).strip()))


def leftover_placeholders(repo_path: Path) -> list[str]:
    """Return "<file>: <placeholder>" for every shipped placeholder still present in the files an installer ships."""
    pattern = re.compile("|".join(sorted(SHIPPED_PLACEHOLDERS, key=len, reverse=True)))
    found = []
    for name in SHIPPED_PATHS:
        root = repo_path / name
        files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else [root] if root.is_file() else []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # images and other binary files carry no placeholder
            found += [f"{path.relative_to(repo_path).as_posix()}: {m}" for m in sorted(set(pattern.findall(text)))]
    return found
