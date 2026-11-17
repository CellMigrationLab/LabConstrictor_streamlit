"""Tests for requirements_format: the form accepts fixed versions, with or without extras, and nothing else."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requirements_format  # noqa: E402


class PinnedRequirementTests(unittest.TestCase):
    def test_fixed_versions_are_accepted(self) -> None:
        for dependency in ("numpy==2.0.2", "scikit-image==0.26.0", "zope.interface==7.2", "tifffile==2026.4.11", "a==1"):
            with self.subTest(dependency=dependency):
                self.assertTrue(requirements_format.is_pinned_requirement(dependency))

    def test_fixed_versions_with_extras_are_accepted(self) -> None:
        for dependency in ("colabfold[alphafold,openmm]==1.6.3", "dask[array]==2024.8.0", "colabfold[alphafold, openmm]==1.6.3",
                           "tensorflow[and-cuda]==2.20.0"):
            with self.subTest(dependency=dependency):
                self.assertTrue(requirements_format.is_pinned_requirement(dependency))

    def test_anything_else_is_refused(self) -> None:
        for dependency in ("numpy", "numpy>=2.0", "numpy<2", "numpy~=2.0", "numpy==2.*", "colabfold[]==1.6.3",
                           "colabfold[alphafold,]==1.6.3", "colabfold[alphafold==1.6.3", "colabfold[alphafold]", "colabfold[alphafold]>=1.6",
                           'numpy==2.0.2 ; sys_platform == "win32"', "git+https://github.com/x/y.git", "numpy==2.0.2 extra"):
            with self.subTest(dependency=dependency):
                self.assertFalse(requirements_format.is_pinned_requirement(dependency))

    def test_the_error_names_the_dependency_and_both_formats(self) -> None:
        message = requirements_format.format_error("numpy>=2.0")
        self.assertIn("'numpy>=2.0'", message)
        self.assertIn("'package==version'", message)
        self.assertIn("'package[extra1,extra2]==version'", message)


if __name__ == "__main__":
    unittest.main()
