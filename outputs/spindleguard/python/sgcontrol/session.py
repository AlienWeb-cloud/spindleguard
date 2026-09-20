# SPDX-License-Identifier: GPL-2.0-or-later
"""Retained disposable UI sessions. Never deletes files."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .policy import MARKER_NAME, PolicyError, check_host_paths, check_observe_path, check_session_parent

PAYLOAD_CYCLE = bytes(range(256))


def default_parent(project_root: Path) -> Path:
    env = os.environ.get("SPINDLEGUARD_SESSION_PARENT")
    if env:
        parent = Path(env)
        check_session_parent(str(parent))
        parent.mkdir(parents=True, exist_ok=True)
        return parent
    work = Path(project_root) / "work"
    try:
        work.mkdir(parents=True, exist_ok=True)
        if os.access(work, os.W_OK):
            return work
    except OSError:
        pass
    if sys.platform == "darwin":
        parent = Path.home() / "Library" / "Application Support" / "SpindleGuard" / "sessions"
    else:
        parent = Path.home() / ".spindleguard" / "sessions"
    check_session_parent(str(parent))
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def create_session(parent: Path) -> dict[str, Any]:
    check_session_parent(str(parent))
    stamp = time.time_ns()
    root = Path(parent) / f"ui-session-{stamp}"
    source = root / "source"
    mount = root / "mount"
    workspace = source / "Workspace"
    source.mkdir(parents=True)
    mount.mkdir()
    workspace.mkdir()
    (source / MARKER_NAME).write_text("disposable test data\n", encoding="utf-8")
    (workspace / "existing.txt").write_text("before\n", encoding="utf-8")
    (workspace / "notes.txt").write_text(
        "Write through the mount only under /Workspace.\n", encoding="utf-8"
    )
    (source / "second.txt").write_text("second operation\n", encoding="utf-8")
    (source / "large.bin").write_bytes(PAYLOAD_CYCLE * 1024)
    log = root / "broker.jsonl"
    log.write_text("", encoding="utf-8")
    record = {
        "session": str(root),
        "source": str(source),
        "mount": str(mount),
        "log": str(log),
        "write_prefix": "/Workspace",
        "created_ns": stamp,
        "retained": True,
        "deletion_bucket": False,
    }
    (root / "session.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def load_session(path: Path) -> dict[str, Any]:
    check_observe_path(str(path))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("session", "source", "mount", "log"):
        if key not in data:
            raise PolicyError(f"session file missing {key}")
    check_host_paths(data["source"], data["mount"])
    check_observe_path(data["log"])
    check_observe_path(data["session"])
    data["retained"] = True
    data["deletion_bucket"] = False
    return data


def list_sessions(parent: Path) -> dict[str, Any]:
    check_session_parent(str(parent))
    root = Path(parent)
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("ui-session-*")):
            marker = path / "session.json"
            if not marker.is_file():
                continue
            try:
                items.append(load_session(marker))
            except (PolicyError, OSError, json.JSONDecodeError, KeyError):
                continue
    return {
        "parent": str(root),
        "sessions": items,
        "retained": True,
        "deletion_buckets": False,
        "deletes": False,
        "note": "Prototype retains sessions. There is no deletion bucket.",
    }
