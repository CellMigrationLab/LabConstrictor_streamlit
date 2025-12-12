"""Minimal Streamlit form to capture a project name, Python version, and uploaded files."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List
import streamlit as st
import subprocess
import requests
import tempfile

st.set_page_config(page_title="Python Project Intake", layout="centered")

PYTHON_VERSIONS = ["3.13", "3.12", "3.11", "3.10", "3.9", "3.8"]
MAX_FILE_SIZE_MB = 25

if "ready_for_pr" not in st.session_state:
    st.session_state["ready_for_pr"] = False
if "github_repo_url" not in st.session_state:
    st.session_state["github_repo_url"] = ""


def validate_submission(project_name: str, uploads: List) -> List[str]:
    """Ensure required inputs exist and meet basic quality checks."""
    errors: List[str] = []
    if not project_name.strip():
        errors.append("Please enter the name of the project.")
    if not uploads:
        errors.append("Upload at least one file so we can inspect the project.")
    else:
        oversized = [
            upload.name
            for upload in uploads
            if upload.size > MAX_FILE_SIZE_MB * 1024 * 1024
        ]
        if oversized:
            joined = ", ".join(oversized)
            errors.append(
                f"The following files are larger than {MAX_FILE_SIZE_MB} MB: {joined}."
            )
    return errors


def project_progress(name: str, version: str, uploads: List) -> int:
    """Compute how many of the required inputs have been filled out."""
    checks = [
        bool(name.strip()),
        bool(version),
        bool(uploads),
    ]
    return int((sum(checks) / len(checks)) * 100)


def python_version_hint(version: str) -> str:
    """Return feedback copy based on the selected Python version."""
    major, minor = (int(part) for part in version.split("."))
    if (major, minor) < (3, 10):
        return (
            "Python versions earlier than 3.10 only receive security fixes. "
            "Consider upgrading soon."
        )
    if (major, minor) >= (3, 12):
        return "Great pick! Python 3.12+ includes the latest performance gains."
    return ""

def log_submission(name: str, version: str, uploads: List) -> None:
    """Placeholder hook that currently just prints submitted values."""
    file_names = [upload.name for upload in uploads] if uploads else []
    print(f"[submission] project={name!r}, python={version}, files={file_names}")

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

def run_git_command(args, cwd):
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
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
        run_git_command(["pull", "origin", "main"], cwd=repo_path)

        if not has_changes_to_commit(folder, cwd=repo_path):
            st.write(f"ℹ️ No changes detected in `{folder}`. Nothing to push.")
            return None
        else:
            st.write(f"✅ Changes detected!")

        run_git_command(["checkout", "-b", new_branch], cwd=repo_path)
        run_git_command(["add", folder], cwd=repo_path)
        run_git_command(["commit", "-m", commit_message], cwd=repo_path)
        run_git_command(["push", "--set-upstream", "origin", new_branch], cwd=repo_path)

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

def enqueue_pull_request(repo_url: str, personal_access_token:str, 
                         input_dict: dict) -> None:
    
    st.write(f"🌀 Creating pull request for '{project}'...")

    github_owner, github_repo_name = repo_url.rstrip('/').split('/')[-2:]

    # Download the GitHub repo, create a branch, add files, open a PR, etc.
    if "repo_path" in st.session_state and (st.session_state["repo_path"] / ".git").exists():
        st.write(f"✅ Git repo already cloned at {st.session_state['repo_path']}")
    else:
        st.session_state["repo_path"] = Path.cwd() / github_repo_name # Path(tempfile.mkdtemp(prefix="project-intake-"))
        
        st.write(f"🌀 Cloning Git repo to {st.session_state['repo_path']}...")

        result = subprocess.run(["git", "clone", repo_url, st.session_state["repo_path"]], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"❌ Git clone failed: {result.stderr.strip()}")
        
        st.write(f"✅ Git repo cloned at {st.session_state['repo_path']}")

    # Create a test text file to simulate adding files
    test_file_path = st.session_state["repo_path"] / "README.md"
    with open(test_file_path, "w") as f:
        f.write(f"Project: {input_dict['project']}\n")
        f.write(f"Python Version: {input_dict['version']}\n")
        f.write(f"Files: {', '.join(input_dict['files'])}\n")

    st.write(f"✅ Created test file at {test_file_path}")
  
    # Create a pull request using GitHub CLI
    pr_title = f"Add submission for {input_dict['project']}"
    pr_body = f"This PR adds the submission for the project {input_dict['project']} targeting Python {input_dict['version']}."
    
    push_and_create_pr(
        folder=st.session_state["repo_path"],
        branch_prefix="submission",
        commit_message=f"Add submission for {input_dict['project']}",
        pr_title=pr_title,
        pr_body=pr_body,
        github_repo_url=repo_url,
        github_token=personal_access_token,
        repo_path=st.session_state["repo_path"]
    )

with st.sidebar:
    st.header("Submission tips")
    st.markdown(
        """
- Zip large folders before uploading.
- Pick the interpreter version that matches your `pyproject.toml` or `runtime.txt`.
- Keep uploads below 25 MB each to avoid browser time-outs.
        """
    )

st.title("Python Project Intake Form")
st.caption(
    "Share the name of your project, tell us which Python version it targets, "
    "and attach any relevant files (source code, requirements, docs, etc.)."
)

with st.form("project_form", clear_on_submit=False):
    project_name = st.text_input("Name of the project", placeholder="Cool Analytics API")
    python_version = st.selectbox("Python version", PYTHON_VERSIONS, index=1)
    uploaded_files = st.file_uploader(
        "Upload project files",
        accept_multiple_files=True,
        type=None,
        help=f"Individual files must be smaller than {MAX_FILE_SIZE_MB} MB.",
    )
    submitted = st.form_submit_button("Validate submission", use_container_width=True)

progress = project_progress(project_name, python_version, uploaded_files)
st.progress(progress / 100, text=f"{progress}% of required information captured")

version_message = python_version_hint(python_version)
if version_message:
    st.info(version_message)

if submitted:
    validation_errors = validate_submission(project_name, uploaded_files)
    if validation_errors:
        st.error("Please fix the following before resubmitting:")
        for item in validation_errors:
            st.write(f"- {item}")
        st.session_state["ready_for_pr"] = False
    else:
        st.success(
            f"Project '{project_name.strip()}' targeting Python {python_version} "
            "was submitted successfully!"
        )
        log_submission(project_name, python_version, uploaded_files)
        st.session_state["ready_for_pr"] = True
        st.session_state["last_project_name"] = project_name.strip()
        st.session_state["last_python_version"] = python_version
        st.session_state["last_file_names"] = [
            upload.name for upload in uploaded_files
        ]
        total_size_mb = (
            sum(upload.size for upload in uploaded_files) / (1024 * 1024)
            if uploaded_files
            else 0
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
        project = st.session_state.get("last_project_name", project_name)
        version = st.session_state.get("last_python_version", python_version)
        files = st.session_state.get("last_file_names", [])
        
        with st.status("Creating pull request...", expanded=True) as status:
            try:
                enqueue_pull_request(repo_url.strip(), token.strip(),
                                    {"project": project, "version": version, "files": files})
            except Exception as e:
                status.error(f"❌ Failed to create PR:\n{e}")