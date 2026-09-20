# SPDX-License-Identifier: GPL-2.0-or-later
"""Host capability check. Does not mount and does not open /dev."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any


FUSE_T_DYLIB = "/usr/local/lib/libfuse-t.dylib"
FUSE_T_HEADER = "/usr/local/include/fuse/fuse.h"


def which(name: str) -> str | None:
    return shutil.which(name)


def doctor(project_root: Path) -> dict[str, Any]:
    root = Path(project_root)
    binary = root / "build" / "spindleguard"
    helpers = root.parent / "Helpers" / "spindleguard"
    broker = None
    for candidate in (binary, helpers, Path("/usr/local/bin/spindleguard")):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            broker = str(candidate)
            break
    python = sys.executable
    fuse = Path(FUSE_T_DYLIB).is_file()
    header = Path(FUSE_T_HEADER).is_file()
    darwin = sys.platform == "darwin"
    problems = []
    if not darwin:
        problems.append("native app and FUSE-T mount require macOS")
    if not fuse:
        problems.append(f"missing {FUSE_T_DYLIB}")
    if broker is None:
        problems.append("broker binary not built (run make)")
    if which("python3") is None and not python:
        problems.append("python3 not found")
    return {
        "os": sys.platform,
        "darwin": darwin,
        "python": python,
        "python3": which("python3"),
        "clang": which("clang"),
        "make": which("make"),
        "swiftc": which("swiftc"),
        "broker": broker,
        "fuse_t_dylib": fuse,
        "fuse_t_header": header,
        "umount": "/sbin/umount" if Path("/sbin/umount").is_file() else None,
        "can_mount": bool(darwin and fuse and broker),
        "can_build_app": bool(darwin and which("swiftc")),
        "problems": problems,
        "project_root": str(root),
    }
