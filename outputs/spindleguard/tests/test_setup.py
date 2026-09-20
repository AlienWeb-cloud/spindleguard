# SPDX-License-Identifier: GPL-2.0-or-later
"""One-command setup and install verification. No mounts, no host /dev."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "python"))

from sgcontrol.policy import PolicyError, VOLUMES_MSG
from sgcontrol.session import default_parent
from sgcontrol.setup import MSG_FUSE_MAC, MSG_FUSE_YES, setup
from sgcontrol.verify import verify_quick

from test_sg_cli import run_sg


class SetupTests(unittest.TestCase):
    def test_dry_run_steps(self):
        report = setup(PROJECT, dry_run=True)
        names = [s["name"] for s in report["steps"]]
        self.assertEqual(
            names,
            ["python", "macos", "fuse-t", "build-broker", "build-app", "session"],
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["dry_run"])
        self.assertIsNone(report["session"])
        self.assertIn("brew install macos-fuse-t/homebrew-cask/fuse-t", report["fuse_install"])

    def test_dry_run_create_session_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = setup(
                PROJECT,
                dry_run=True,
                create_session_flag=True,
                session_parent=Path(tmp),
            )
            self.assertIsNone(report["session"])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_install_fuse_requires_yes(self):
        with self.assertRaises(PolicyError) as cm:
            setup(PROJECT, install_fuse=True, dry_run=True)
        self.assertEqual(str(cm.exception), MSG_FUSE_YES)

    def test_install_fuse_requires_macos(self):
        if sys.platform == "darwin":
            return
        with self.assertRaises(PolicyError) as cm:
            setup(PROJECT, install_fuse=True, yes=True, dry_run=True)
        self.assertEqual(str(cm.exception), MSG_FUSE_MAC)

    def test_cli_setup_dry_run(self):
        result = run_sg("setup", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["ok"])

    def test_cli_setup_install_fuse_without_yes(self):
        result = run_sg("setup", "--install-fuse", "--dry-run", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --yes", result.stderr)
        self.assertIn("./sg setup --dry-run --json", result.stderr)

    def test_verify_quick(self):
        payload = verify_quick(PROJECT)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["mode"], "quick")
        names = [c["name"] for c in payload["checks"]]
        self.assertIn("volumes-refusal", names)
        self.assertIn("scan", names)
        self.assertIn("bind-example", names)
        self.assertIn("purge-requires-yes", names)
        self.assertIn("unmount-volumes", names)

    def test_cli_verify_quick(self):
        result = run_sg("verify", "--quick", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["failed"], [])

    def test_verify_quick_source_does_not_run_full(self):
        text = (PROJECT / "python/sgcontrol/verify.py").read_text(encoding="utf-8")
        quick = text.split("def verify_full")[0]
        self.assertNotIn("tests/strict.py", quick)
        self.assertNotIn("run_bindcheck_mutations", quick)
        self.assertNotIn("make test\n", quick)

    def test_unmount_refuses_volumes(self):
        result = run_sg("unmount", "--mount", "/Volumes/exhibit", "--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Prototype refuses /Volumes paths", result.stderr)

    def test_unmount_dry_run_safe_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_sg("unmount", "--mount", tmp, "--dry-run", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["cmd"][0], "/sbin/umount")
            self.assertTrue(payload["dry_run"])

    def test_unmount_linux_without_dry_run(self):
        if sys.platform == "darwin":
            return
        with tempfile.TemporaryDirectory() as tmp:
            result = run_sg("unmount", "--mount", tmp)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unmount requires macOS", result.stderr)

    def test_session_parent_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get("SPINDLEGUARD_SESSION_PARENT")
            os.environ["SPINDLEGUARD_SESSION_PARENT"] = tmp
            try:
                self.assertEqual(default_parent(PROJECT), Path(tmp))
            finally:
                if previous is None:
                    del os.environ["SPINDLEGUARD_SESSION_PARENT"]
                else:
                    os.environ["SPINDLEGUARD_SESSION_PARENT"] = previous

    def test_session_parent_env_volumes(self):
        previous = os.environ.get("SPINDLEGUARD_SESSION_PARENT")
        os.environ["SPINDLEGUARD_SESSION_PARENT"] = "/Volumes/exhibit"
        try:
            with self.assertRaises(PolicyError) as cm:
                default_parent(PROJECT)
            self.assertEqual(str(cm.exception), VOLUMES_MSG)
        finally:
            if previous is None:
                del os.environ["SPINDLEGUARD_SESSION_PARENT"]
            else:
                os.environ["SPINDLEGUARD_SESSION_PARENT"] = previous

    def test_session_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = run_sg("session-create", "--parent", tmp, "--json")
            self.assertEqual(created.returncode, 0, created.stderr)
            rec = json.loads(created.stdout)
            loaded = run_sg(
                "session-load",
                "--file",
                str(Path(rec["session"]) / "session.json"),
                "--json",
            )
            self.assertEqual(loaded.returncode, 0, loaded.stderr)
            body = json.loads(loaded.stdout)
            self.assertEqual(body["source"], rec["source"])
            self.assertTrue(body["retained"])

    def test_session_list_has_empty_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = run_sg("session-create", "--parent", tmp, "--json")
            rec = json.loads(created.stdout)
            listed = run_sg("session-list", "--parent", tmp, "--json")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            payload = json.loads(listed.stdout)
            self.assertTrue(payload["deletion_buckets"])
            self.assertTrue(payload["deletes"])
            self.assertFalse(payload["deletes_active"])
            self.assertEqual(payload["sessions"][0]["session"], rec["session"])
            self.assertEqual(payload["bucket"], [])

    def test_session_bucket_restore_purge(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = run_sg("session-create", "--parent", tmp, "--json")
            rec = json.loads(created.stdout)
            session = rec["session"]
            marker = Path(session) / "source" / ".spindleguard-test-root"
            self.assertTrue(marker.is_file())
            refused = run_sg("session-purge", "--session", session, "--json")
            self.assertEqual(refused.returncode, 2)
            self.assertIn("requires --yes", refused.stderr)
            self.assertTrue(Path(session).is_dir())
            active_purge = run_sg("session-purge", "--session", session, "--yes", "--json")
            self.assertEqual(active_purge.returncode, 2)
            self.assertIn("already in the bucket", active_purge.stderr)
            self.assertTrue(Path(session).is_dir())
            moved = run_sg("session-bucket", "--session", session, "--parent", tmp, "--json")
            self.assertEqual(moved.returncode, 0, moved.stderr)
            body = json.loads(moved.stdout)
            self.assertTrue(body["deletion_bucket"])
            self.assertFalse(Path(session).exists())
            bucketed = body["session"]
            self.assertTrue(Path(bucketed).is_dir())
            listed = json.loads(run_sg("session-list", "--parent", tmp, "--json").stdout)
            self.assertEqual(listed["sessions"], [])
            self.assertEqual(listed["bucket"][0]["session"], bucketed)
            restored = run_sg("session-restore", "--session", bucketed, "--parent", tmp, "--json")
            self.assertEqual(restored.returncode, 0, restored.stderr)
            back = json.loads(restored.stdout)
            self.assertFalse(back["deletion_bucket"])
            self.assertTrue(Path(back["session"]).is_dir())
            run_sg("session-bucket", "--session", back["session"], "--parent", tmp, "--json")
            listed = json.loads(run_sg("session-list", "--parent", tmp, "--json").stdout)
            target = listed["bucket"][0]["session"]
            purged = run_sg("session-purge", "--session", target, "--yes", "--json")
            self.assertEqual(purged.returncode, 0, purged.stderr)
            gone = json.loads(purged.stdout)
            self.assertEqual(gone["count"], 1)
            self.assertFalse(Path(target).exists())
            empty = json.loads(run_sg("session-list", "--parent", tmp, "--json").stdout)
            self.assertEqual(empty["bucket"], [])
            self.assertEqual(empty["sessions"], [])

    def test_session_purge_all_and_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = json.loads(run_sg("session-create", "--parent", tmp, "--json").stdout)
            second = json.loads(run_sg("session-create", "--parent", tmp, "--json").stdout)
            run_sg("session-bucket", "--session", first["session"], "--parent", tmp, "--json")
            run_sg("session-bucket", "--session", second["session"], "--parent", tmp, "--json")
            dry = run_sg("session-purge", "--all", "--parent", tmp, "--dry-run", "--json")
            self.assertEqual(dry.returncode, 0, dry.stderr)
            planned = json.loads(dry.stdout)
            self.assertEqual(planned["count"], 2)
            self.assertTrue(planned["dry_run"])
            listed = json.loads(run_sg("session-list", "--parent", tmp, "--json").stdout)
            self.assertEqual(len(listed["bucket"]), 2)
            emptied = run_sg("session-purge", "--all", "--parent", tmp, "--yes", "--json")
            self.assertEqual(emptied.returncode, 0, emptied.stderr)
            after = json.loads(run_sg("session-list", "--parent", tmp, "--json").stdout)
            self.assertEqual(after["bucket"], [])
            volumes = run_sg("session-bucket", "--session", "/Volumes/exhibit")
            self.assertEqual(volumes.returncode, 2)
            self.assertIn("Prototype refuses /Volumes", volumes.stderr)

    def test_preview_refuses_dangerous_argv(self):
        from sgcontrol.policy import PolicyError
        from sgcontrol.ui import _validate_argv

        with self.assertRaises(PolicyError):
            _validate_argv(["setup", "--install-fuse", "--yes"])
        with self.assertRaises(PolicyError):
            _validate_argv(["session-purge", "--session", "/tmp/ui-session-1"])
        with self.assertRaises(PolicyError):
            _validate_argv(["verify", "--full"])
        with self.assertRaises(PolicyError):
            _validate_argv(["start", "--source", "/tmp/a", "--mount", "/tmp/b"])
        with self.assertRaises(PolicyError):
            _validate_argv(["topology", "--path", "/Volumes/exhibit"])
        _validate_argv(["setup", "--dry-run", "--json"])
        _validate_argv(["start", "--dry-run", "--source", "/tmp/a", "--mount", "/tmp/b"])
        _validate_argv(["session-purge", "--session", "/tmp/ui-session-1", "--yes", "--json"])
        _validate_argv(["session-bucket", "--session", "/tmp/ui-session-1", "--json"])

    def test_session_load_volumes(self):
        result = run_sg("session-load", "--file", "/Volumes/exhibit/session.json")
        self.assertEqual(result.returncode, 2)

    def test_root_wrapper(self):
        wrapper = PROJECT.parent.parent / "sg"
        self.assertTrue(wrapper.is_file(), wrapper)
        import subprocess

        result = subprocess.run(
            [sys.executable, str(wrapper), "doctor", "--json"],
            cwd=str(PROJECT.parent.parent),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("can_mount", payload)
        self.assertTrue(payload["ready_for_ui"])


if __name__ == "__main__":
    unittest.main()
