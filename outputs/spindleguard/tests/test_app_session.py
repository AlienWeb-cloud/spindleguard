# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable UI sessions. Uses a temp parent. Purge is bucket-only."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "python"))

from sgcontrol.policy import MARKER_NAME, PolicyError, VOLUMES_MSG, check
from sgcontrol.session import create_session, load_session, bucket_session, restore_session, purge_sessions, list_sessions


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
            listed = list_sessions(Path(tmp))
            self.assertTrue(listed["deletion_buckets"])
            self.assertEqual(listed["bucket"], [])

    def test_bucket_restore_purge(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            record = create_session(parent)
            session = Path(record["session"])
            with self.assertRaises(PolicyError):
                purge_sessions(parent, session, yes=False)
            self.assertTrue(session.is_dir())
            moved = bucket_session(parent, session)
            self.assertTrue(moved["deletion_bucket"])
            self.assertFalse(session.exists())
            bucketed = Path(moved["session"])
            self.assertTrue(bucketed.is_dir())
            loaded = load_session(bucketed / "session.json")
            self.assertTrue(loaded["deletion_bucket"])
            restored = restore_session(parent, bucketed)
            self.assertFalse(restored["deletion_bucket"])
            live = Path(restored["session"])
            self.assertTrue(live.is_dir())
            bucket_session(parent, live)
            listed = list_sessions(parent)
            target = Path(listed["bucket"][0]["session"])
            purged = purge_sessions(parent, target, yes=True)
            self.assertEqual(purged["count"], 1)
            self.assertFalse(target.exists())

    def test_refuses_volumes_parent(self):
        with self.assertRaises(PolicyError):
            create_session(Path("/Volumes/exhibit"))

    def test_load_session_refuses_volumes_file(self):
        with self.assertRaises(PolicyError) as cm:
            load_session(Path("/Volumes/exhibit/session.json"))
        self.assertEqual(str(cm.exception), VOLUMES_MSG)


if __name__ == "__main__":
    unittest.main()
