# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-path policy for the broker and native app.

Matches the C daemon's /Volumes and disjoint checks, and is slightly
stricter on a bare `/Volumes` path (the UI refuses it before spawn).
The C/Python /Volumes duplication is deliberate; this is a third copy
for the Mac app and `sg`, not a relaxation of either guard.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

VOLUMES_MSG = "Prototype refuses /Volumes paths. Use disposable directories."
DISJOINT_MSG = "Source and mount must be disjoint."
MARKER_MSG = "Missing disposable test root marker."
PREFIX_MISSING_MSG = "Write prefix must be an existing safe test directory."
PREFIX_SHAPE_MSG = "Write prefix is invalid."
EMPTY_MSG = "Source and mount paths are required."
DEV_MSG = "Prototype refuses /dev paths. Use disposable directories."
MARKER_NAME = ".spindleguard-test-root"


class PolicyError(ValueError):
    """Fail-closed path policy refusal."""


def is_volumes_path(path: str) -> bool:
    if not path:
        return False
    if path == "/Volumes" or path.startswith("/Volumes/"):
        return True
    try:
        resolved = str(Path(path).resolve())
    except OSError:
        resolved = path
    return resolved == "/Volumes" or resolved.startswith("/Volumes/")


def is_dev_path(path: str) -> bool:
    if not path:
        return False
    if path == "/dev" or path.startswith("/dev/"):
        return True
    try:
        resolved = str(Path(path).resolve())
    except OSError:
        resolved = path
    return resolved == "/dev" or resolved.startswith("/dev/")


def _norm(path: str) -> str:
    try:
        p = Path(path)
        if p.exists():
            return str(p.resolve())
    except OSError:
        pass
    return path


def are_disjoint(source: str, mount: str) -> bool:
    a = _norm(source)
    b = _norm(mount)
    n = len(a)
    m = len(b)
    if not n or not m:
        return False
    source_is_under_mount = a.startswith(b) and (len(a) == m or a[m] == "/")
    mount_is_under_source = b.startswith(a) and (len(b) == n or b[n] == "/")
    return not source_is_under_mount and not mount_is_under_source


def write_prefix_shape(prefix: str) -> bool:
    if not prefix or prefix[0] != "/" or len(prefix) < 2:
        return False
    if ".." in prefix:
        return False
    if prefix.endswith("/"):
        return False
    return True


def check_host_paths(source: str, mount: str) -> None:
    if not source or not mount:
        raise PolicyError(EMPTY_MSG)
    if is_volumes_path(source) or is_volumes_path(mount):
        raise PolicyError(VOLUMES_MSG)
    if is_dev_path(source) or is_dev_path(mount):
        raise PolicyError(DEV_MSG)
    if not are_disjoint(source, mount):
        raise PolicyError(DISJOINT_MSG)


def check_session_parent(parent: str) -> None:
    if not parent:
        raise PolicyError(EMPTY_MSG)
    if is_volumes_path(parent):
        raise PolicyError(VOLUMES_MSG)
    if is_dev_path(parent):
        raise PolicyError(DEV_MSG)


def check_observe_path(path: str) -> None:
    if not path:
        raise PolicyError(EMPTY_MSG)
    if is_volumes_path(path):
        raise PolicyError(VOLUMES_MSG)
    if is_dev_path(path):
        raise PolicyError(DEV_MSG)


def check_marker(source: str) -> None:
    marker = Path(source) / MARKER_NAME
    if not marker.is_file():
        raise PolicyError(MARKER_MSG)


def check_write_prefix(source: str, prefix: Optional[str]) -> None:
    if prefix in (None, "", "-"):
        return
    if not write_prefix_shape(prefix):
        raise PolicyError(PREFIX_SHAPE_MSG)
    target = Path(source) / prefix.lstrip("/")
    if not target.is_dir():
        raise PolicyError(PREFIX_MISSING_MSG)


def check(
    source: str,
    mount: str,
    write_prefix: Optional[str] = None,
    *,
    require_marker: bool = True,
) -> None:
    check_host_paths(source, mount)
    src = Path(source)
    mnt = Path(mount)
    if require_marker and src.is_dir():
        check_marker(str(src))
    if write_prefix not in (None, "", "-") and src.is_dir():
        check_write_prefix(str(src), write_prefix)
    if src.exists() and not src.is_dir():
        raise PolicyError("Source must be a directory.")
    if mnt.exists() and not mnt.is_dir():
        raise PolicyError("Mount must be a directory.")
