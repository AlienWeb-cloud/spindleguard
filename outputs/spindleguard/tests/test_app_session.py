# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable UI sessions. Never deletes; uses a temp parent."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "python"))

from sgcontrol.policy import MARKER_NAME, PolicyError, VOLUMES_MSG, check
from sgcontrol.session import create_session, load_session


class SessionTests(unittest.TestCase):
    def test_create_session_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = create_session(Path(tmp))
            source = Path(record["source"])
            mount = Path(record["mount"])
            self.assertTrue((source / MARKER_NAME).is_file())
            self.assertTrue((source / "Workspace").is_dir())
            self.assertTrue((source / "large.bin").is_file())
            self.assertTrue((source / "second.txt").is_file())
            self.assertTrue(mount.is_dir())
            self.assertTrue(Path(record["log"]).is_file())
            check(str(source), str(mount), "/Workspace")
            loaded = load_session(Path(record["session"]) / "session.json")
            self.assertEqual(loaded["source"], record["source"])
            self.assertTrue(loaded["retained"])
            self.assertFalse(record["deletion_bucket"])

    def test_refuses_volumes_parent(self):
        with self.assertRaises(PolicyError):
            create_session(Path("/Volumes/exhibit"))

    def test_load_session_refuses_volumes_file(self):
        with self.assertRaises(PolicyError) as cm:
            load_session(Path("/Volumes/exhibit/session.json"))
        self.assertEqual(str(cm.exception), VOLUMES_MSG)


if __name__ == "__main__":
    unittest.main()
