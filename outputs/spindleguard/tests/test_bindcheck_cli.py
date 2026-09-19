# SPDX-License-Identifier: GPL-2.0-or-later
"""CLI: non-interactive flags, examples on error, no host /dev."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run_mod(*args: str, cwd=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [PYTHON, "-m", "bindcheck", *args],
        cwd=str(cwd or PROJECT),
        capture_output=True,
        text=True,
        env=env,
    )


class CliTests(unittest.TestCase):
    def test_help_exit_zero_and_lists_examples(self):
        result = run_mod("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scan", result.stdout)
        self.assertIn("bind", result.stdout)

    def test_subcommand_help_includes_example(self):
        result = run_mod("bind", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--manifest", result.stdout)

    def test_missing_subcommand(self):
        result = run_mod()
        self.assertEqual(result.returncode, 2)
        self.assertIn("python3 -m bindcheck scan --root .", result.stderr)

    def test_bind_missing_manifest_prints_example(self):
        result = run_mod("bind", "--path", "/dev/sda1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)
        self.assertIn("--manifest FILE", result.stderr)

    def test_bind_without_fixture_refuses_hardware_probe(self):
        result = run_mod("bind", "--manifest", "m.json", "--path", "/dev/sda1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("hardware probing is not enabled", result.stderr)

    def test_scan_clean_tree(self):
        result = run_mod("scan", "--root", str(PROJECT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STRUCTURAL_CANARY_assert_bound", result.stdout)

    def test_scan_json(self):
        result = run_mod("scan", "--root", str(PROJECT), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["canary"], "STRUCTURAL_CANARY_assert_bound")
        self.assertEqual(payload["violations"], [])

    def test_bind_fixture_success_and_skip_reason(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        manifest = {
            "serial": "SERIAL-A",
            "partuuid": "PART-A",
            "fs_uuid": "FS-A",
            "media_class": "failing",
        }
        fixture = {
            "blocks": [
                {
                    "path": "/dev/sda1",
                    "serial": "SERIAL-A",
                    "partuuid": "PART-A",
                    "fs_uuid": "FS-A",
                    "major": 8,
                    "minor": 1,
                    "ro": True,
                }
            ]
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / "fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
        result = run_mod(
            "bind",
            "--manifest",
            str(root / "manifest.json"),
            "--path",
            "/dev/sda1",
            "--fixture",
            str(root / "fixture.json"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fingerprint skipped: media_class=failing", result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["fingerprint_skipped"])
        self.assertEqual(payload["fingerprint_skip_reason"], "media_class=failing")
        self.assertNotIn("path", payload)

    def test_bind_usb_bridge_prints_warning(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        manifest = {
            "serial": "SERIAL-A",
            "partuuid": "PART-A",
            "fs_uuid": "FS-A",
            "allow_fingerprint": True,
            "media_class": "stable",
        }
        fixture = {
            "blocks": [
                {
                    "path": "/dev/sda1",
                    "serial": "SERIAL-A",
                    "partuuid": "PART-A",
                    "fs_uuid": "FS-A",
                    "major": 8,
                    "minor": 1,
                    "ro": True,
                    "usb_bridge": True,
                }
            ]
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / "fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
        result = run_mod(
            "bind",
            "--manifest",
            str(root / "manifest.json"),
            "--path",
            "/dev/sda1",
            "--fixture",
            str(root / "fixture.json"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usb bridge can hide sibling LUNs", result.stderr)

    def test_rotate_dry_run_writes_nothing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        old = {
            "generation": 1,
            "serial": "SERIAL-A",
            "partuuid": "PART-A",
            "fs_uuid": "FS-A",
        }
        observed = dict(old, partuuid="PART-B")
        (root / "old.json").write_text(json.dumps(old), encoding="utf-8")
        (root / "new.json").write_text(json.dumps(observed), encoding="utf-8")
        out = root / "out.json"
        audit = root / "audit.jsonl"
        result = run_mod(
            "rotate-manifest",
            "--old",
            str(root / "old.json"),
            "--observed",
            str(root / "new.json"),
            "--reason",
            "repartitioned",
            "--out",
            str(out),
            "--audit",
            str(audit),
            "--dry-run",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(out.exists())
        self.assertFalse(audit.exists())
        payload = json.loads(result.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["fields_changed"], ["partuuid"])

    def test_rotate_missing_reason_example(self):
        result = run_mod("rotate-manifest", "--old", "a.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--reason TEXT", result.stderr)


if __name__ == "__main__":
    unittest.main()
