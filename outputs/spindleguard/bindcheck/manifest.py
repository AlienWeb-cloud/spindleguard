# SPDX-License-Identifier: GPL-2.0-or-later
"""Logged, explicit identity-manifest rotation.

Re-partitioning invalidates a manifest. The temptation is to edit the JSON
in place so the job starts again. This module will not overwrite an existing
manifest path. It writes a new generation file and an append-only audit line.

assert_bound() has no update=True escape hatch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .bind import REQUIRED_FIELDS, BindError, UnresolvableField, _present

MSG_NO_REASON = "manifest rotation requires a non-empty reason"
MSG_OUT_EXISTS = "refuses to overwrite existing manifest path"
MSG_NO_CHANGE = "observed identity matches the current manifest; no rotation"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(manifest: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(manifest), sort_keys=True, separators=(",", ":")).encode()


def identity_fields(manifest: Mapping[str, Any]) -> dict[str, str]:
    out = {}
    for field in REQUIRED_FIELDS:
        if not _present(manifest.get(field)):
            raise UnresolvableField(field)
        out[field] = str(manifest[field])
    return out


def fields_changed(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[str]:
    a = identity_fields(old)
    b = identity_fields(new)
    return [field for field in REQUIRED_FIELDS if a[field] != b[field]]


def rotate_manifest(
    old: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    reason: str,
    out_path: str | Path,
    audit_path: str | Path,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a new generation. Never deletes or overwrites `out_path`."""
    if not isinstance(reason, str) or not reason.strip():
        raise BindError(MSG_NO_REASON)
    dest = Path(out_path)
    if dest.exists():
        raise BindError(MSG_OUT_EXISTS)
    changed = fields_changed(old, observed)
    if not changed:
        raise BindError(MSG_NO_CHANGE)
    generation = int(old.get("generation") or 1) + 1
    new_manifest: dict[str, Any] = {
        "generation": generation,
        "serial": str(observed["serial"]),
        "partuuid": str(observed["partuuid"]),
        "fs_uuid": str(observed["fs_uuid"]),
        "media_class": observed.get("media_class", old.get("media_class")),
        "allow_fingerprint": bool(
            observed.get("allow_fingerprint", old.get("allow_fingerprint", False))
        ),
        "rotated_from_generation": int(old.get("generation") or 1),
        "rotation_reason": reason.strip(),
    }
    if extra:
        for key, value in extra.items():
            if key not in new_manifest:
                new_manifest[key] = value
    payload = json.dumps(new_manifest, indent=2, sort_keys=True) + "\n"
    encoded = payload.encode()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(encoded)
    audit = {
        "event": "manifest-rotate",
        "reason": reason.strip(),
        "from_generation": int(old.get("generation") or 1),
        "to_generation": generation,
        "fields_changed": changed,
        "old_sha256": _sha256_bytes(_canonical(old)),
        "new_sha256": _sha256_bytes(encoded),
        "out_path": str(dest),
    }
    audit_file = Path(audit_path)
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with audit_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, sort_keys=True) + "\n")
    return new_manifest
