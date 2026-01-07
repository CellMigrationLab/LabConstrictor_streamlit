from __future__ import annotations

from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image
import streamlit as st
import subprocess
import requests
import struct
import base64
import shutil
import yaml
import stat
import re
import os

st.set_page_config(page_title="LabConstrictor - Repository initializer", 
                   page_icon="🐍",
                   layout="wide",
                   )

MAX_FILE_SIZE_MB = 25

if "ready_for_pr" not in st.session_state:
    st.session_state["ready_for_pr"] = False
if "github_repo_url" not in st.session_state:
    st.session_state["github_repo_url"] = ""

def validate_submission(submitted_info):
    """Ensure required inputs exist and meet basic quality checks."""
    errors = []

    project_name = submitted_info.get("project_name", "").strip()
    if not project_name:
        errors.append("Project name is required.")

    project_version = submitted_info.get("project_version", "").strip()
    if not project_version:
        errors.append("Project version is required.")
    else:
        semver_pattern = r"^\d+\.\d+\.\d+(-[0-9A-Za-z-.]+)?(\+[0-9A-Za-z-.]+)?$"
        if not re.match(semver_pattern, project_version):
            errors.append("Project version must follow semantic versioning (e.g., 1.0.0).")

    if uploaded_icon := submitted_info.get("icon_uploaded"):
        if uploaded_icon.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            errors.append(f"Icon file '{uploaded_icon.name}' exceeds {MAX_FILE_SIZE_MB} MB limit.")
    if uploaded_welcome := submitted_info.get("welcome_uploaded"):
        if uploaded_welcome.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            errors.append(f"Welcome file '{uploaded_welcome.name}' exceeds {MAX_FILE_SIZE_MB} MB limit.")
    if uploaded_headers := submitted_info.get("headers_uploaded"):
        if uploaded_headers.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            errors.append(f"Headers file '{uploaded_headers.name}' exceeds {MAX_FILE_SIZE_MB} MB limit.")

    if not errors:
        st.session_state["ready_for_pr"] = True
    else:
        st.session_state["ready_for_pr"] = False

    return errors


def reset_tool_versions():
    for key in ("jupyterlab_version", "notebook_version", "matplotlib_version"):
        if key in st.session_state:
            del st.session_state[key]

def get_authenticated_username(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    response = requests.get("https://api.github.com/user", headers=headers)
    if response.status_code == 200:
        return response.json().get("login", "user")
    else:
        raise RuntimeError(f"❌ Could not retrieve GitHub username: {response.status_code} — {response.text}")
    
def has_changes_to_commit(path, cwd):
    try:
        status = run_git_command(["status", "--porcelain", str(path)], cwd=cwd)
        return bool(status.strip())
    except Exception as e:
        st.write(f"⚠️ Could not check changes: {e}")
        return False

def run_git_command(args, cwd=None, github_token=None):
    git_cmd = ["git"]
    env = None
    if github_token:
        sanitized_token = github_token.strip()
        if sanitized_token:
            basic_token = base64.b64encode(
                f"x-access-token:{sanitized_token}".encode("utf-8")
            ).decode("ascii")
            auth_value = f"Basic {basic_token}"
            git_cmd.extend(["-c", f"http.extraHeader=Authorization: {auth_value}"])
            env = os.environ.copy()
            env["GIT_HTTP_AUTHORIZATION"] = auth_value
    result = subprocess.run(
        git_cmd + args, cwd=cwd, capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        raise RuntimeError(f"❌ Git error running 'git {' '.join(args)}':\n{result.stderr.strip()}")
    return result.stdout.strip()

def push_config_changes_to_new_branch(
    folder, branch_prefix, commit_message, github_token, repo_path
):
    try:

        username = get_authenticated_username(github_token)
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        new_branch = f"{branch_prefix}/{username}-{timestamp}"

        run_git_command(["config", "user.email", f"{username}@users.noreply.github.com"], cwd=repo_path)
        run_git_command(["config", "user.name", username], cwd=repo_path)

        run_git_command(["checkout", "main"], cwd=repo_path)
        run_git_command(["pull", "origin", "main"], cwd=repo_path, github_token=github_token)

        if not has_changes_to_commit(folder, cwd=repo_path):
            st.write(f"ℹ️ No changes detected in `{folder}`. Nothing to push.")
            return None
        else:
            st.write(f"✅ Changes detected!")

        run_git_command(["checkout", "-b", new_branch], cwd=repo_path)
        run_git_command(["add", folder], cwd=repo_path)
        run_git_command(["commit", "-m", commit_message], cwd=repo_path)
        run_git_command(
            ["push", "--set-upstream", "origin", new_branch],
            cwd=repo_path,
            github_token=github_token,
        )

        st.write(f"✅ Successfully pushed to branch `{new_branch}`.")
        return new_branch

    except Exception as e:
        st.write(f"❌ Failed to push changes: {e}")
        return None
    
def create_pull_request(from_branch, title, body, github_repo_url, github_token):
    try:
        repo_url = github_repo_url.strip().rstrip('/')
        github_owner, github_repo_name = repo_url.split('/')[-2:]
        api_url = f"https://api.github.com/repos/{github_owner}/{github_repo_name}/pulls"

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token.strip()}"
        }

        payload = {
            "title": title,
            "head": from_branch,
            "base": "main",
            "body": body,
            "maintainer_can_modify": True
        }

        response = requests.post(api_url, headers=headers, json=payload)

        if response.status_code == 201:
            pr_url = response.json()["html_url"]
            st.write(f"✅ Pull request created: {pr_url}")
            return response.json()

        elif response.status_code == 422 and "already exists" in response.text:
            st.write(f"ℹ️ Pull request already exists for branch `{from_branch}`. It has been automatically updated.")
            return None

        else:
            st.write(f"❌ Failed to create pull request: {response.status_code} — {response.text}")
            return None

    except Exception as e:
        st.write(f"❌ Error creating PR: {e}")
        return None
    
def push_and_create_pr(folder, branch_prefix, 
                       commit_message, pr_title, pr_body, 
                       github_repo_url, github_token, 
                       repo_path):
    branch = push_config_changes_to_new_branch(
        folder=folder,
        branch_prefix=branch_prefix,
        commit_message=commit_message,
        github_token=github_token,
        repo_path=repo_path
    )
    if branch:
        create_pull_request(
            from_branch=branch,
            title=pr_title,
            body=pr_body,
            github_repo_url=github_repo_url,
            github_token=github_token
        )

# Handle Windows permission issues with .git directories
def handle_remove_error(func, path, exc_info):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
        func(path)
    else:
        raise exc_info[1]
        
def replace_in_file(file_path, old, new):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    content = content.replace(old, str(new).strip())
    with open(file_path, 'w', encoding='utf-8') as file:
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


def create_icns(img, output_path):
    # Function taken from: https://github.com/jojomondag/PNG_to_ico_to_icns_converter/blob/main/PNG_to_ico_to_icns_converter.py
    # Define the icon types and sizes
    icon_sizes = {
        'icp4': (16, 16),       # 16x16
        'icp5': (32, 32),       # 32x32
        'icp6': (64, 64),       # 64x64
        'ic07': (128, 128),     # 128x128
        'ic08': (256, 256),     # 256x256
        'ic09': (512, 512),     # 512x512
        'ic10': (1024, 1024),   # 1024x1024
    }

    icns_data = b''
    for icon_type, size in icon_sizes.items():
        # Use different interpolation methods depending on size
        if size[0] <= 32:  # For very small sizes, use NEAREST for crispness
            resized_img = img.resize(size, Image.NEAREST)
        else:  # For larger sizes, use LANCZOS for better quality
            resized_img = img.resize(size, Image.LANCZOS)

        # Save the image to PNG format in memory
        png_data_io = BytesIO()
        resized_img.save(png_data_io, format='PNG')
        png_data = png_data_io.getvalue()

        # Build the icon block
        icon_block = icon_type.encode('utf-8') + struct.pack('>I', len(png_data) + 8) + png_data
        icns_data += icon_block

    # ICNS header
    icns_header = b'icns' + struct.pack('>I', len(icns_data) + 8)
    with open(output_path, 'wb') as f:
        f.write(icns_header)
        f.write(icns_data)

def initialize_project(repo_path, project_name, version, 
                       welcome_image_path, header_image_path, icon_image_path,
                       ico_image_path, icns_image_path, 
                       github_owner):
    proyectname_lower = project_name.lower()

    conversion_dict = {
        "LOWER_PROJ_NAME": {
            "environment.yaml": proyectname_lower,
        },
        "UNDERSCORED_PROJECT_NAME": {
            "construct.yaml": project_name.replace(" ", "_"),
            "app/bash_bat_scripts/pre_uninstall.bat": project_name.replace(" ", "_"),
            "app/bash_bat_scripts/post_install.bat": project_name.replace(" ", "_"),
        },
        "PROJECT_NAME": {
            "construct.yaml": project_name,
            ".tools/templates/Welcome_template.ipynb": project_name,
            "app/menuinst/notebook_launcher.json": project_name,
            "app/bash_bat_scripts/post_install.bat": project_name,
            "app/bash_bat_scripts/post_install.sh": project_name,
            "app/bash_bat_scripts/pre_uninstall.bat": project_name,
            "app/bash_bat_scripts/pre_uninstall.sh": project_name,
            "app/bash_bat_scripts/uninstall.sh": project_name,
        },
        "VERSION_NUMBER": {
            "construct.yaml": version,
            "app/bash_bat_scripts/post_install.bat": version,
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
        }
    }

    # Replace placeholders in files
    for placeholder, files in conversion_dict.items():
        for file_path, replacement in files.items():
            replace_in_file(repo_path / file_path, placeholder, replacement)


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

def enqueue_pull_request(repo_url, personal_access_token, input_dict):
    
    github_owner, github_repo_name = repo_url.rstrip('/').split('/')[-2:]

    st.write(f"🌀 Creating pull request for {github_repo_name}...")

    # Download the GitHub repo, create a branch, add files, open a PR, etc.
    if "repo_path" in st.session_state and (st.session_state["repo_path"] / ".git").exists():
        st.write(f"✅ Git repo already cloned at {st.session_state['repo_path']}")
    else:
        st.session_state["repo_path"] = Path.cwd() / github_repo_name 
        
        if (st.session_state["repo_path"] / ".git").exists():
            st.write(f"🧹 Removing existing folder at {st.session_state['repo_path']}...")
            shutil.rmtree(st.session_state["repo_path"], onerror=handle_remove_error)

        st.write(f"🌀 Cloning Git repo to {st.session_state['repo_path']}...")

        try:
            run_git_command(
                ["clone", repo_url, str(st.session_state["repo_path"])],
                github_token=personal_access_token,
            )
        except RuntimeError as clone_error:
            raise RuntimeError(f"❌ Git clone failed: {clone_error}") from clone_error
        
        st.write(f"✅ Git repo cloned at {st.session_state['repo_path']}")

    st.write("🛠 Initializing project files...")

    logo_folder_path = st.session_state["repo_path"] / "app" / "logo"
    logo_folder_path.mkdir(parents=True, exist_ok=True)

    icon_path, ico_path, icns_path, welcome_path, headers_path = "", "", "", "", ""

    # Convert the uploaded icon PNg to ICO format and 
    if input_dict["icon_uploaded"]:
        icon_path = Path("app") / "logo" / input_dict["icon_uploaded"].name
        ico_path = Path("app") / "logo" / input_dict["icon_uploaded"].name.replace(".png", ".ico")
        icns_path = Path("app") / "logo" / input_dict["icon_uploaded"].name.replace(".png", ".icns")
        with open(st.session_state["repo_path"] / icon_path, "wb") as f:
            f.write(input_dict["icon_uploaded"].getbuffer())

        # Load the uploaded image
        ico_logo = Image.open(input_dict["icon_uploaded"])
        # Save as ICO
        ico_logo.save(st.session_state["repo_path"] / ico_path, 
                  format='ICO', sizes=[(16,16), (32,32), (64,64), (128,128), (256,256)])
        # Save as ICNS
        create_icns(ico_logo, st.session_state["repo_path"] / icns_path)

    # First move the uploaded files to the repo path under the app/logo
    if input_dict["welcome_uploaded"]:
        welcome_path = Path("app") / "logo" / input_dict["welcome_uploaded"].name
        with open(st.session_state["repo_path"] / welcome_path, "wb") as f:
            f.write(input_dict["welcome_uploaded"].getbuffer())
    if input_dict["headers_uploaded"]:
        headers_path = Path("app") / "logo" / input_dict["headers_uploaded"].name
        with open(st.session_state["repo_path"] / headers_path, "wb") as f:
            f.write(input_dict["headers_uploaded"].getbuffer())

    # Then initialize the project files by replacing placeholders
    initialize_project(
        repo_path=st.session_state["repo_path"],
        project_name=input_dict["project_name"],
        version=input_dict["project_version"],
        welcome_image_path=welcome_path,
        header_image_path=headers_path,
        icon_image_path=icon_path,
        ico_image_path=ico_path,
        icns_image_path=icns_path,
        github_owner=github_owner,
    )

    # Also, check if there is a README.md file and if so move it to the '.tools/docs' folder and create a new one with the project name
    readme_path = st.session_state["repo_path"] / "README.md"
    if readme_path.exists():
        docs_folder = st.session_state["repo_path"] / ".tools" / "docs"
        docs_folder.mkdir(parents=True, exist_ok=True)
        # Move the existing README.md to docs folder
        shutil.move(str(readme_path), str(docs_folder / "README.md"))
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"# {input_dict['project_name']}\n\n")
        f.write("This repository was initialized using LabConstrictor.\n")
        f.write("Please, feel free to customize this README file.\n")

    # Create a pull request using GitHub CLI
    pr_title = f"Add submission for {input_dict['project_name']}"
    pr_body = f"This PR adds the submission for the project {input_dict['project_name']} v{input_dict['project_version']}."
    
    push_and_create_pr(
        folder=st.session_state["repo_path"],
        branch_prefix="submission",
        commit_message=f"Add submission for {input_dict['project_name']}",
        pr_title=pr_title,
        pr_body=pr_body,
        github_repo_url=repo_url,
        github_token=personal_access_token,
        repo_path=st.session_state["repo_path"]
    )
    
    st.write(f"🧹 Cleaning the repo {st.session_state['repo_path']}.")
    shutil.rmtree(st.session_state["repo_path"], onerror=handle_remove_error)
    st.write(f"✅ Cleaned up the repo.")

    st.write("🏆 Finished!")

with st.sidebar:
    st.header("Submission tips")
    st.markdown(
        """
- Zip large folders before uploading.
- Pick the interpreter version that matches your `pyproject.toml` or `runtime.txt`.
- Keep uploads below 25 MB each to avoid browser time-outs.
        """
    )

st.title("LabConstrictor - Repository initializer")
st.caption("Once you have created a GitHub repository using the LabConstrictor template, you can use this form to initialize it with your project details.")
st.caption("Fill in the project name, version, and optionally upload images to customize your executable interface.")
st.caption("Then, provide your GitHub repository URL and a Personal Access Token to create a pull request with the configuration changes.")
st.caption("Once you submit the form, please follow the instructions described here: ...")

runtime_container = st.container()
with runtime_container:
    ##########################################################
    st.subheader("*Project basic info")
    project_name = st.text_input("Name of the project", placeholder="Cool Analytics API")
    project_version = st.text_input("Initial project version", placeholder="0.0.1", help="Specify the initial version of the project.")

    ##########################################################
    st.subheader("(Optional) Upload project images")
    uploaded_icon = st.file_uploader(
        "Project icon image (resized to 256 x 256 px)",
        accept_multiple_files=False,
        type="png",
        help=f"",
    )
    uploaded_welcome = st.file_uploader(
        "Project welcome image (resized to 164 x 314 px)",
        accept_multiple_files=False,
        type="png",
        help=f"",
    )
    uploaded_headers = st.file_uploader(
        "Project headers image (resized to 150 x 57 px)",
        accept_multiple_files=False,
        type="png",
        help=f"",
    )

    submitted = st.button("Validate submission", use_container_width=True)

if submitted:
    st.session_state["submitted_info"] = {
        "project_name": project_name,
        "project_version": project_version,
        "icon_uploaded": uploaded_icon,
        "welcome_uploaded": uploaded_welcome,
        "headers_uploaded": uploaded_headers,    
    }

    validation_errors = validate_submission(st.session_state["submitted_info"])
    if validation_errors:
        validation_error_list_text = ['\n - ' + e for e in validation_errors]
        st.error(f"Please fix the following before resubmitting: {''.join(validation_error_list_text)}")
        st.session_state["ready_for_pr"] = False
    else:
        st.success(
            f"Project '{project_name.strip()}' was submitted successfully!"
        )

if st.session_state.get("ready_for_pr"):
    st.subheader("Optional: GitHub follow-up")
    repo_url = st.text_input(
        "GitHub repository URL",
        key="github_repo_url",
        placeholder="https://github.com/org/repo",
        help="Paste the repository where the pull request should be opened.",
    )
    token = st.text_input("Personal Access Token", 
                          key="pat",
                          type="password",
                          help="Provide a GitHub Personal Access Token with repo permissions.",
                          )
    create_pr = st.button(
        "Create pull request",
        disabled=not repo_url.strip(),
    )

    if create_pr:
        with st.status("Creating pull request...", expanded=True) as status:
            enqueue_pull_request(repo_url.strip(), token.strip(), st.session_state["submitted_info"])
            # try:
            #     enqueue_pull_request(repo_url.strip(), token.strip(), st.session_state["submitted_info"])
            # except Exception as e:
            #     status.error(f"❌ Failed to create PR:\n{e}")
