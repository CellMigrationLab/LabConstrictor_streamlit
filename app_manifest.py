"""Create labconstrictor-app.yaml: the description of an app that the LabConstrictor App Centre reads.

The repository initialiser asks for a summary, a kind and the software the app works in, fills in
what it already knows (name, installers, icon) and writes the file as part of the initialisation pull
request, so the author reviews it before merging. Everything is checked against the schema in
schemas/ before it is written; nothing is guessed or defaulted silently.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

MANIFEST_NAME = "labconstrictor-app.yaml"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "labconstrictor-app.schema.json"
SCHEMA_URL = "https://labconstrictor.cellmig.org/schema/labconstrictor-app.schema.json"
KINDS = {"Analysis": "analysis", "Segmentation": "segmentation", "Simulation": "simulation",
         "Game": "game", "Training": "training", "Utility": "utility"}
HOSTS = ("notebook", "napari", "fiji", "qupath")


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    """The manifest schema shipped with this app (raises FileNotFoundError or ValueError if it is missing or broken)."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def build_manifest(name: str, summary: str, kind_label: str, hosts: list[str],
                   description: str, icon_path: str | None) -> dict[str, Any]:
    """The manifest as a dict. `kind_label` is a key of KINDS. Optional parts (description, hosts, icon) are
    left out when empty. Installers are always declared: the template builds them on every release."""
    manifest: dict[str, Any] = {"schema": 1, "name": name.strip(), "summary": summary.strip()}
    if description.strip():
        manifest["description"] = description.strip()
    manifest["kind"] = KINDS[kind_label]
    if hosts:
        manifest["hosts"] = list(hosts)
    manifest["distribution"] = {"installer": True}
    if icon_path:
        manifest["icon"] = icon_path
    return manifest


def icon_manifest_path(icon_file_name: str | None) -> str | None:
    """Where the initialiser stores an uploaded icon in the repository (app/logo/<file>), or None without an icon."""
    return f"app/logo/{icon_file_name}" if icon_file_name else None


def schema_errors(manifest: dict[str, Any]) -> list[str]:
    """Plain-language problems of a manifest ("summary: 'x' is too short"); empty when it is valid."""
    validator = Draft202012Validator(load_schema())
    found = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or 'manifest'}: {e.message}" for e in found]


def _literal_for_paragraphs(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    """Write multi-line text as a readable block ("|-") instead of one quoted line."""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


class _Dumper(yaml.SafeDumper):
    """YAML writer that keeps paragraphs readable."""


_Dumper.add_representer(str, _literal_for_paragraphs)


def render(manifest: dict[str, Any]) -> str:
    """The text of labconstrictor-app.yaml, starting with the schema comment that gives editors validation.
    Raises ValueError listing every schema problem, so an invalid file is never written."""
    errors = schema_errors(manifest)
    if errors:
        raise ValueError("labconstrictor-app.yaml would be invalid: " + "; ".join(errors))
    body = yaml.dump(manifest, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)
    return f"# yaml-language-server: $schema={SCHEMA_URL}\n{body}"
