"""Minimal Streamlit form to capture a project name, Python version, and uploaded files."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import base64
import os
import streamlit as st
import subprocess
import requests

st.set_page_config(page_title="Python Project Intake", layout="centered")

PYTHON_VERSIONS = ["3.13", "3.12", "3.11", "3.10", "3.9", "3.8"]
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
        project_version = "0.0.1"
    python_version = submitted_info.get("python_version", "").strip()
    if python_version not in PYTHON_VERSIONS:
        errors.append("Please select a valid Python version.")

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
        st.write(f"✅ repo path: {repo_path} with elements: {list(Path(repo_path).iterdir())}")
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

def enqueue_pull_request(repo_url: str, personal_access_token:str, 
                         input_dict: dict) -> None:
    
    st.write(f"🌀 Creating pull request for '{project}'...")

    github_owner, github_repo_name = repo_url.rstrip('/').split('/')[-2:]

    # Download the GitHub repo, create a branch, add files, open a PR, etc.
    if "repo_path" in st.session_state and (st.session_state["repo_path"] / ".git").exists():
        st.write(f"✅ Git repo already cloned at {st.session_state['repo_path']}")
    else:
        st.session_state["repo_path"] = Path.cwd() / github_repo_name 
        
        if st.session_state["repo_path"].exists():
            st.write(f"🧹 Removing existing folder at {st.session_state['repo_path']}...")
            subprocess.run(["rm", "-rf", str(st.session_state["repo_path"])])

        st.write(f"🌀 Cloning Git repo to {st.session_state['repo_path']}...")

        try:
            run_git_command(
                ["clone", repo_url, str(st.session_state["repo_path"])],
                github_token=personal_access_token,
            )
        except RuntimeError as clone_error:
            raise RuntimeError(f"❌ Git clone failed: {clone_error}") from clone_error
        
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
    
    st.write(f"🧹 Cleaning the repo {st.session_state['repo_path']}.")
    subprocess.run(["rm", "-rf", str(st.session_state["repo_path"])])
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

st.title("Python Project Intake Form")
st.caption(
    "Share the name of your project, tell us which Python version it targets, "
    "and attach any relevant files (source code, requirements, docs, etc.)."
)

with st.form("project_form", clear_on_submit=False):
    project_name = st.text_input("*Name of the project", placeholder="Cool Analytics API")
    project_version = st.text_input("*Initial project version", placeholder="0.0.1", help="Specify the initial version of the project.")
    python_col, jupyterlab_col, notebook_col, matplotlib_col = st.columns(4, gap="small")  # or st.columns([2,1,1])
    with python_col:
        python_version = st.selectbox("*Python version", PYTHON_VERSIONS, index=1)
    with jupyterlab_col:
        jupyterlab_version = st.checkbox("Includes JupyterLab", value=False, help="Check if the project includes JupyterLab components.")
    with notebook_col:
        notebook_version = st.checkbox("Includes Notebooks", value=False, help="Check if the project includes Jupyter Notebooks.")
    with matplotlib_col:
        matplotlib_version = st.checkbox("Uses Matplotlib", value=False, help="Check if the project uses Matplotlib for plotting.")
    
    uploaded_icon = st.file_uploader(
        "(Optional) Upload project icon image",
        accept_multiple_files=False,
        type="png",
        help=f"",
    )
    uploaded_welcome = st.file_uploader(
        "(Optional) Upload project welcome image",
        accept_multiple_files=False,
        type="png",
        help=f"",
    )
    uploaded_headers = st.file_uploader(
        "(Optional) Upload project headers image",
        accept_multiple_files=False,
        type="png",
        help=f"",
    )
    submitted = st.form_submit_button("Validate submission", use_container_width=True)


if submitted:
    submitted_info = {
        "project_name": project_name,
        "project_version": project_version,
        "python_version": python_version,
        "jupyterlab_included": jupyterlab_version,
        "notebook_included": notebook_version,
        "matplotlib_used": matplotlib_version,
        "icon_uploaded": uploaded_icon.name if uploaded_icon else None,
        "welcome_uploaded": uploaded_welcome.name if uploaded_welcome else None,
        "headers_uploaded": uploaded_headers.name if uploaded_headers else None,    
    }

    validation_errors = validate_submission(submitted_info)
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
            try:
                enqueue_pull_request(repo_url.strip(), token.strip(), submitted_info)
            except Exception as e:
                status.error(f"❌ Failed to create PR:\n{e}")
