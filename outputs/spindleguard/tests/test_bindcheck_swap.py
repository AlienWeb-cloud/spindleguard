# SPDX-License-Identifier: GPL-2.0-or-later
"""The sda/sdb swap incident: permission checks pass, identity must not.

A carve was hardcoded to /dev/sda1. After reboot the names swapped. Every
check was permission-shaped (exists? read-only? allowed?) so it passed on
the wrong disk. Identity is serial / PARTUUID / FS-UUID plus major:minor
of the fd, not the path string.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from bindcheck.bind import IdentityMismatch, assert_bound
from bindcheck.fake import FakeBlock, FakeResolver

MANIFEST_A = {
    "serial": "SERIAL-A",
    "partuuid": "PART-A",
    "fs_uuid": "FS-A",
    "media_class": "stable",
}


def swapped_bus():
    """After reboot, the name /dev/sda1 now names drive B."""
    return FakeResolver(
        [
            FakeBlock(
                path="/dev/sda1",
                serial="SERIAL-B",
                partuuid="PART-B",
                fs_uuid="FS-B",
                major=8,
                minor=1,
                ro=True,
            ),
            FakeBlock(
                path="/dev/sdb1",
                serial="SERIAL-A",
                partuuid="PART-A",
                fs_uuid="FS-A",
                major=8,
                minor=17,
                ro=True,
            ),
        ]
    )


def permission_shaped(block: FakeBlock) -> bool:
    return bool(block.ro) and block.path.startswith("/dev/")


class SwapIncidentTests(unittest.TestCase):
    def test_permission_shaped_check_passes_on_wrong_disk(self):
        res = swapped_bus()
        wrong = next(b for b in res.blocks if b.path == "/dev/sda1")
        self.assertTrue(permission_shaped(wrong))
        self.assertEqual(wrong.serial, "SERIAL-B")

    def test_hardcoded_sda1_refuses_after_swap(self):
        res = swapped_bus()
        with self.assertRaises(IdentityMismatch) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(str(cm.exception), "identity mismatch: serial")
        self.assertEqual(cm.exception.expected, "SERIAL-A")
        self.assertEqual(cm.exception.observed, "SERIAL-B")

    def test_partuuid_mismatch_message(self):
        res = swapped_bus()
        manifest = {
            "serial": "SERIAL-B",
            "partuuid": "PART-A",
            "fs_uuid": "FS-B",
        }
        with self.assertRaises(IdentityMismatch) as cm:
            assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertEqual(str(cm.exception), "identity mismatch: partuuid")

    def test_correct_name_after_swap_still_binds_by_identity(self):
        res = swapped_bus()
        bound = assert_bound("/dev/sdb1", MANIFEST_A, resolver=res)
        self.assertEqual(bound.serial, "SERIAL-A")
        self.assertEqual((bound.major, bound.minor), (8, 17))
        with self.assertRaises(AttributeError):
            _ = bound.path

    def test_open_records_the_path_only_as_open_argument(self):
        res = swapped_bus()
        with self.assertRaises(IdentityMismatch):
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        opens = [arg for name, arg in res.calls if name == "open"]
        self.assertEqual(opens, ["/dev/sda1"])
        idents = [arg for name, arg in res.calls if name == "identity_from_fd"]
        self.assertEqual(len(idents), 1)
        self.assertIsInstance(idents[0], int)


if __name__ == "__main__":
    unittest.main()
