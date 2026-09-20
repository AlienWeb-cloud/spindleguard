# SPDX-License-Identifier: GPL-2.0-or-later
"""The Mac app sources exist, refuse /Volumes, and make app fails on non-macOS."""
from __future__ import annotations

import os
import plistlib
import subprocess
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MACOS = PROJECT / "macos"


class AppBundleTests(unittest.TestCase):
    def test_swift_sources_present(self):
        for name in (
            "SpindleGuardApp.swift",
            "AppState.swift",
            "PathPolicy.swift",
            "SGPaths.swift",
            "BrokerService.swift",
            "ContentView.swift",
            "Panes.swift",
        ):
            self.assertTrue((MACOS / name).is_file(), name)

    def test_swift_policy_strings_match_python(self):
        text = (MACOS / "PathPolicy.swift").read_text(encoding="utf-8")
        self.assertIn("Prototype refuses /Volumes paths. Use disposable directories.", text)
        self.assertIn("Prototype refuses /dev paths. Use disposable directories.", text)
        self.assertIn("Source and mount must be disjoint.", text)
        self.assertIn("Missing disposable test root marker.", text)
        self.assertIn(".spindleguard-test-root", text)

    def test_app_wires_every_control(self):
        state = (MACOS / "AppState.swift").read_text(encoding="utf-8")
        for needle in (
            "func start()",
            "func stop()",
            "func newSession()",
            "func probeQueue()",
            "func scanTree()",
            "func bindIdentity()",
            "func rotateManifest()",
            "func runTopology()",
            "func refreshDoctor()",
            "func openMount()",
        ):
            self.assertIn(needle, state)
        panes = (MACOS / "Panes.swift").read_text(encoding="utf-8")
        self.assertIn("Bind identity", panes)
        self.assertIn("Resolve source topology", panes)
        self.assertIn("Probe concurrent reads", panes)
        app = (MACOS / "SpindleGuardApp.swift").read_text(encoding="utf-8")
        self.assertIn('Button("Start")', app)
        self.assertIn('Button("Stop")', app)

    def test_info_plist(self):
        info = plistlib.loads((MACOS / "Info.plist").read_bytes())
        self.assertEqual(info["CFBundleIdentifier"], "cloud.alienweb.spindleguard")
        self.assertEqual(info["CFBundleExecutable"], "SpindleGuard")
        self.assertEqual(info["LSMinimumSystemVersion"], "13.0")
        self.assertFalse(info["NSSupportsAutomaticTermination"])

    def test_make_app_requires_macos(self):
        makefile = (PROJECT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("requires macOS", makefile)
        if os.uname().sysname == "Darwin":
            return
        result = subprocess.run(
            ["make", "app"],
            cwd=str(PROJECT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn("requires macOS", combined)
        self.assertIn("make app", combined)

    def test_makefile_does_not_delete_bundle(self):
        makefile = (PROJECT / "Makefile").read_text(encoding="utf-8")
        self.assertNotIn("rm -rf $(APP)", makefile)
        self.assertNotIn("rm -rf SpindleGuard.app", makefile)


if __name__ == "__main__":
    unittest.main()
