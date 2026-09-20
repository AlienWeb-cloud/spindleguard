# SPDX-License-Identifier: GPL-2.0-or-later
"""Control-plane unittest runner.

SG_REQUIRE_FULL=1 turns skipped tests into failures. Does not run proof.py
(real mounts). Does not touch /Volumes or host /dev.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
PY = str(PROJECT / "python")
if PY not in sys.path:
    sys.path.insert(0, PY)

TESTS = Path(__file__).resolve().parent


class RequireFullResult(unittest.TextTestResult):
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if os.environ.get("SG_REQUIRE_FULL") == "1":
            try:
                raise AssertionError(f"skip treated as error: {reason}")
            except AssertionError:
                self.addFailure(test, sys.exc_info())


def control_suite():
    loader = unittest.TestLoader()
    return loader.discover(str(TESTS), pattern="test_*.py", top_level_dir=str(PROJECT))


def main():
    verbosity = 2
    runner = unittest.TextTestRunner(verbosity=verbosity, resultclass=RequireFullResult)
    result = runner.run(control_suite())
    files = sorted(p.name for p in TESTS.glob("test_*.py"))
    ran = result.testsRun
    failed = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    print(
        f"CONTROL: files={len(files)} tests={ran} fail={failed} skip={skipped} "
        f"exit={0 if result.wasSuccessful() else 1}",
        flush=True,
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
