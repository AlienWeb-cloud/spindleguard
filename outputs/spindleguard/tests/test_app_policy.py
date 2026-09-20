# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-path policy for the native app and sg CLI."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "python"))

from sgcontrol.broker import broker_command
from sgcontrol.policy import (
    DEV_MSG,
    DISJOINT_MSG,
    EMPTY_MSG,
    MARKER_NAME,
    PREFIX_MISSING_MSG,
    PREFIX_SHAPE_MSG,
    VOLUMES_MSG,
    PolicyError,
    check,
    check_observe_path,
    check_session_parent,
    is_dev_path,
    is_volumes_path,
)


class PolicyTests(unittest.TestCase):
    def test_volumes_string_refused_without_stat(self):
        self.assertTrue(is_volumes_path("/Volumes"))
        self.assertTrue(is_volumes_path("/Volumes/exhibit"))
        self.assertFalse(is_volumes_path("/tmp"))
        with self.assertRaises(PolicyError) as cm:
            check("/Volumes/exhibit", "/tmp/mount", require_marker=False)
        self.assertEqual(str(cm.exception), VOLUMES_MSG)

    def test_dev_string_refused(self):
        self.assertTrue(is_dev_path("/dev/sda1"))
        with self.assertRaises(PolicyError) as cm:
            check("/dev/sda1", "/tmp/mount", require_marker=False)
        self.assertEqual(str(cm.exception), DEV_MSG)

    def test_empty_paths(self):
        with self.assertRaises(PolicyError) as cm:
            check("", "/tmp/m", require_marker=False)
        self.assertEqual(str(cm.exception), EMPTY_MSG)

    def test_disjoint_and_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            mount = root / "mount"
            nested = source / "inside"
            source.mkdir()
            mount.mkdir()
            nested.mkdir()
            with self.assertRaises(PolicyError) as cm:
                check(str(source), str(nested), require_marker=False)
            self.assertEqual(str(cm.exception), DISJOINT_MSG)
            with self.assertRaises(PolicyError) as cm:
                check(str(source), str(mount))
            self.assertEqual(str(cm.exception), "Missing disposable test root marker.")
            (source / MARKER_NAME).write_text("disposable test data\n")
            check(str(source), str(mount), require_marker=True)

    def test_write_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            mount = Path(tmp) / "mount"
            source.mkdir()
            mount.mkdir()
            (source / MARKER_NAME).write_text("x\n")
            with self.assertRaises(PolicyError) as cm:
                check(str(source), str(mount), "/Workspace")
            self.assertEqual(str(cm.exception), PREFIX_MISSING_MSG)
            (source / "Workspace").mkdir()
            check(str(source), str(mount), "/Workspace")
            with self.assertRaises(PolicyError) as cm:
                check(str(source), str(mount), "/Workspace/")
            self.assertEqual(str(cm.exception), PREFIX_SHAPE_MSG)

    def test_session_parent_volumes(self):
        with self.assertRaises(PolicyError) as cm:
            check_session_parent("/Volumes")
        self.assertEqual(str(cm.exception), VOLUMES_MSG)

    def test_observe_path(self):
        with self.assertRaises(PolicyError) as cm:
            check_observe_path("/Volumes/x")
        self.assertEqual(str(cm.exception), VOLUMES_MSG)
        with self.assertRaises(PolicyError) as cm:
            check_observe_path("/dev/disk0")
        self.assertEqual(str(cm.exception), DEV_MSG)

    def test_broker_command_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            mount = Path(tmp) / "mount"
            source.mkdir()
            mount.mkdir()
            (source / MARKER_NAME).write_text("x\n")
            (source / "Workspace").mkdir()
            cmd = broker_command("/helper/spindleguard", str(source), str(mount), "/Workspace", 150)
            self.assertEqual(cmd[0], "/helper/spindleguard")
            self.assertEqual(cmd[3], "/Workspace")
            self.assertEqual(cmd[4], "150")
            ro = broker_command("/helper/spindleguard", str(source), str(mount), None, None)
            self.assertEqual(ro, ["/helper/spindleguard", str(source), str(mount)])
            delayed = broker_command("/helper/spindleguard", str(source), str(mount), None, 80)
            self.assertEqual(delayed[3], "-")
            self.assertEqual(delayed[4], "80")

    def test_broker_command_refuses_volumes(self):
        with self.assertRaises(PolicyError):
            broker_command("/helper/spindleguard", "/Volumes/x", "/tmp/m", require_marker=False)


if __name__ == "__main__":
    unittest.main()
