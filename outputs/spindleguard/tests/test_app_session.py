# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable UI sessions. Three lists: active, bucket, purged."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "python"))

from sgcontrol.policy import MARKER_NAME, PolicyError, VOLUMES_MSG, check
from sgcontrol.session import (
    MSG_ALREADY_BUCKETED,
    MSG_DESTROY_YES,
    MSG_NOT_ACTIVE,
    MSG_NOT_IN_BUCKET,
    MSG_NOT_PURGED,
    MSG_NOT_STAGED,
    bucket_session,
    create_session,
    destroy_sessions,
    list_sessions,
    load_session,
    purge_sessions,
    restore_session,
)


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
            self.assertFalse(record["purged"])
            listed = list_sessions(Path(tmp))
            self.assertTrue(listed["deletion_buckets"])
            self.assertEqual(listed["bucket"], [])
            self.assertEqual(listed["purged"], [])

    def test_bucket_purge_destroy_three_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            record = create_session(parent)
            session = Path(record["session"])
            with self.assertRaises(PolicyError) as cm:
                purge_sessions(parent, session)
            self.assertEqual(str(cm.exception), MSG_NOT_IN_BUCKET)
            self.assertTrue(session.is_dir())
            moved = bucket_session(parent, session)
            self.assertTrue(moved["deletion_bucket"])
            self.assertFalse(moved["purged"])
            self.assertFalse(session.exists())
            bucketed = Path(moved["session"])
            self.assertTrue(bucketed.is_dir())
            loaded = load_session(bucketed / "session.json")
            self.assertTrue(loaded["deletion_bucket"])
            restored = restore_session(parent, bucketed)
            self.assertFalse(restored["deletion_bucket"])
            self.assertFalse(restored["purged"])
            live = Path(restored["session"])
            self.assertTrue(live.is_dir())
            bucket_session(parent, live)
            listed = list_sessions(parent)
            target = Path(listed["bucket"][0]["session"])
            with self.assertRaises(PolicyError) as cm:
                destroy_sessions(parent, target, yes=True)
            self.assertEqual(str(cm.exception), MSG_NOT_PURGED)
            self.assertTrue(target.is_dir())
            purged = purge_sessions(parent, target)
            self.assertEqual(purged["count"], 1)
            self.assertTrue(purged["purged"])
            self.assertFalse(purged["deletion_bucket"])
            self.assertEqual(purged["lane"], "purged")
            self.assertFalse(target.exists())
            listed = list_sessions(parent)
            self.assertEqual(listed["bucket"], [])
            self.assertEqual(len(listed["purged"]), 1)
            purged_dir = Path(listed["purged"][0]["session"])
            self.assertTrue(purged_dir.is_dir())
            self.assertTrue((purged_dir / "source" / MARKER_NAME).is_file())
            loaded = load_session(purged_dir / "session.json")
            self.assertTrue(loaded["purged"])
            self.assertFalse(loaded["deletion_bucket"])
            with self.assertRaises(PolicyError) as cm:
                destroy_sessions(parent, purged_dir, yes=False)
            self.assertEqual(str(cm.exception), MSG_DESTROY_YES)
            self.assertTrue(purged_dir.is_dir())
            restored = restore_session(parent, purged_dir)
            self.assertTrue(restored["deletion_bucket"])
            self.assertFalse(restored["purged"])
            bucketed = Path(restored["session"])
            self.assertTrue(bucketed.is_dir())
            purge_sessions(parent, bucketed)
            listed = list_sessions(parent)
            final = Path(listed["purged"][0]["session"])
            gone = destroy_sessions(parent, final, yes=True)
            self.assertEqual(gone["count"], 1)
            self.assertFalse(final.exists())
            empty = list_sessions(parent)
            self.assertEqual(empty["sessions"], [])
            self.assertEqual(empty["bucket"], [])
            self.assertEqual(empty["purged"], [])

    def test_lanes_cannot_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            record = create_session(parent)
            active = Path(record["session"])
            with self.assertRaises(PolicyError) as cm:
                restore_session(parent, active)
            self.assertEqual(str(cm.exception), MSG_NOT_STAGED)
            with self.assertRaises(PolicyError) as cm:
                destroy_sessions(parent, active, yes=True)
            self.assertEqual(str(cm.exception), MSG_NOT_PURGED)
            self.assertTrue(active.is_dir())
            bucketed = Path(bucket_session(parent, active)["session"])
            with self.assertRaises(PolicyError) as cm:
                bucket_session(parent, bucketed)
            self.assertEqual(str(cm.exception), MSG_ALREADY_BUCKETED)
            purged = Path(purge_sessions(parent, bucketed)["session"])
            self.assertTrue((purged / "source" / MARKER_NAME).is_file())
            with self.assertRaises(PolicyError) as cm:
                bucket_session(parent, purged)
            self.assertEqual(str(cm.exception), MSG_NOT_ACTIVE)
            with self.assertRaises(PolicyError) as cm:
                purge_sessions(parent, purged)
            self.assertEqual(str(cm.exception), MSG_NOT_IN_BUCKET)
            self.assertTrue(purged.is_dir())
            listed = list_sessions(parent)
            self.assertEqual(listed["sessions"], [])
            self.assertEqual(listed["bucket"], [])
            self.assertEqual(len(listed["purged"]), 1)
            loaded = load_session(purged / "session.json")
            self.assertIn(f"/{loaded['lane']}/", loaded["source"].replace("\\", "/"))

    def test_refuses_volumes_parent(self):
        with self.assertRaises(PolicyError):
            create_session(Path("/Volumes/exhibit"))

    def test_load_session_refuses_volumes_file(self):
        with self.assertRaises(PolicyError) as cm:
            load_session(Path("/Volumes/exhibit/session.json"))
        self.assertEqual(str(cm.exception), VOLUMES_MSG)


if __name__ == "__main__":
    unittest.main()
