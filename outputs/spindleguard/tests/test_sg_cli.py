# SPDX-License-Identifier: GPL-2.0-or-later
"""sg CLI: non-interactive, examples on error, no host /dev."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SG = PROJECT / "sg"
PYTHON = sys.executable


def run_sg(*args: str, cwd=None):
    return subprocess.run(
        [PYTHON, str(SG), *args],
        cwd=str(cwd or PROJECT),
        capture_output=True,
        text=True,
    )


class SgCliTests(unittest.TestCase):
    def test_help(self):
        result = run_sg("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("doctor", result.stdout)
        self.assertIn("session-create", result.stdout)

    def test_missing_subcommand_example(self):
        result = run_sg()
        self.assertEqual(result.returncode, 2)
        self.assertIn("./sg doctor --json", result.stderr)

    def test_doctor_json(self):
        result = run_sg("doctor", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("can_mount", payload)
        self.assertIn("problems", payload)
        self.assertFalse(payload["can_mount"])

    def test_session_create_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_sg("session-create", "--parent", tmp, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            rec = json.loads(result.stdout)
            checked = run_sg(
                "policy-check",
                "--source",
                rec["source"],
                "--mount",
                rec["mount"],
                "--write-prefix",
                "/Workspace",
                "--json",
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            dry = run_sg(
                "start",
                "--dry-run",
                "--binary",
                "/helper/spindleguard",
                "--source",
                rec["source"],
                "--mount",
                rec["mount"],
                "--write-prefix",
                "/Workspace",
                "--delay-ms",
                "150",
                "--json",
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            argv = json.loads(dry.stdout)["cmd"]
            self.assertEqual(argv[0], "/helper/spindleguard")
            self.assertEqual(argv[3], "/Workspace")
            self.assertEqual(argv[4], "150")

    def test_policy_volumes(self):
        result = run_sg("policy-check", "--source", "/Volumes/x", "--mount", "/tmp/m")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Prototype refuses /Volumes paths", result.stderr)

    def test_topology_refuses_volumes_without_diskutil(self):
        result = run_sg("topology", "--path", "/Volumes/exhibit")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Prototype refuses /Volumes paths", result.stderr)

    def test_topology_refuses_dev(self):
        result = run_sg("topology", "--path", "/dev/disk0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Prototype refuses /dev paths", result.stderr)

    def test_scan(self):
        result = run_sg("scan", "--root", str(PROJECT), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["violations"], [])

    def test_bind_example_fixture(self):
        result = run_sg(
            "bind",
            "--manifest",
            str(PROJECT / "macos/Resources/example-manifest.json"),
            "--path",
            "/dev/sda1",
            "--fixture",
            str(PROJECT / "macos/Resources/example-fixture.json"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["fingerprint_skipped"])
        self.assertNotIn("path", payload)

    def test_bind_failing_skip_reason(self):
        result = run_sg(
            "bind",
            "--manifest",
            str(PROJECT / "macos/Resources/example-failing-manifest.json"),
            "--path",
            "/dev/sda1",
            "--fixture",
            str(PROJECT / "macos/Resources/example-fixture.json"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fingerprint skipped: media_class=failing", result.stderr)

    def test_probe_log(self):
        payload = json.loads((PROJECT / "queue-proof.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "broker.jsonl"
            log.write_text(
                "\n".join(json.dumps(e) for e in payload["events"]) + "\n", encoding="utf-8"
            )
            result = run_sg("probe-log", "--log", str(log), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            body = json.loads(result.stdout)
            self.assertGreater(body["competing"]["wait_ms"], 20)

    def test_app_dry_run(self):
        result = run_sg("app", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["darwin"])
        self.assertIn("make app", payload["hint"])

    def test_start_without_source_example(self):
        result = run_sg("start")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--source DIR", result.stderr)


if __name__ == "__main__":
    unittest.main()
