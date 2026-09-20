# SPDX-License-Identifier: GPL-2.0-or-later
"""Device-shaped open() outside bindcheck/ must fail the suite."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from bindcheck.scan import (
    STRUCTURAL_CANARY,
    c_violations,
    in_bindcheck,
    python_violations,
    scan_source,
    scan_tree,
)


class ScannerSnippetTests(unittest.TestCase):
    def test_canary_present_in_scanner_module(self):
        text = (PROJECT / "bindcheck" / "scan.py").read_text(encoding="utf-8")
        self.assertIn(STRUCTURAL_CANARY, text)
        self.assertIn("STRUCTURAL_CANARY_assert_bound", text)

    def test_flags_os_open_literal(self):
        src = 'import os\nos.open("/dev/sda1", os.O_RDONLY)\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(hits)
        self.assertTrue(
            any("os.open" in h.message or "device-shaped" in h.message for h in hits)
        )

    def test_flags_builtin_open_literal(self):
        src = 'open("/dev/nvme0n1p1", "rb")\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(any("device-shaped open()" in h.message for h in hits))

    def test_flags_concatenated_dev_prefix(self):
        src = 'name = "sda1"\nopen("/dev/" + name, "rb")\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(hits)

    def test_flags_fstring_dev(self):
        src = 'disk = "sdb1"\nopen(f"/dev/{disk}", "rb")\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(hits)

    def test_flags_join(self):
        src = 'import os\nopen(os.path.join("/dev", "sda1"), "rb")\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(hits)

    def test_flags_assigned_device_path(self):
        src = 'path = "/dev/disk0s1"\nopen(path, "rb")\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(hits)

    def test_flags_pathlib_open(self):
        src = 'from pathlib import Path\nPath("/dev/rdisk2").open("rb")\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(hits)

    def test_flags_os_open_variable_even_without_dev_shape(self):
        src = 'import os\npath = other\nos.open(path, os.O_RDONLY)\n'
        hits = python_violations(src, "tools/evil.py")
        self.assertTrue(any("os.open/os.openat outside bindcheck" in h.message for h in hits))

    def test_allows_regular_file_open(self):
        src = 'open("README.md", "r", encoding="utf-8")\n'
        self.assertEqual(python_violations(src, "tools/ok.py"), [])

    def test_allows_dev_null(self):
        src = 'open("/dev/null", "wb")\n'
        self.assertEqual(python_violations(src, "tools/ok.py"), [])

    def test_flags_c_open_of_dev(self):
        src = 'int fd = open("/dev/sda1", 0);\n'
        hits = c_violations(src, "src/evil.c")
        self.assertTrue(hits)

    def test_c_comment_is_not_a_hit(self):
        src = '// open("/dev/sda1", 0);\nint fd = open(source, 0);\n'
        self.assertEqual(c_violations(src, "src/ok.c"), [])

    def test_c_without_open_call_ignores_string(self):
        src = 'const char *msg = "/dev/sda1";\n'
        self.assertEqual(c_violations(src, "src/ok.c"), [])

    def test_macos_rdisk_is_device_shaped(self):
        src = 'open("/dev/rdisk0", "rb")\n'
        self.assertTrue(python_violations(src, "tools/evil.py"))


class LiveTreeTests(unittest.TestCase):
    def test_bindcheck_dir_is_allowlisted(self):
        self.assertTrue(in_bindcheck(PROJECT / "bindcheck" / "bind.py", PROJECT))
        self.assertFalse(in_bindcheck(PROJECT / "tools" / "topology.py", PROJECT))
        self.assertFalse(in_bindcheck(PROJECT / "tests" / "test_bindcheck.py", PROJECT))

    def test_current_tree_has_no_violations(self):
        hits = scan_tree(PROJECT)
        self.assertEqual(hits, [], [h.as_text() for h in hits])

    def test_scan_source_dispatches(self):
        self.assertTrue(scan_source('open("/dev/sda", "rb")\n', "x.py"))
        self.assertTrue(scan_source('open("/dev/sda", 0);\n', "x.c"))


if __name__ == "__main__":
    unittest.main()
