"""Tests for app_manifest: what is written, and that invalid input is refused."""

import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app_manifest as am  # noqa: E402

SUMMARY = "Count and track cells in time-lapse movies."


class ManifestTests(unittest.TestCase):
    def build(self, **overrides):
        args = dict(name="Cool Analytics", summary=SUMMARY, kind_label="Analysis", hosts=["notebook"], description="", icon_path=None)
        return am.build_manifest(**{**args, **overrides})

    def test_a_valid_manifest_round_trips(self) -> None:
        text = am.render(self.build(description="First paragraph.\n\nSecond paragraph.", icon_path="app/logo/icon.png"))
        self.assertTrue(text.startswith("# yaml-language-server: $schema=https://labconstrictor.cellmig.org/"))
        data = yaml.safe_load(text)
        self.assertEqual(data["kind"], "analysis")
        self.assertEqual(data["distribution"], {"installer": True})
        self.assertEqual(data["description"], "First paragraph.\n\nSecond paragraph.")
        self.assertEqual(data["icon"], "app/logo/icon.png")

    def test_optional_parts_are_left_out_when_empty(self) -> None:
        data = yaml.safe_load(am.render(self.build(hosts=[])))
        for key in ("description", "hosts", "icon"):
            self.assertNotIn(key, data)

    def test_a_short_summary_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            am.render(self.build(summary="Too short"))
        self.assertIn("summary", str(caught.exception))

    def test_an_icon_that_is_not_a_png_or_jpeg_is_refused(self) -> None:
        self.assertTrue(am.schema_errors(self.build(icon_path="app/logo/icon.svg")))

    def test_every_kind_label_gives_a_valid_kind(self) -> None:
        for label in am.KINDS:
            self.assertEqual(am.schema_errors(self.build(kind_label=label)), [])

    def test_unknown_kind_label_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.build(kind_label="Magic")


if __name__ == "__main__":
    unittest.main()
