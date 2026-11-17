"""The format the form accepts for each dependency of a notebook's requirements.yaml: one fixed version, `package==version`.

Kept apart from app.py (which builds the Streamlit page when it is imported) so that tests can check it.

Optional extras are allowed (`colabfold[alphafold,openmm]==1.6.3`): they choose optional parts of the same package and its
version stays fixed. The template's requirements merge combines the extras that several notebooks ask for.
"""

from __future__ import annotations

import re

NAME = r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?"
EXTRAS = rf"\[\s*{NAME}(?:\s*,\s*{NAME})*\s*\]"
PINNED_REQUIREMENT = re.compile(rf"^{NAME}(?:{EXTRAS})?==[A-Za-z0-9_.-]+$")


def is_pinned_requirement(dependency: str) -> bool:
    """Whether `dependency` is `package==version`, optionally with extras: `package[extra1,extra2]==version`."""
    return bool(PINNED_REQUIREMENT.match(dependency))


def format_error(dependency: object) -> str:
    return (
        f"Dependency '{dependency}' is not in the correct format. Only fixed versions are allowed: 'package==version', "
        "or 'package[extra1,extra2]==version' with optional extras."
    )
