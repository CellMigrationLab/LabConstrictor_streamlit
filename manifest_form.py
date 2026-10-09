"""The App Centre part of the repository initialiser: form fields, validation and writing labconstrictor-app.yaml.

app.py only calls the functions here, so the manifest logic stays out of its long form code. The pure
file-building logic is in app_manifest.py. Nothing in this module guesses a missing value: when the
author asked for a description file, every field is present and checked against the schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import streamlit as st

import app_manifest

FIELDS = ("describe_app", "app_summary", "app_kind", "app_hosts", "app_description")


def _text_fields(on_change: Callable[[], None]) -> dict[str, Any]:
    """The summary, kind, hosts and description inputs; returns their values by field name."""
    summary = st.text_input("One-sentence summary", placeholder="Count and track cells in time-lapse movies.",
                            help="Shown on your app's card. Plain text, 20 to 200 characters.", on_change=on_change)
    kind = st.selectbox("Kind of app", list(app_manifest.KINDS), on_change=on_change)
    hosts = st.multiselect("Also works in", list(app_manifest.HOSTS), default=["notebook"],
                           help="Where the tools of your app can run besides its own window.", on_change=on_change)
    description = st.text_area("Longer description (optional)", on_change=on_change,
                               help="A few plain-text paragraphs; separate paragraphs with a blank line. No HTML or Markdown.")
    return {"app_summary": summary, "app_kind": kind, "app_hosts": hosts, "app_description": description}


def render_fields(on_change: Callable[[], None]) -> dict[str, Any]:
    """Show the "Describe your app" section. Returns the values for every name in FIELDS
    (the text fields are empty strings or lists when the author declines the description)."""
    st.subheader("Describe your app (recommended)")
    describe = st.checkbox("Add a description file for the LabConstrictor App Centre", value=True, on_change=on_change,
                           help="Creates labconstrictor-app.yaml in your repository. You can review and edit it in the pull request.")
    values: dict[str, Any] = {"app_summary": "", "app_kind": "", "app_hosts": [], "app_description": ""}
    if describe:
        values = _text_fields(on_change)
    return {"describe_app": describe, **values}


def _manifest(info: dict[str, Any], project_name: str, icon_file_name: str | None) -> dict[str, Any]:
    """The manifest for submitted form values (raises KeyError if a field is missing: the form always sets all of them)."""
    return app_manifest.build_manifest(project_name, info["app_summary"], info["app_kind"], info["app_hosts"],
                                       info["app_description"], app_manifest.icon_manifest_path(icon_file_name))


def submission_errors(info: dict[str, Any], uploaded_icon: Any) -> list[str]:
    """Problems with the description fields, in plain language; empty when the author declined the description
    or everything is valid. The project name has its own checks, so its message is not repeated here."""
    if not info["describe_app"]:
        return []
    manifest = _manifest(info, info["project_name"].strip(), uploaded_icon.name if uploaded_icon else None)
    return [e for e in app_manifest.schema_errors(manifest) if not e.startswith("name:")]


def write_manifest(repo_path: Path, info: dict[str, Any], icon_path: Path | str) -> None:
    """Write labconstrictor-app.yaml into the cloned repository when the author asked for it. `icon_path` is the
    path the initialiser stored the icon at, or an empty value when no icon was uploaded."""
    if not info["describe_app"]:
        return
    icon_name = Path(icon_path).name if icon_path else None
    text = app_manifest.render(_manifest(info, info["project_name"].strip(), icon_name))
    (repo_path / app_manifest.MANIFEST_NAME).write_text(text, encoding="utf-8")


def pr_note(info: dict[str, Any]) -> str:
    """The sentence added to the pull request description (empty when no file was written)."""
    if not info["describe_app"]:
        return ""
    return (f"\n\nIt also adds `{app_manifest.MANIFEST_NAME}`, the description the LabConstrictor App Centre reads. "
            "Please review the summary, kind and description, and edit them if needed.")
