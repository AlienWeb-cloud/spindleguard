# SPDX-License-Identifier: GPL-2.0-or-later
"""One-command host setup. Does not mount, does not open /dev, does not delete."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .doctor import FUSE_DOCS, FUSE_INSTALL, doctor
from .policy import PolicyError, check_session_parent
from .session import create_session, default_parent

MSG_FUSE_YES = "setup --install-fuse requires --yes"
MSG_FUSE_MAC = "FUSE-T install requires macOS"
MSG_FUSE_BREW = "brew not found; install Homebrew, then: " + FUSE_INSTALL


def _step(name: str, ok: bool, detail: str, command: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"name": name, "ok": ok, "detail": detail}
    if command:
        item["command"] = command
    return item


def setup(
    project_root: Path,
    *,
    dry_run: bool = False,
    install_fuse: bool = False,
    yes: bool = False,
    create_session_flag: bool = False,
    session_parent: Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    info = doctor(root)
    steps: list[dict[str, Any]] = []
    errors: list[str] = []

    steps.append(_step("python", True, info["python"] or "missing"))
    steps.append(
        _step(
            "macos",
            bool(info["darwin"]),
            "darwin" if info["darwin"] else "not macOS; native app and mounts are unavailable",
        )
    )
    steps.append(
        _step(
            "fuse-t",
            bool(info["fuse_t_dylib"]),
            "present" if info["fuse_t_dylib"] else f"missing; install with: {FUSE_INSTALL}",
            None if info["fuse_t_dylib"] else FUSE_INSTALL,
        )
    )

    if install_fuse:
        if not yes:
            raise PolicyError(MSG_FUSE_YES)
        if not info["darwin"]:
            raise PolicyError(MSG_FUSE_MAC)
        brew = info.get("brew")
        if not brew:
            raise PolicyError(MSG_FUSE_BREW)
        cmd = [brew, "install", "macos-fuse-t/homebrew-cask/fuse-t"]
        steps.append(_step("install-fuse", True, "planned" if dry_run else "running", " ".join(cmd)))
        if not dry_run:
            result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
            if result.returncode != 0:
                errors.append(result.stderr.strip() or "brew install failed")
                steps[-1]["ok"] = False
            info = doctor(root)

    if info["darwin"] and info["fuse_t_dylib"] and info["clang"] and info["make"]:
        cmd = [info["make"], "-C", str(root)]
        steps.append(_step("build-broker", True, "planned" if dry_run else "make", " ".join(cmd)))
        if not dry_run:
            result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
            if result.returncode != 0:
                errors.append(result.stderr.strip() or result.stdout.strip() or "make failed")
                steps[-1]["ok"] = False
            info = doctor(root)
    else:
        steps.append(
            _step(
                "build-broker",
                False,
                "skipped (need macOS + FUSE-T + clang + make)",
                "make",
            )
        )

    if info["darwin"] and info["swiftc"] and info["make"]:
        cmd = [info["make"], "-C", str(root), "app"]
        steps.append(_step("build-app", True, "planned" if dry_run else "make app", " ".join(cmd)))
        if not dry_run:
            result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
            if result.returncode != 0:
                errors.append(result.stderr.strip() or result.stdout.strip() or "make app failed")
                steps[-1]["ok"] = False
            info = doctor(root)
    else:
        steps.append(
            _step(
                "build-app",
                False,
                "skipped (need macOS + swiftc + make)",
                "make app",
            )
        )

    session = None
    if create_session_flag:
        parent = Path(session_parent) if session_parent else default_parent(root)
        check_session_parent(str(parent))
        steps.append(_step("session", True, "planned" if dry_run else str(parent)))
        if not dry_run:
            session = create_session(parent)
    else:
        steps.append(_step("session", True, "not requested"))

    info = doctor(root)
    next_steps = list(info.get("next") or [])
    if not info["darwin"]:
        next_steps = ["use a Mac for make app and mounts", "./sg verify --quick"]
    return {
        "dry_run": dry_run,
        "ok": not errors,
        "can_mount": info["can_mount"],
        "can_build_app": info["can_build_app"],
        "fuse_install": FUSE_INSTALL,
        "fuse_docs": FUSE_DOCS,
        "next": next_steps,
        "steps": steps,
        "errors": errors,
        "doctor": info,
        "session": session,
        "open": "open SpindleGuard.app" if info.get("app_bundle") else "./sg setup",
    }
