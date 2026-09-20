# SPDX-License-Identifier: GPL-2.0-or-later
"""assert_bound refusals, fd return, fingerprint skip reasons.

Each refusal fixture is valid on every other axis so deleting that one
check makes this test go red (see run_bindcheck_mutations.py).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from bindcheck.bind import (
    SKIP_FAILING,
    SKIP_NOT_ALLOWED,
    SKIP_UNSET_CLASS,
    SKIP_USB_BRIDGE,
    MSG_NO_PATH,
    MSG_VOLUMES,
    AmbiguousSerial,
    BindError,
    BoundDevice,
    IdentityMismatch,
    NoManifest,
    NotReadOnly,
    UnresolvableField,
    assert_bound,
    open_device_readonly,
)
from bindcheck.fake import FakeBlock, FakeResolver

MANIFEST_A = {
    "serial": "SERIAL-A",
    "partuuid": "PART-A",
    "fs_uuid": "FS-A",
    "media_class": "stable",
    "allow_fingerprint": False,
}

DRIVE_A = FakeBlock(
    path="/dev/sda1",
    serial="SERIAL-A",
    partuuid="PART-A",
    fs_uuid="FS-A",
    major=8,
    minor=1,
    ro=True,
)
DRIVE_B = FakeBlock(
    path="/dev/sdb1",
    serial="SERIAL-B",
    partuuid="PART-B",
    fs_uuid="FS-B",
    major=8,
    minor=17,
    ro=True,
)


def resolver(*blocks: FakeBlock) -> FakeResolver:
    return FakeResolver(list(blocks))


class AssertBoundTests(unittest.TestCase):
    def test_bind_success_returns_fd_not_path(self):
        res = resolver(DRIVE_A)
        bound = assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertIsInstance(bound, BoundDevice)
        self.assertIsInstance(bound.fd, int)
        self.assertGreaterEqual(bound.fd, 0)
        self.assertEqual(bound.fileno(), bound.fd)
        self.assertEqual(bound.serial, "SERIAL-A")
        self.assertEqual((bound.major, bound.minor), (8, 1))
        with self.assertRaises(AttributeError) as cm:
            _ = bound.path
        self.assertIn("does not expose a path", str(cm.exception))
        self.assertEqual(str(cm.exception), MSG_NO_PATH)
        self.assertNotIn("path", bound.as_log())

    def test_success_order_open_fstat_identity_then_readonly(self):
        res = resolver(DRIVE_A)
        bound = assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        names = res.call_names()
        self.assertEqual(names[0], "open")
        self.assertIn("fstat", names)
        self.assertIn("identity_from_fd", names)
        self.assertIn("is_read_only", names)
        self.assertLess(names.index("open"), names.index("fstat"))
        self.assertLess(names.index("fstat"), names.index("identity_from_fd"))
        self.assertLess(names.index("identity_from_fd"), names.index("is_read_only"))
        ro_calls = [arg for name, arg in res.calls if name == "is_read_only"]
        self.assertEqual(ro_calls, [bound.fd])

    def test_no_manifest_none(self):
        res = resolver(DRIVE_A)
        with self.assertRaises(NoManifest) as cm:
            assert_bound("/dev/sda1", None, resolver=res)
        self.assertEqual(str(cm.exception), "no identity manifest")
        self.assertNotIn("open", res.call_names())

    def test_no_manifest_empty(self):
        res = resolver(DRIVE_A)
        with self.assertRaises(NoManifest) as cm:
            assert_bound("/dev/sda1", {}, resolver=res)
        self.assertEqual(str(cm.exception), "no identity manifest")

    def test_unresolvable_manifest_serial(self):
        res = resolver(DRIVE_A)
        manifest = dict(MANIFEST_A, serial="")
        with self.assertRaises(UnresolvableField) as cm:
            assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertEqual(cm.exception.field, "serial")
        self.assertEqual(str(cm.exception), "unresolvable identity field: serial")
        self.assertNotIn("open", res.call_names())

    def test_unresolvable_manifest_partuuid(self):
        res = resolver(DRIVE_A)
        manifest = dict(MANIFEST_A)
        del manifest["partuuid"]
        with self.assertRaises(UnresolvableField) as cm:
            assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertEqual(str(cm.exception), "unresolvable identity field: partuuid")

    def test_unresolvable_observed_serial(self):
        blank = FakeBlock(
            path="/dev/sda1",
            serial="",
            partuuid="PART-A",
            fs_uuid="FS-A",
            major=8,
            minor=1,
            ro=True,
        )
        res = resolver(blank)
        with self.assertRaises(UnresolvableField) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(str(cm.exception), "unresolvable identity field: serial")
        self.assertIn("open", res.call_names())

    def test_unresolvable_observed_fs_uuid(self):
        blank = FakeBlock(
            path="/dev/sda1",
            serial="SERIAL-A",
            partuuid="PART-A",
            fs_uuid="",
            major=8,
            minor=1,
            ro=True,
        )
        res = resolver(blank)
        with self.assertRaises(UnresolvableField) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(str(cm.exception), "unresolvable identity field: fs_uuid")

    def test_majmin_mismatch_independent_of_path(self):
        lying = FakeBlock(
            path="/dev/sda1",
            serial="SERIAL-A",
            partuuid="PART-A",
            fs_uuid="FS-A",
            major=8,
            minor=1,
            ro=True,
        )
        res = resolver(lying)

        orig = res.identity_from_fd

        def shifted(fd):
            ident = orig(fd)
            ident["minor"] = 99
            return ident

        res.identity_from_fd = shifted  # type: ignore[method-assign]
        with self.assertRaises(IdentityMismatch) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(cm.exception.field, "major:minor")
        self.assertEqual(str(cm.exception), "identity mismatch: major:minor")

    def test_not_readonly_on_verified_fd(self):
        writable = FakeBlock(
            path="/dev/sda1",
            serial="SERIAL-A",
            partuuid="PART-A",
            fs_uuid="FS-A",
            major=8,
            minor=1,
            ro=False,
        )
        res = resolver(writable)
        with self.assertRaises(NotReadOnly) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(str(cm.exception), "device is not read-only")
        self.assertIn("identity_from_fd", res.call_names())
        self.assertIn("is_read_only", res.call_names())
        fds = [arg for name, arg in res.calls if name == "is_read_only"]
        self.assertEqual(len(fds), 1)
        self.assertIn("close", res.call_names())
        self.assertTrue(res.closed(fds[0]))

    def test_ambiguous_serial_two_nodes(self):
        twin = FakeBlock(
            path="/dev/sdb1",
            serial="SERIAL-A",
            partuuid="PART-OTHER",
            fs_uuid="FS-OTHER",
            major=8,
            minor=17,
            ro=True,
        )
        res = resolver(DRIVE_A, twin)
        with self.assertRaises(AmbiguousSerial) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(cm.exception.serial, "SERIAL-A")
        self.assertEqual(
            str(cm.exception),
            "ambiguous serial: multiple devices share SERIAL-A",
        )

    def test_zero_serial_matches_is_ambiguous(self):
        res = resolver(DRIVE_A)
        res.devices_with_serial = lambda serial: []  # type: ignore[method-assign]
        with self.assertRaises(AmbiguousSerial) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertIn("ambiguous serial", str(cm.exception))

    def test_fingerprint_skipped_when_not_allowed(self):
        res = resolver(DRIVE_A)
        bound = assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertTrue(bound.fingerprint_skipped)
        self.assertEqual(bound.fingerprint_skip_reason, SKIP_NOT_ALLOWED)
        self.assertNotIn("fingerprint", res.call_names())

    def test_fingerprint_skipped_failing_even_if_allowed(self):
        res = resolver(DRIVE_A)
        manifest = dict(MANIFEST_A, media_class="failing", allow_fingerprint=True)
        bound = assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertTrue(bound.fingerprint_skipped)
        self.assertEqual(bound.fingerprint_skip_reason, SKIP_FAILING)
        self.assertNotIn("fingerprint", res.call_names())

    def test_fingerprint_skipped_unset_media_class(self):
        res = resolver(DRIVE_A)
        manifest = {
            "serial": "SERIAL-A",
            "partuuid": "PART-A",
            "fs_uuid": "FS-A",
        }
        bound = assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertTrue(bound.fingerprint_skipped)
        self.assertEqual(bound.fingerprint_skip_reason, SKIP_UNSET_CLASS)

    def test_fingerprint_runs_when_allowed_on_stable(self):
        res = resolver(DRIVE_A)
        manifest = dict(MANIFEST_A, allow_fingerprint=True)
        bound = assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertFalse(bound.fingerprint_skipped)
        self.assertIsNone(bound.fingerprint_skip_reason)
        self.assertEqual(bound.fingerprint, b"fake-fingerprint")
        self.assertIn("fingerprint", res.call_names())

    def test_usb_bridge_same_serial_does_not_trip_ambiguity(self):
        """Known gap: a bridge that enumerates as one node shares one serial."""
        bridge = FakeBlock(
            path="/dev/sda1",
            serial="SERIAL-A",
            partuuid="PART-A",
            fs_uuid="FS-A",
            major=8,
            minor=1,
            ro=True,
            usb_bridge=True,
        )
        res = resolver(bridge)
        manifest = dict(MANIFEST_A, allow_fingerprint=True)
        bound = assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertEqual(bound.serial, "SERIAL-A")
        self.assertTrue(bound.fingerprint_skipped)
        self.assertEqual(bound.fingerprint_skip_reason, SKIP_USB_BRIDGE)
        self.assertIn(SKIP_USB_BRIDGE, bound.warnings)
        self.assertNotIn("fingerprint", res.call_names())

    def test_manifest_path_key_is_ignored(self):
        res = resolver(DRIVE_A, DRIVE_B)
        manifest = dict(MANIFEST_A, path="/dev/sdb1")
        bound = assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertEqual(bound.serial, "SERIAL-A")

    def test_stale_manifest_path_does_not_bind_wrong_disk(self):
        swapped = FakeBlock(
            path="/dev/sda1",
            serial="SERIAL-B",
            partuuid="PART-B",
            fs_uuid="FS-B",
            major=8,
            minor=1,
            ro=True,
        )
        res = resolver(swapped, DRIVE_B)
        manifest = dict(MANIFEST_A, path="/dev/sda1")
        with self.assertRaises(IdentityMismatch) as cm:
            assert_bound("/dev/sda1", manifest, resolver=res)
        self.assertEqual(str(cm.exception), "identity mismatch: serial")

    def test_missing_resolver(self):
        with self.assertRaises(TypeError):
            assert_bound("/dev/sda1", MANIFEST_A)

    def test_none_resolver(self):
        with self.assertRaises(BindError) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=None)
        self.assertEqual(str(cm.exception), "no identity resolver")

    def test_volumes_refused_before_syscall(self):
        with self.assertRaises(BindError) as cm:
            open_device_readonly("/Volumes/exhibit")
        self.assertEqual(str(cm.exception), MSG_VOLUMES)
        with self.assertRaises(BindError) as cm:
            open_device_readonly("/Volumes")
        self.assertEqual(str(cm.exception), MSG_VOLUMES)

    def test_open_device_readonly_regular_file_not_host_dev(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "regular")
            Path(path).write_bytes(b"x")
            fd = open_device_readonly(path)
            try:
                self.assertGreaterEqual(fd, 0)
                self.assertEqual(os.read(fd, 1), b"x")
            finally:
                os.close(fd)

    def test_as_log_reports_fingerprint_skip(self):
        res = resolver(DRIVE_A)
        bound = assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        payload = bound.as_log()
        self.assertTrue(payload["fingerprint_skipped"])
        self.assertEqual(payload["fingerprint_skip_reason"], SKIP_NOT_ALLOWED)

    def test_context_manager_yields_same_fd(self):
        res = resolver(DRIVE_A)
        with assert_bound("/dev/sda1", MANIFEST_A, resolver=res) as bound:
            self.assertGreaterEqual(bound.fd, 0)


class PermissionShapedContrastTests(unittest.TestCase):
    def test_readonly_exists_is_not_identity(self):
        wrong = FakeBlock(
            path="/dev/sda1",
            serial="SERIAL-B",
            partuuid="PART-B",
            fs_uuid="FS-B",
            major=8,
            minor=1,
            ro=True,
        )
        self.assertTrue(wrong.ro)
        self.assertTrue(wrong.path.startswith("/dev/"))
        res = resolver(wrong, DRIVE_B)
        with self.assertRaises(IdentityMismatch) as cm:
            assert_bound("/dev/sda1", MANIFEST_A, resolver=res)
        self.assertEqual(str(cm.exception), "identity mismatch: serial")


if __name__ == "__main__":
    unittest.main()
