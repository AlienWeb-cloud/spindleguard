# SPDX-License-Identifier: GPL-2.0-or-later
"""Manifest rotation is explicit, logged, and never an in-place edit."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from bindcheck.bind import BindError, UnresolvableField
from bindcheck.manifest import (
    MSG_NO_CHANGE,
    MSG_NO_REASON,
    MSG_OUT_EXISTS,
    fields_changed,
    rotate_manifest,
)

OLD = {
    "generation": 1,
    "serial": "SERIAL-A",
    "partuuid": "PART-A",
    "fs_uuid": "FS-A",
    "media_class": "stable",
}
NEW = {
    "serial": "SERIAL-A",
    "partuuid": "PART-A-NEW",
    "fs_uuid": "FS-A-NEW",
    "media_class": "stable",
}


class ManifestRotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fields_changed_lists_identity_keys(self):
        self.assertEqual(fields_changed(OLD, NEW), ["partuuid", "fs_uuid"])

    def test_writes_new_generation_and_audit_line(self):
        out = self.dir / "manifest.generation-2.json"
        audit = self.dir / "manifest-audit.jsonl"
        result = rotate_manifest(
            OLD, NEW, reason="repartitioned after imaging", out_path=out, audit_path=audit
        )
        self.assertEqual(result["generation"], 2)
        self.assertEqual(result["partuuid"], "PART-A-NEW")
        self.assertEqual(result["rotation_reason"], "repartitioned after imaging")
        self.assertTrue(out.is_file())
        lines = audit.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["event"], "manifest-rotate")
        self.assertEqual(record["fields_changed"], ["partuuid", "fs_uuid"])
        self.assertEqual(record["from_generation"], 1)
        self.assertEqual(record["to_generation"], 2)
        self.assertIn("old_sha256", record)
        self.assertIn("new_sha256", record)

    def test_refuses_overwrite(self):
        out = self.dir / "manifest.json"
        out.write_text("{}\n", encoding="utf-8")
        before = out.read_bytes()
        audit = self.dir / "audit.jsonl"
        with self.assertRaises(BindError) as cm:
            rotate_manifest(OLD, NEW, reason="nope", out_path=out, audit_path=audit)
        self.assertEqual(str(cm.exception), MSG_OUT_EXISTS)
        self.assertEqual(out.read_bytes(), before)
        self.assertFalse(audit.exists())

    def test_requires_reason(self):
        with self.assertRaises(BindError) as cm:
            rotate_manifest(
                OLD,
                NEW,
                reason="  ",
                out_path=self.dir / "n.json",
                audit_path=self.dir / "a.jsonl",
            )
        self.assertEqual(str(cm.exception), MSG_NO_REASON)

    def test_no_change_refused(self):
        with self.assertRaises(BindError) as cm:
            rotate_manifest(
                OLD,
                OLD,
                reason="same",
                out_path=self.dir / "n.json",
                audit_path=self.dir / "a.jsonl",
            )
        self.assertEqual(str(cm.exception), MSG_NO_CHANGE)

    def test_unresolvable_observed(self):
        with self.assertRaises(UnresolvableField):
            rotate_manifest(
                OLD,
                {"serial": "SERIAL-A", "partuuid": "", "fs_uuid": "FS"},
                reason="bad",
                out_path=self.dir / "n.json",
                audit_path=self.dir / "a.jsonl",
            )

    def test_append_audit_does_not_rewrite(self):
        out1 = self.dir / "g2.json"
        out2 = self.dir / "g3.json"
        audit = self.dir / "audit.jsonl"
        first = rotate_manifest(OLD, NEW, reason="first", out_path=out1, audit_path=audit)
        rotate_manifest(first, dict(NEW, fs_uuid="FS-3"), reason="second", out_path=out2, audit_path=audit)
        self.assertEqual(len(audit.read_text(encoding="utf-8").splitlines()), 2)
        self.assertTrue(out1.is_file())
        self.assertTrue(out2.is_file())


if __name__ == "__main__":
    unittest.main()
