# SPDX-License-Identifier: GPL-2.0-or-later
"""Argv for the C broker. Does not spawn a mount by itself."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .policy import check


def broker_command(
    binary: str,
    source: str,
    mount: str,
    write_prefix: Optional[str] = None,
    delay_ms: Optional[int] = None,
    *,
    require_marker: bool = True,
) -> list[str]:
    check(source, mount, write_prefix, require_marker=require_marker)
    if delay_ms is not None and (delay_ms < 0 or delay_ms > 5000):
        raise ValueError("delay_ms must be 0..5000")
    cmd = [str(Path(binary)), source, mount]
    writable = write_prefix not in (None, "", "-")
    if writable or (delay_ms or 0) > 0:
        cmd.append(write_prefix if writable else "-")
    if (delay_ms or 0) > 0:
        cmd.append(str(int(delay_ms)))
    return cmd
