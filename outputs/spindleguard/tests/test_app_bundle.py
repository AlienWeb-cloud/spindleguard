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
            "func loadSession()",
            "func probeQueue()",
            "func scanTree()",
            "func bindIdentity()",
            "func rotateManifest()",
            "func runTopology()",
            "func refreshDoctor()",
            "func openMount()",
            "func previewSetup()",
            "func runSetup()",
            "func installFuse()",
            "func verifyInstall()",
            "func unmountOnly()",
            "func policyCheck()",
            "func previewStart()",
            "func copyFuseCommand()",
            "func openFuseDocs()",
            "func listSessions()",
            "func showMainWindow()",
        ):
            self.assertIn(needle, state)
        self.assertIn('["setup", "--json"]', state)
        self.assertIn('["setup", "--dry-run", "--json"]', state)
        self.assertNotIn(
            'runSG(arguments: ["setup", "--dry-run", "--json"])',
            state.split("func runSetup")[1][:400] if "func runSetup" in state else "",
        )
        panes = (MACOS / "Panes.swift").read_text(encoding="utf-8")
        self.assertIn("struct SetupPane", panes)
        self.assertIn("struct RetainPane", panes)
        self.assertIn("There is no deletion bucket", panes)
        self.assertIn("Run setup", panes)
        self.assertIn("Verify install", panes)
        self.assertIn("Copy FUSE-T command", panes)
        self.assertIn("Bind identity", panes)
        self.assertIn("Resolve source topology", panes)
        self.assertIn("Probe concurrent reads", panes)
        self.assertIn("Policy check", panes)
        self.assertIn("Preview start", panes)
        content = (MACOS / "ContentView.swift").read_text(encoding="utf-8")
        self.assertIn("case .setup: SetupPane()", content)
        self.assertIn("case .retain: RetainPane()", content)
        self.assertIn('Button("Verify Install"', content)
        app = (MACOS / "SpindleGuardApp.swift").read_text(encoding="utf-8")
        self.assertIn('Button("Start")', app)
        self.assertIn('Button("Stop")', app)
        self.assertIn('CommandMenu("Setup")', app)
        self.assertIn("MenuBarExtra", app)
        self.assertIn('systemImage: "externaldrive"', app)
        self.assertIn("import UniformTypeIdentifiers", state)
        self.assertIn("sessionParent()", (MACOS / "SGPaths.swift").read_text(encoding="utf-8"))
        self.assertIn("func unmount(mount: String)", (MACOS / "BrokerService.swift").read_text(encoding="utf-8"))

    def test_preview_html_mirrors_native_chrome(self):
        page = (MACOS / "preview.html").read_text(encoding="utf-8")
        self.assertIn("SpindleGuard", page)
        self.assertIn("There is no deletion bucket", page)
        self.assertIn('id="extraBtn"', page)
        self.assertIn("New Session", page)
        self.assertIn("Retain", page)
        info = plistlib.loads((MACOS / "Info.plist").read_bytes())
        self.assertEqual(info["CFBundleIdentifier"], "cloud.alienweb.spindleguard")
        self.assertEqual(info["CFBundleExecutable"], "SpindleGuard")
        self.assertEqual(info["LSMinimumSystemVersion"], "13.0")
        self.assertEqual(info["CFBundleShortVersionString"], "0.5")
        self.assertEqual(info["CFBundleVersion"], "5")
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
        self.assertNotIn("app: all", makefile)
        self.assertIn("UniformTypeIdentifiers", makefile)
        self.assertIn("python3 -B ./sg setup", makefile)
        self.assertIn("python3 -B ./sg verify --quick", makefile)
        self.assertIn("verify --full", makefile)
        self.assertIn("macos/preview.html", makefile)


if __name__ == "__main__":
    unittest.main()
