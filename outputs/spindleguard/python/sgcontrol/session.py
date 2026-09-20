# SPDX-License-Identifier: GPL-2.0-or-later
"""Retained disposable UI sessions, plus a deletion bucket.

Active sessions stay on disk. Move them into <parent>/bucket/ first.
Purge unlinks only ui-session-* directories that are already in that
bucket, and only with --yes. /Volumes and /dev are refused.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Optional

from .policy import MARKER_NAME, PolicyError, check_host_paths, check_observe_path, check_session_parent

PAYLOAD_CYCLE = bytes(range(256))
BUCKET_DIR = "bucket"
SESSION_NAME_RE = re.compile(r"^ui-session-\d+$")
MSG_PURGE_YES = "session-purge requires --yes"
MSG_NOT_SESSION = "not a disposable ui-session directory"
MSG_NOT_IN_BUCKET = "purge only deletes sessions already in the bucket"
MSG_ALREADY_BUCKETED = "session is already in the bucket"
MSG_NOT_BUCKETED = "session is not in the bucket"
MSG_NOT_UNDER_PARENT = "session must be under the session parent"
MSG_NAME_COLLISION = "a session with that name already exists at the destination"


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


def bucket_root(parent: Path) -> Path:
    return Path(parent) / BUCKET_DIR


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


def _session_dir(path: Path) -> Path:
    p = Path(path)
    if p.name == "session.json":
        p = p.parent
    return p


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def infer_parent(session: Path) -> Path:
    session = _session_dir(session)
    if session.parent.name == BUCKET_DIR:
        return session.parent.parent
    return session.parent


def _in_bucket(session: Path, parent: Path) -> bool:
    return session.resolve().parent == bucket_root(parent).resolve()


def _require_ui_session(path: Path, parent: Path) -> Path:
    check_session_parent(str(parent))
    check_observe_path(str(path))
    session = _session_dir(path)
    check_observe_path(str(session))
    if not session.is_dir() or not SESSION_NAME_RE.match(session.name):
        raise PolicyError(MSG_NOT_SESSION)
    if not (session / "session.json").is_file():
        raise PolicyError(MSG_NOT_SESSION)
    parent_res = Path(parent).resolve()
    sess_res = session.resolve()
    if sess_res == parent_res or sess_res == bucket_root(parent_res).resolve():
        raise PolicyError(MSG_NOT_SESSION)
    if not _is_under(sess_res, parent_res):
        raise PolicyError(MSG_NOT_UNDER_PARENT)
    return sess_res


def _rewrite_record(session: Path, *, in_bucket: bool) -> dict[str, Any]:
    marker = session / "session.json"
    data = json.loads(marker.read_text(encoding="utf-8"))
    data["session"] = str(session)
    data["source"] = str(session / "source")
    data["mount"] = str(session / "mount")
    data["log"] = str(session / "broker.jsonl")
    data["retained"] = not in_bucket
    data["deletion_bucket"] = in_bucket
    marker.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def load_session(path: Path) -> dict[str, Any]:
    check_observe_path(str(path))
    marker = Path(path)
    if marker.is_dir():
        marker = marker / "session.json"
    data = json.loads(marker.read_text(encoding="utf-8"))
    for key in ("session", "source", "mount", "log"):
        if key not in data:
            raise PolicyError(f"session file missing {key}")
    check_host_paths(data["source"], data["mount"])
    check_observe_path(data["log"])
    check_observe_path(data["session"])
    session_dir = marker.parent
    bucketed = session_dir.parent.name == BUCKET_DIR
    data["session"] = str(session_dir)
    data["retained"] = not bucketed
    data["deletion_bucket"] = bucketed
    return data


def _collect(root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not root.is_dir():
        return items
    for path in sorted(root.glob("ui-session-*")):
        marker = path / "session.json"
        if not marker.is_file() or not SESSION_NAME_RE.match(path.name):
            continue
        try:
            items.append(load_session(marker))
        except (PolicyError, OSError, json.JSONDecodeError, KeyError):
            continue
    return items


def list_sessions(parent: Path) -> dict[str, Any]:
    check_session_parent(str(parent))
    root = Path(parent)
    return {
        "parent": str(root),
        "bucket_dir": str(bucket_root(root)),
        "sessions": _collect(root),
        "bucket": _collect(bucket_root(root)),
        "retained": True,
        "deletion_buckets": True,
        "deletes": True,
        "deletes_active": False,
        "note": "Active sessions stay on disk. Move to the bucket, then purge with --yes.",
    }


def bucket_session(parent: Path, session: Path) -> dict[str, Any]:
    sess = _require_ui_session(session, parent)
    if _in_bucket(sess, parent):
        raise PolicyError(MSG_ALREADY_BUCKETED)
    dest_dir = bucket_root(parent)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / sess.name
    if dest.exists():
        raise PolicyError(MSG_NAME_COLLISION)
    shutil.move(str(sess), str(dest))
    record = _rewrite_record(dest, in_bucket=True)
    record["ok"] = True
    record["action"] = "bucket"
    return record


def restore_session(parent: Path, session: Path) -> dict[str, Any]:
    sess = _require_ui_session(session, parent)
    if not _in_bucket(sess, parent):
        raise PolicyError(MSG_NOT_BUCKETED)
    dest = Path(parent) / sess.name
    if dest.exists():
        raise PolicyError(MSG_NAME_COLLISION)
    shutil.move(str(sess), str(dest))
    record = _rewrite_record(dest, in_bucket=False)
    record["ok"] = True
    record["action"] = "restore"
    return record


def _purge_one(parent: Path, session: Path, *, dry_run: bool) -> str:
    sess = _require_ui_session(session, parent)
    if not _in_bucket(sess, parent):
        raise PolicyError(MSG_NOT_IN_BUCKET)
    if dry_run:
        return str(sess)
    shutil.rmtree(sess)
    return str(sess)


def purge_sessions(
    parent: Path,
    session: Optional[Path] = None,
    *,
    purge_all: bool = False,
    yes: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    check_session_parent(str(parent))
    if not yes and not dry_run:
        raise PolicyError(MSG_PURGE_YES)
    deleted: list[str] = []
    if purge_all:
        for item in _collect(bucket_root(parent)):
            deleted.append(_purge_one(parent, Path(item["session"]), dry_run=dry_run))
    elif session is not None:
        deleted.append(_purge_one(parent, session, dry_run=dry_run))
    else:
        raise PolicyError("session-purge requires --session or --all")
    return {
        "ok": True,
        "action": "purge",
        "dry_run": dry_run,
        "deleted": deleted,
        "count": len(deleted),
        "parent": str(parent),
        "bucket_dir": str(bucket_root(parent)),
    }
