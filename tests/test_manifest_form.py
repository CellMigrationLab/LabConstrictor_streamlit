"""Tests for manifest_form: validation of the form values and writing of the file."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manifest_form as mf  # noqa: E402

INFO = {"project_name": "Cool Analytics", "describe_app": True, "app_summary": "Count and track cells in time-lapse movies.",
        "app_kind": "Analysis", "app_hosts": ["notebook", "napari"], "app_description": ""}


class SubmissionTests(unittest.TestCase):
    def test_valid_values_have_no_errors(self) -> None:
        self.assertEqual(mf.submission_errors(INFO, None), [])

    def test_declining_the_description_skips_every_check(self) -> None:
        info = {**INFO, "describe_app": False, "app_summary": "", "app_kind": "", "app_hosts": []}
        self.assertEqual(mf.submission_errors(info, None), [])

    def test_an_icon_name_the_manifest_cannot_hold_is_reported(self) -> None:
        errors = mf.submission_errors(INFO, SimpleNamespace(name="icon (1).png"))
        self.assertTrue(any(e.startswith("icon") for e in errors), errors)

    def test_a_missing_field_raises_instead_of_being_defaulted(self) -> None:
        info = {k: v for k, v in INFO.items() if k != "app_kind"}
        with self.assertRaises(KeyError):
            mf.submission_errors(info, None)


class WriteTests(unittest.TestCase):
    def test_the_file_is_written_with_the_icon_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mf.write_manifest(Path(tmp), INFO, Path("app") / "logo" / "icon.png")
            data = yaml.safe_load((Path(tmp) / "labconstrictor-app.yaml").read_text(encoding="utf-8"))
        self.assertEqual((data["name"], data["kind"], data["icon"]), ("Cool Analytics", "analysis", "app/logo/icon.png"))

    def test_nothing_is_written_when_declined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mf.write_manifest(Path(tmp), {**INFO, "describe_app": False}, "")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_the_pull_request_note_only_appears_with_a_file(self) -> None:
        self.assertIn("labconstrictor-app.yaml", mf.pr_note(INFO))
        self.assertEqual(mf.pr_note({**INFO, "describe_app": False}), "")


if __name__ == "__main__":
    unittest.main()
