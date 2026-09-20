# SPDX-License-Identifier: GPL-2.0-or-later
"""Retained disposable UI sessions: active, bucket, and purged lists.

Active sessions stay on disk. Move them into <parent>/bucket/, then into
<parent>/purged/. Destroy unlinks only ui-session-* directories that are
already in the purged list, and only with --yes. /Volumes and /dev are
refused.
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
PURGED_DIR = "purged"
LANE_ACTIVE = "active"
LANE_BUCKET = "bucket"
LANE_PURGED = "purged"
SESSION_NAME_RE = re.compile(r"^ui-session-\d+$")
MSG_DESTROY_YES = "session-destroy requires --yes"
MSG_NOT_SESSION = "not a disposable ui-session directory"
MSG_NOT_IN_BUCKET = "purge only accepts sessions already in the bucket"
MSG_NOT_PURGED = "destroy only deletes sessions already in the purged list"
MSG_ALREADY_BUCKETED = "session is already in the bucket"
MSG_ALREADY_PURGED = "session is already in the purged list"
MSG_NOT_BUCKETED = "session is not in the bucket"
MSG_NOT_STAGED = "session is not in the bucket or the purged list"
MSG_NOT_ACTIVE = "only an active session can be moved to the bucket"
MSG_NOT_UNDER_PARENT = "session must be under the session parent"
MSG_NAME_COLLISION = "a session with that name already exists at the destination"
MSG_PURGE_YES = MSG_DESTROY_YES


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


def purge_root(parent: Path) -> Path:
    return Path(parent) / PURGED_DIR


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
        "purged": False,
        "lane": LANE_ACTIVE,
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


def infer_parent(session: Path) -> Path:
    session = _session_dir(session)
    if session.parent.name in (BUCKET_DIR, PURGED_DIR):
        return session.parent.parent
    return session.parent


def _lanes(parent: Path) -> dict[str, Path]:
    parent_res = Path(parent).resolve()
    return {
        LANE_ACTIVE: parent_res,
        LANE_BUCKET: bucket_root(parent_res).resolve(),
        LANE_PURGED: purge_root(parent_res).resolve(),
    }


def _lane(session: Path, parent: Path) -> str:
    parent_res = Path(parent).resolve()
    sess = session.resolve()
    for name, root in _lanes(parent_res).items():
        if sess.parent == root:
            return name
    raise PolicyError(MSG_NOT_UNDER_PARENT)


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
    allowed = set(_lanes(parent_res).values())
    if sess_res in allowed:
        raise PolicyError(MSG_NOT_SESSION)
    if sess_res.parent not in allowed:
        raise PolicyError(MSG_NOT_UNDER_PARENT)
    return sess_res


def _flags(lane: str) -> dict[str, Any]:
    return {
        "lane": lane,
        "retained": lane == LANE_ACTIVE,
        "deletion_bucket": lane == LANE_BUCKET,
        "purged": lane == LANE_PURGED,
    }


def _rewrite_record(session: Path, parent: Path) -> dict[str, Any]:
    marker = session / "session.json"
    data = json.loads(marker.read_text(encoding="utf-8"))
    data["session"] = str(session)
    data["source"] = str(session / "source")
    data["mount"] = str(session / "mount")
    data["log"] = str(session / "broker.jsonl")
    data.update(_flags(_lane(session, parent)))
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
    name = session_dir.parent.name
    lane = LANE_PURGED if name == PURGED_DIR else LANE_BUCKET if name == BUCKET_DIR else LANE_ACTIVE
    data["session"] = str(session_dir)
    data.update(_flags(lane))
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
        "purged_dir": str(purge_root(root)),
        "sessions": _collect(root),
        "bucket": _collect(bucket_root(root)),
        "purged": _collect(purge_root(root)),
        "retained": True,
        "deletion_buckets": True,
        "deletes": True,
        "deletes_active": False,
        "note": "Three lists: active, bucket, purged. Destroy only from purged, with --yes.",
    }


def _move_lane(parent: Path, session: Path, dest_lane: str, action: str) -> dict[str, Any]:
    sess = _require_ui_session(session, parent)
    dest_dir = _lanes(parent)[dest_lane]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / sess.name
    if dest.exists():
        raise PolicyError(MSG_NAME_COLLISION)
    shutil.move(str(sess), str(dest))
    record = _rewrite_record(dest, parent)
    record["ok"] = True
    record["action"] = action
    return record


def bucket_session(parent: Path, session: Path) -> dict[str, Any]:
    sess = _require_ui_session(session, parent)
    lane = _lane(sess, parent)
    if lane == LANE_BUCKET:
        raise PolicyError(MSG_ALREADY_BUCKETED)
    if lane != LANE_ACTIVE:
        raise PolicyError(MSG_NOT_ACTIVE)
    return _move_lane(parent, sess, LANE_BUCKET, "bucket")


def restore_session(parent: Path, session: Path) -> dict[str, Any]:
    sess = _require_ui_session(session, parent)
    lane = _lane(sess, parent)
    if lane == LANE_BUCKET:
        return _move_lane(parent, sess, LANE_ACTIVE, "restore")
    if lane == LANE_PURGED:
        return _move_lane(parent, sess, LANE_BUCKET, "restore")
    raise PolicyError(MSG_NOT_STAGED)


def purge_sessions(
    parent: Path,
    session: Optional[Path] = None,
    *,
    purge_all: bool = False,
    yes: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Move bucketed sessions into the purged list. Does not unlink files."""
    del yes
    check_session_parent(str(parent))
    records: list[dict[str, Any]] = []
    moved: list[str] = []
    if purge_all:
        targets = [Path(item["session"]) for item in _collect(bucket_root(parent))]
    elif session is not None:
        targets = [session]
    else:
        raise PolicyError("session-purge requires --session or --all")
    for target in targets:
        sess = _require_ui_session(target, parent)
        if _lane(sess, parent) != LANE_BUCKET:
            raise PolicyError(MSG_NOT_IN_BUCKET)
        if dry_run:
            moved.append(str(sess))
            continue
        record = _move_lane(parent, sess, LANE_PURGED, "purge")
        records.append(record)
        moved.append(record["session"])
    payload: dict[str, Any] = {
        "ok": True,
        "action": "purge",
        "dry_run": dry_run,
        "moved": moved,
        "count": len(moved),
        "parent": str(parent),
        "bucket_dir": str(bucket_root(parent)),
        "purged_dir": str(purge_root(parent)),
    }
    if len(records) == 1:
        payload.update(records[0])
        payload["moved"] = moved
        payload["count"] = 1
        payload["action"] = "purge"
        payload["ok"] = True
    return payload


def _destroy_one(parent: Path, session: Path, *, dry_run: bool) -> str:
    sess = _require_ui_session(session, parent)
    if _lane(sess, parent) != LANE_PURGED:
        raise PolicyError(MSG_NOT_PURGED)
    if dry_run:
        return str(sess)
    shutil.rmtree(sess)
    return str(sess)


def destroy_sessions(
    parent: Path,
    session: Optional[Path] = None,
    *,
    destroy_all: bool = False,
    yes: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    check_session_parent(str(parent))
    if not yes and not dry_run:
        raise PolicyError(MSG_DESTROY_YES)
    deleted: list[str] = []
    if destroy_all:
        for item in _collect(purge_root(parent)):
            deleted.append(_destroy_one(parent, Path(item["session"]), dry_run=dry_run))
    elif session is not None:
        deleted.append(_destroy_one(parent, session, dry_run=dry_run))
    else:
        raise PolicyError("session-destroy requires --session or --all")
    return {
        "ok": True,
        "action": "destroy",
        "dry_run": dry_run,
        "deleted": deleted,
        "count": len(deleted),
        "parent": str(parent),
        "purged_dir": str(purge_root(parent)),
    }
