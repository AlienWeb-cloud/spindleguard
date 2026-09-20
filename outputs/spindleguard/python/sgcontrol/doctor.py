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
FUSE_INSTALL = "brew install macos-fuse-t/homebrew-cask/fuse-t"
FUSE_DOCS = "https://github.com/macos-fuse-t/fuse-t"
CLT_INSTALL = "xcode-select --install"


def which(name: str) -> str | None:
    return shutil.which(name)


def _check(cid: str, ok: bool, label: str, fix: str = "") -> dict[str, Any]:
    return {"id": cid, "ok": ok, "label": label, "fix": fix}


def _broker_candidates(root: Path) -> tuple[Path, ...]:
    return (
        root / "build" / "spindleguard",
        root / "SpindleGuard.app" / "Contents" / "Helpers" / "spindleguard",
        root.parent / "Helpers" / "spindleguard",
        Path("/usr/local/bin/spindleguard"),
    )


def doctor(project_root: Path) -> dict[str, Any]:
    root = Path(project_root)
    broker = None
    for candidate in _broker_candidates(root):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            broker = str(candidate)
            break
    python = sys.executable
    fuse = Path(FUSE_T_DYLIB).is_file()
    header = Path(FUSE_T_HEADER).is_file()
    darwin = sys.platform == "darwin"
    clang = which("clang")
    make = which("make")
    swiftc = which("swiftc")
    brew = which("brew")
    app_bundle = (root / "SpindleGuard.app").is_dir()
    python3 = which("python3")
    sg_cli = (root / "sg").is_file()
    checks = [
        _check("python", bool(python or python3), f"Python ({python or python3 or 'missing'})"),
        _check("sg", sg_cli, "sg CLI", "checkout the project"),
        _check("darwin", darwin, "macOS host", "use a Mac for make app and mounts"),
        _check("fuse_t", fuse, "FUSE-T runtime", FUSE_INSTALL),
        _check("fuse_headers", header, "FUSE-T headers", FUSE_INSTALL),
        _check("clang", bool(clang), "clang", CLT_INSTALL),
        _check("make", bool(make), "make", CLT_INSTALL),
        _check("swiftc", bool(swiftc), "swiftc (native app)", CLT_INSTALL),
        _check("brew", bool(brew) or not darwin, "Homebrew (FUSE-T install)", "https://brew.sh"),
        _check("broker", broker is not None, "broker binary", "./sg setup  or  make"),
        _check("app", app_bundle or not darwin, "SpindleGuard.app", "make app"),
    ]
    problems = []
    if not darwin:
        problems.append("native app and FUSE-T mount require macOS")
    if not fuse:
        problems.append(f"missing {FUSE_T_DYLIB}; {FUSE_INSTALL}")
    if broker is None:
        problems.append("broker binary not built; run ./sg setup or make")
    if python3 is None and not python:
        problems.append("python3 not found")
    nxt: list[str] = []
    if not darwin:
        nxt = ["use a Mac for make app and mounts", "./sg verify --quick"]
    elif not fuse:
        nxt = [FUSE_INSTALL, "docs: " + FUSE_DOCS, "./sg setup"]
    elif broker is None:
        nxt = ["./sg setup", "make"]
    elif not app_bundle:
        nxt = ["make app", "open SpindleGuard.app"]
    else:
        nxt = ["open SpindleGuard.app", "./sg app", "New Session in the UI, then Start"]
    return {
        "os": sys.platform,
        "darwin": darwin,
        "python": python,
        "python3": python3,
        "clang": clang,
        "make": make,
        "swiftc": swiftc,
        "brew": brew,
        "broker": broker,
        "fuse_t_dylib": fuse,
        "fuse_t_header": header,
        "umount": "/sbin/umount" if Path("/sbin/umount").is_file() else None,
        "can_mount": bool(darwin and fuse and broker),
        "can_build_app": bool(darwin and swiftc),
        "app_bundle": app_bundle,
        "problems": problems,
        "checks": checks,
        "next": nxt,
        "fuse_install": FUSE_INSTALL,
        "fuse_docs": FUSE_DOCS,
        "project_root": str(root),
        "ready_for_ui": bool(python or python3) and sg_cli,
    }
