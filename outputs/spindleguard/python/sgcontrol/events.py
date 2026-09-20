# SPDX-License-Identifier: GPL-2.0-or-later
"""Queue JSONL helpers. Same event shape as the C daemon stderr."""
from __future__ import annotations

import json
from typing import Any, Iterable, Optional


def parse_line(line: str) -> Optional[dict[str, Any]]:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "event" not in data:
        return None
    return data


def load_events(text: str) -> list[dict[str, Any]]:
    return [e for line in text.splitlines() if (e := parse_line(line))]


def queue_snapshot(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    events = list(events)
    active = None
    pending = 0
    last_wait = 0.0
    starts = 0
    finishes = 0
    for e in events:
        kind = e.get("event")
        if kind == "start":
            active = {
                "ticket": e.get("ticket"),
                "op": e.get("op"),
                "file_tag": e.get("file_tag"),
            }
            starts += 1
        elif kind == "finish":
            active = None
            finishes += 1
        elif kind == "queued":
            pending = int(e.get("pending") or 0)
        wait = e.get("wait_ms")
        if isinstance(wait, (int, float)) and wait > last_wait:
            last_wait = float(wait)
    return {
        "active": active,
        "active_count": 0 if active is None else 1,
        "pending": pending,
        "starts": starts,
        "finishes": finishes,
        "last_wait_ms": last_wait,
        "events": len(events),
    }


def competing_wait(events: Iterable[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Return evidence that a later request waited behind an active one."""
    start: dict[Any, dict[str, Any]] = {}
    finish: dict[Any, dict[str, Any]] = {}
    queued: dict[Any, dict[str, Any]] = {}
    active: set[Any] = set()
    witnessed: list[tuple[Any, Any]] = []
    for e in events:
        t = e.get("ticket")
        kind = e.get("event")
        if kind == "queued":
            queued[t] = e
            if active:
                witnessed.append((next(iter(active)), t))
        elif kind == "start":
            start[t] = e
            active.add(t)
        elif kind == "finish":
            finish[t] = e
            active.discard(t)
    for a, b in witnessed:
        if a in finish and b in start:
            wait = float(start[b].get("wait_ms") or 0)
            if start[b]["time"] >= finish[a]["time"] and wait > 20:
                return {
                    "active_ticket": a,
                    "queued_ticket": b,
                    "queued_op": start[b].get("op"),
                    "wait_ms": wait,
                    "read_finish": finish[a]["time"],
                    "second_start": start[b]["time"],
                }
    return None
