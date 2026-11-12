"""Initialise a repository created from the LabConstrictor template: replace the template's placeholders.

Kept apart from app.py (no Streamlit import) so that tests/test_initializer.py can run it on the real template.
"""
from __future__ import annotations

import shutil

import yaml


def to_python_project_name(project_name: str) -> str:
    return project_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def replace_in_file(file_path, old, new):
    # newline="" keeps the file's own line endings (CRLF in the .bat files) on every OS.
    with open(file_path, 'r', encoding='utf-8', newline='') as file:
        content = file.read()
    content = content.replace(old, str(new).strip())
    with open(file_path, 'w', encoding='utf-8', newline='') as file:
        file.write(content)


def capture_yaml_key_lines(yaml_text: str, key: str):
    """Return all lines whose trimmed content starts with '<key>:'."""
    prefix = f"{key}:"
    captured = []
    for line in yaml_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(prefix):
            indent = line[: len(line) - len(stripped)]
            captured.append(f"{indent}{stripped}")
    return captured


def restore_yaml_duplicate_keys(serialized_text: str, key: str, preserved_lines):
    """Replace the serialized '<key>:' line with the preserved lines (i.e., duplicates)."""
    if not preserved_lines:
        return serialized_text
    key_prefix = f"{key}:"
    output_lines = []
    inserted = False
    for line in serialized_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(key_prefix):
            if not inserted:
                output_lines.extend(preserved_lines)
                inserted = True
            continue
        output_lines.append(line)

    if not inserted:
        output_lines.extend(preserved_lines)

    if serialized_text.endswith("\n"):
        return "\n".join(output_lines) + "\n"
    return "\n".join(output_lines)


def placeholder_map(project_name, version, hide_code, welcome_image_path, header_image_path,
                    icon_image_path, github_owner, github_repo_name):
    """The placeholders of the LabConstrictor template and, for each one, the files it is replaced in and its value.

    The keys are replaced in this order: UNDERSCORED_PROJECT_NAME must come before PROJECT_NAME, which it contains.
    Every template file that the installer ships must be listed for each placeholder it holds: a placeholder left
    in one of them breaks the installer (issue CellMigrationLab/LabConstrictor#40). tests/test_initializer.py
    initialises the current template and fails when one is left.
    """
    proyectname_lower = project_name.lower()
    python_project_name = to_python_project_name(project_name)
    return {
        "LOWER_PROJ_NAME": {
            "environment.yaml": proyectname_lower,
            ".tools/templates/download_executable_template.md": proyectname_lower,
        },
        "PYTHON_PROJ_NAME": {
            "setup.py": python_project_name,
            ".tools/docs/external_code_upload.md": python_project_name,
            ".tools/templates/Welcome_template.ipynb": python_project_name,
            # The import check and the <package>_lc_tools module name of the installer (template 0.1.16 and later).
            "app/bash_bat_scripts/post_install.sh": python_project_name,
            "app/bash_bat_scripts/post_install.bat": python_project_name,
        },
        "UNDERSCORED_PROJECT_NAME": {
            "construct.yaml": project_name.replace(" ", "_"),
            "app/bash_bat_scripts/pre_uninstall.bat": project_name.replace(" ", "_"),
            "app/bash_bat_scripts/post_install.bat": project_name.replace(" ", "_"),
        },
        "PROJECT_NAME": {
            "construct.yaml": project_name,
            "app/menuinst/notebook_launcher.json": project_name,
            "app/bash_bat_scripts/post_install.bat": project_name,
            "app/bash_bat_scripts/post_install.sh": project_name,
            "app/bash_bat_scripts/pre_uninstall.bat": project_name,
            "app/bash_bat_scripts/pre_uninstall.sh": project_name,
            "app/bash_bat_scripts/uninstall.sh": project_name,
            ".tools/templates/Welcome_template.ipynb": project_name,
            ".tools/templates/download_executable_template.md": project_name,
            ".tools/python/bump_constructor.py": project_name,
            # PROJECT_DISPLAY_NAME of the JupyterLab launcher (its window titles and error messages).
            "app/python_scripts/launch_jupyter.py": project_name,
        },
        "VERSION_NUMBER": {
            "construct.yaml": version,
            "app/bash_bat_scripts/post_install.bat": version,
            "setup.py": version,
        },
        "WELCOME_IMAGE": {
            "construct.yaml": welcome_image_path,
        },
        "HEADER_IMAGE": {
            "construct.yaml": header_image_path,
        },
        "ICON_IMAGE": {
            "construct.yaml": icon_image_path,
        },
        "GITHUB_OWNER": {
            "app/bash_bat_scripts/post_install.bat": github_owner,
            ".tools/templates/download_executable_template.md": github_owner,
        },
        "GITHUB_REPO_NAME": {
            ".tools/templates/download_executable_template.md": github_repo_name,
        },
        "HIDE_CODE_DISABLED": {
            "app/python_scripts/hide_code_cells.py": hide_code,
        }
    }


def initialize_project(repo_path, project_name, version, hide_code,
                       welcome_image_path, header_image_path, icon_image_path,
                       ico_image_path, icns_image_path, 
                       github_owner, github_repo_name):

    # Copy and replace template files into their final locations
    template_to_location = {
        ".tools/templates/hide_code_cells.py": "app/python_scripts/hide_code_cells.py"
    }

    for template_path, final_path in template_to_location.items():
        shutil.copyfile(repo_path / template_path, repo_path / final_path)

    conversion_dict = placeholder_map(
        project_name=project_name,
        version=version,
        hide_code=hide_code,
        welcome_image_path=welcome_image_path,
        header_image_path=header_image_path,
        icon_image_path=icon_image_path,
        github_owner=github_owner,
        github_repo_name=github_repo_name,
    )
    python_project_name = to_python_project_name(project_name)

    # Replace placeholders in files
    for placeholder, files in conversion_dict.items():
        for file_path, replacement in files.items():
            replace_in_file(repo_path / file_path, placeholder, replacement)

    package_dir = repo_path / "src" / python_project_name
    package_dir.mkdir(parents=True, exist_ok=True)
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")

    # Update the notebook launcher JSON file to set the icons if needed
    notebook_launcher_path = repo_path / "app" / "menuinst" / "notebook_launcher.json"
    if notebook_launcher_path.exists():
        with open(notebook_launcher_path, "r", encoding="utf-8") as f:
            launcher_data = f.read()
        if icon_image_path:
            launcher_data = launcher_data.replace("ICON_IMAGE_PATH", f"BASE_PATH_KEYWORD/{project_name}/{icon_image_path.name}")
        else:
            launcher_data = launcher_data.replace("ICON_IMAGE_PATH", f"")
        if ico_image_path:
            launcher_data = launcher_data.replace("ICON_ICO_IMAGE_PATH", f"BASE_PATH_KEYWORD/{project_name}/{ico_image_path.name}")
        else:
            launcher_data = launcher_data.replace("ICON_ICO_IMAGE_PATH", f"")
        if icns_image_path:
            launcher_data = launcher_data.replace("ICON_ICNS_IMAGE_PATH", f"BASE_PATH_KEYWORD/{project_name}/{icns_image_path.name}")
        else:
            launcher_data = launcher_data.replace("ICON_ICNS_IMAGE_PATH", f"")
        with open(notebook_launcher_path, "w", encoding="utf-8") as f:
            f.write(launcher_data)

    # Update the construct.yaml extra_files to include the images if they were provided
    # Read the construct.yaml to check if images need to be set
    construct_path = repo_path / "construct.yaml"
    construct_raw_text = construct_path.read_text(encoding="utf-8")
    post_install_lines = capture_yaml_key_lines(construct_raw_text, "post_install")
    pre_uninstall_lines = capture_yaml_key_lines(construct_raw_text, "pre_uninstall")
    construct_data = yaml.safe_load(construct_raw_text)
    if construct_data is None:
        construct_data = {}
    extra_files = construct_data.get("extra_files")
    if extra_files is None:
        extra_files = []
        construct_data["extra_files"] = extra_files
    

    # Check if the welcome, header, icon images were provided and in case they were not, set them to empty in the construct.yaml
    if not welcome_image_path:
        construct_data.pop("welcome_image", None)
    if not header_image_path:
        construct_data.pop("header_image", None)
    if not icon_image_path:
        construct_data.pop("icon_image", None)

    # Normalize existing entries into a dict for quick lookup
    existing_sources = set()
    existing_dests = set()
    normalized_items = []

    for item in extra_files:
        # Items can be either dicts (k: v) or strings with mapping? Assume dicts per example
        if isinstance(item, dict):
            for src, dst in item.items():
                existing_sources.add(str(src))
                existing_dests.add(str(dst))
                normalized_items.append({str(src): str(dst)})
        else:
            # If strings are present, keep them
            normalized_items.append(item)

    # Check if the images paths are provided and not already in the list¨
    image_mappings = [ icon_image_path, ico_image_path, icns_image_path ]

    for src_path in image_mappings:
        if src_path:
            dest_path = f"{project_name}/{src_path.name}"
            if src_path and str(src_path) not in existing_sources and dest_path not in existing_dests:
                normalized_items.append({str(src_path): dest_path})
                
    # Optionally sort entries (dicts by their single key) for determinism
    def sort_key(item):
        if isinstance(item, dict):
            # single-key dict
            k = next(iter(item.keys()))
            return (0, k)
        return (1, str(item))

    normalized_items.sort(key=sort_key)
    construct_data["extra_files"] = normalized_items

    # Write back the updated construct.yaml
    construct_serialized = yaml.dump(construct_data, sort_keys=False)
    construct_serialized = restore_yaml_duplicate_keys(
        construct_serialized, "post_install", post_install_lines
    )
    construct_serialized = restore_yaml_duplicate_keys(
        construct_serialized, "pre_uninstall", pre_uninstall_lines
    )
    construct_path.write_text(construct_serialized, encoding="utf-8")
