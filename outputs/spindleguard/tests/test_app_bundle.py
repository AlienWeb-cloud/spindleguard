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
            "Wizard.swift",
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
            "func openWizard()",
            "func finishWizard(skipped: Bool)",
            "func maybePresentWizard()",
            "func revealPane(_ pane: Pane)",
            "func openSessionParent()",
            "func bucketSession(_ row: SessionInfo)",
            "func restoreSession(_ row: SessionInfo)",
            "func purgeSession(_ row: SessionInfo)",
            "func purgeBucket()",
            "func destroySession(_ row: SessionInfo)",
            "func destroyPurged()",
            "func bucketCurrentSession()",
        ):
            self.assertIn(needle, state)
        self.assertIn('wizardKey = "SGWizardFinished"', state)
        self.assertIn("wizardStepCount = 6", state)
        self.assertIn('["setup", "--json"]', state)
        self.assertIn('["setup", "--dry-run", "--json"]', state)
        self.assertNotIn(
            'runSG(arguments: ["setup", "--dry-run", "--json"])',
            state.split("func runSetup")[1][:400] if "func runSetup" in state else "",
        )
        panes = (MACOS / "Panes.swift").read_text(encoding="utf-8")
        self.assertIn("struct SetupPane", panes)
        self.assertIn("struct RetainPane", panes)
        self.assertIn("onAppear { state.listSessions() }", panes)
        self.assertIn('listBlock("Active"', panes)
        self.assertIn('listBlock("Bucket"', panes)
        self.assertIn('listBlock("Purged"', panes)
        self.assertIn("Move current to bucket", panes)
        self.assertIn("Purge bucket", panes)
        self.assertIn("Empty purged", panes)
        self.assertIn("Destroy…", panes)
        self.assertIn("Run setup", panes)
        self.assertIn("First-run wizard", panes)
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
        self.assertIn("SetupWizard()", content)
        self.assertIn(".sheet(isPresented: $state.showWizard)", content)
        wizard = (MACOS / "Wizard.swift").read_text(encoding="utf-8")
        self.assertIn("struct SetupWizard", wizard)
        self.assertIn("First-run setup", wizard)
        self.assertIn("Skip wizard", wizard)
        self.assertIn("Disposable session", wizard)
        app = (MACOS / "SpindleGuardApp.swift").read_text(encoding="utf-8")
        self.assertIn('Button("Start")', app)
        self.assertIn('Button("Stop")', app)
        self.assertIn('CommandMenu("Setup")', app)
        self.assertIn('Button("First-Run Setup Wizard', app)
        self.assertIn("MenuBarExtra", app)
        self.assertIn('systemImage: "externaldrive"', app)
        self.assertIn('.menuBarExtraStyle(.menu)', app)
        self.assertIn('Section("Window")', app)
        self.assertIn('Section("Setup")', app)
        self.assertIn('Section("Session")', app)
        self.assertIn('Section("Broker")', app)
        self.assertIn('Section("Identity")', app)
        for extra in (
            "Show SpindleGuard",
            "First-Run Setup Wizard",
            "Preview Setup",
            "Run Setup",
            "Verify Install",
            "Install FUSE-T",
            "Copy FUSE-T Command",
            "Open FUSE-T Docs",
            "Refresh Doctor",
            "New Disposable Session",
            "Load Session",
            "Retained Sessions",
            "Move Current Session to Bucket",
            "Purge Bucket",
            "Empty Purged List",
            "Open Session Parent",
            "Policy Check",
            "Preview Start",
            "Open Mount in Finder",
            "Open Source in Finder",
            "Reveal Log",
            "Probe Queue",
            "Scan Tree",
            "Bind Example Identity",
            "Load Example Identity",
            "Load Failing Example",
            "Rotate Manifest",
            "Resolve Topology",
            "Quit SpindleGuard",
        ):
            self.assertIn(f'Button("{extra}', app)
        self.assertIn("import UniformTypeIdentifiers", state)
        self.assertIn("sessionParent()", (MACOS / "SGPaths.swift").read_text(encoding="utf-8"))
        self.assertIn("func unmount(mount: String)", (MACOS / "BrokerService.swift").read_text(encoding="utf-8"))

    def test_preview_html_mirrors_native_chrome(self):
        page = (MACOS / "preview.html").read_text(encoding="utf-8")
        self.assertIn("SpindleGuard", page)
        self.assertIn("Three lists", page)
        self.assertIn("session-purge", page)
        self.assertIn("session-destroy", page)
        self.assertIn('id="purgedBody"', page)
        self.assertIn("Empty Purged List", page)
        self.assertIn("Move Current Session to Bucket", page)
        self.assertIn('id="extraBtn"', page)
        self.assertIn("New Session", page)
        self.assertIn("Retain", page)
        self.assertIn("First-Run Setup Wizard", page)
        self.assertIn("First-run setup", page)
        self.assertIn("Skip wizard", page)
        self.assertIn("SGWizardFinished", page)
        self.assertIn('class="group">Window</p>', page)
        self.assertIn('class="group">Setup</p>', page)
        self.assertIn('class="group">Session</p>', page)
        self.assertIn('class="group">Broker</p>', page)
        self.assertIn('class="group">Identity</p>', page)
        self.assertIn("maybePresentWizard", page)
        self.assertIn("New Disposable Session", page)
        self.assertIn("Resolve Topology", page)

    def test_info_plist(self):
        info = plistlib.loads((MACOS / "Info.plist").read_bytes())
        self.assertEqual(info["CFBundleIdentifier"], "cloud.alienweb.spindleguard")
        self.assertEqual(info["CFBundleExecutable"], "SpindleGuard")
        self.assertEqual(info["LSMinimumSystemVersion"], "13.0")
        self.assertEqual(info["CFBundleShortVersionString"], "0.8")
        self.assertEqual(info["CFBundleVersion"], "8")
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
        self.assertIn("macos/Wizard.swift", makefile)


if __name__ == "__main__":
    unittest.main()
