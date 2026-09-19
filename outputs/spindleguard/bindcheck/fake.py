# SPDX-License-Identifier: GPL-2.0-or-later
"""In-memory block-device resolver. Never opens host /dev or /Volumes."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
import os
import stat


@dataclass
class FakeBlock:
    path: str
    serial: str
    partuuid: str
    fs_uuid: str
    major: int
    minor: int
    ro: bool = True
    usb_bridge: bool = False
    fingerprint: bytes = b"fake-fingerprint"


@dataclass
class FakeResolver:
    blocks: list[FakeBlock]
    calls: list[tuple[str, Any]] = field(default_factory=list)
    _fds: dict[int, FakeBlock] = field(default_factory=dict)
    _next_fd: int = 1000
    _closed: set[int] = field(default_factory=set)

    def _by_path(self) -> dict[str, FakeBlock]:
        return {b.path: b for b in self.blocks}

    def open(self, path: str) -> int:
        self.calls.append(("open", path))
        block = self._by_path().get(path)
        if block is None:
            raise FileNotFoundError(path)
        fd = self._next_fd
        self._next_fd += 1
        self._fds[fd] = block
        return fd

    def fstat(self, fd: int) -> Any:
        self.calls.append(("fstat", fd))
        block = self._fds[fd]
        return SimpleNamespace(
            st_rdev=os.makedev(block.major, block.minor),
            st_mode=stat.S_IFBLK | 0o400,
        )

    def close(self, fd: int) -> None:
        self.calls.append(("close", fd))
        self._fds.pop(fd, None)
        self._closed.add(fd)

    def identity_from_fd(self, fd: int) -> dict[str, Any]:
        self.calls.append(("identity_from_fd", fd))
        block = self._fds[fd]
        return {
            "serial": block.serial,
            "partuuid": block.partuuid,
            "fs_uuid": block.fs_uuid,
            "major": block.major,
            "minor": block.minor,
            "usb_bridge": block.usb_bridge,
        }

    def devices_with_serial(self, serial: str) -> list[FakeBlock]:
        self.calls.append(("devices_with_serial", serial))
        return [b for b in self.blocks if b.serial == serial]

    def is_read_only(self, fd: int) -> bool:
        self.calls.append(("is_read_only", fd))
        return bool(self._fds[fd].ro)

    def fingerprint(self, fd: int) -> bytes:
        self.calls.append(("fingerprint", fd))
        return self._fds[fd].fingerprint

    def closed(self, fd: int) -> bool:
        return fd in self._closed

    def call_names(self) -> list[str]:
        return [name for name, _ in self.calls]


def blocks_from_fixture(data: dict[str, Any]) -> list[FakeBlock]:
    out = []
    for raw in data.get("blocks") or []:
        out.append(
            FakeBlock(
                path=raw["path"],
                serial=raw["serial"],
                partuuid=raw["partuuid"],
                fs_uuid=raw["fs_uuid"],
                major=int(raw["major"]),
                minor=int(raw["minor"]),
                ro=bool(raw.get("ro", True)),
                usb_bridge=bool(raw.get("usb_bridge", False)),
                fingerprint=bytes(raw["fingerprint"], "utf-8")
                if isinstance(raw.get("fingerprint"), str)
                else raw.get("fingerprint") or b"fake-fingerprint",
            )
        )
    return out
