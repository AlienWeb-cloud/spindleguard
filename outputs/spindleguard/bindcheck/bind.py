# SPDX-License-Identifier: GPL-2.0-or-later
"""Identity binding for block devices.

Permission-shaped checks (exists? read-only? path allowed?) are not identity.
A Linux carve hardcoded to /dev/sda1 passed those checks after sda/sdb swapped
on reboot, then ran on the wrong disk.

assert_bound() is the only supported way to obtain a device descriptor:

  1. Refuse if there is no identity manifest.
  2. Open the given path to an fd (the path is untrusted after this).
  3. fstat that fd.
  4. Resolve serial / PARTUUID / FS-UUID independently from the fd.
  5. Compare major:minor of the fd against the independently resolved node.
  6. Compare resolved identity fields against the manifest.
  7. Refuse if two enumerated nodes share the serial.
  8. Re-assert read-only on the verified fd (not via the path).
  9. Return the fd holder. Never a path: a path lets the caller re-open (race).

Fingerprint sampling is off unless allow_fingerprint is set, and is skipped
for failing media even then. USB bridges that collapse sibling LUNs onto one
serial are a known gap: they do not always trip the ambiguity refusal. The
result records that fingerprint was skipped and why.

This module does not probe live hardware. Callers inject a Resolver.
Platform resolvers that open real device nodes belong in this package so the
structural test can treat any device-shaped open() elsewhere as a regression.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence


REQUIRED_FIELDS = ("serial", "partuuid", "fs_uuid")

MSG_NO_MANIFEST = "no identity manifest"
MSG_UNRESOLVABLE = "unresolvable identity field: {field}"
MSG_NOT_READONLY = "device is not read-only"
MSG_AMBIGUOUS = "ambiguous serial: multiple devices share {serial}"
MSG_MISMATCH = "identity mismatch: {field}"
MSG_NO_RESOLVER = "no identity resolver"
MSG_VOLUMES = "refuses /Volumes paths"
MSG_NO_PATH = "BoundDevice does not expose a path; reopen is a race"

SKIP_FAILING = "media_class=failing"
SKIP_NOT_ALLOWED = "allow_fingerprint is not set"
SKIP_UNSET_CLASS = "media_class unset; fingerprint skipped"
SKIP_USB_BRIDGE = (
    "usb bridge can hide sibling LUNs behind one serial; fingerprint skipped"
)


class BindError(Exception):
    """Fail-closed identity binding refusal."""


class NoManifest(BindError):
    def __init__(self) -> None:
        super().__init__(MSG_NO_MANIFEST)


class UnresolvableField(BindError):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(MSG_UNRESOLVABLE.format(field=field))


class NotReadOnly(BindError):
    def __init__(self) -> None:
        super().__init__(MSG_NOT_READONLY)


class AmbiguousSerial(BindError):
    def __init__(self, serial: str) -> None:
        self.serial = serial
        super().__init__(MSG_AMBIGUOUS.format(serial=serial))


class IdentityMismatch(BindError):
    def __init__(self, field: str, expected: Any = None, observed: Any = None) -> None:
        self.field = field
        self.expected = expected
        self.observed = observed
        super().__init__(MSG_MISMATCH.format(field=field))


class Resolver(Protocol):
    """Hardware/test seam. Methods receive fds, not paths, after open()."""

    def open(self, path: str) -> int: ...
    def fstat(self, fd: int) -> Any: ...
    def close(self, fd: int) -> None: ...
    def identity_from_fd(self, fd: int) -> Mapping[str, Any]: ...
    def devices_with_serial(self, serial: str) -> Sequence[Any]: ...
    def is_read_only(self, fd: int) -> bool: ...
    def fingerprint(self, fd: int) -> bytes: ...


class BoundDevice:
    """A verified device held by descriptor. The original path is not retained."""

    __slots__ = (
        "_fd",
        "_major",
        "_minor",
        "_serial",
        "_partuuid",
        "_fs_uuid",
        "_fingerprint",
        "_fingerprint_skipped",
        "_fingerprint_skip_reason",
        "_warnings",
    )

    def __init__(
        self,
        fd: int,
        *,
        major: int,
        minor: int,
        serial: str,
        partuuid: str,
        fs_uuid: str,
        fingerprint: Optional[bytes],
        fingerprint_skipped: bool,
        fingerprint_skip_reason: Optional[str],
        warnings: Sequence[str] = (),
    ) -> None:
        self._fd = fd
        self._major = major
        self._minor = minor
        self._serial = serial
        self._partuuid = partuuid
        self._fs_uuid = fs_uuid
        self._fingerprint = fingerprint
        self._fingerprint_skipped = fingerprint_skipped
        self._fingerprint_skip_reason = fingerprint_skip_reason
        self._warnings = tuple(warnings)

    @property
    def fd(self) -> int:
        return self._fd

    def fileno(self) -> int:
        return self._fd

    @property
    def major(self) -> int:
        return self._major

    @property
    def minor(self) -> int:
        return self._minor

    @property
    def serial(self) -> str:
        return self._serial

    @property
    def partuuid(self) -> str:
        return self._partuuid

    @property
    def fs_uuid(self) -> str:
        return self._fs_uuid

    @property
    def fingerprint(self) -> Optional[bytes]:
        return self._fingerprint

    @property
    def fingerprint_skipped(self) -> bool:
        return self._fingerprint_skipped

    @property
    def fingerprint_skip_reason(self) -> Optional[str]:
        return self._fingerprint_skip_reason

    @property
    def warnings(self) -> tuple[str, ...]:
        return self._warnings

    @property
    def path(self) -> str:
        raise AttributeError(MSG_NO_PATH)

    def close(self) -> None:
        """Drop the local fd number. The Resolver still owns the descriptor."""
        self._fd = -1

    def __enter__(self) -> "BoundDevice":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def as_log(self) -> dict[str, Any]:
        return {
            "fd": self._fd,
            "major": self._major,
            "minor": self._minor,
            "serial": self._serial,
            "partuuid": self._partuuid,
            "fs_uuid": self._fs_uuid,
            "fingerprint_skipped": self._fingerprint_skipped,
            "fingerprint_skip_reason": self._fingerprint_skip_reason,
            "warnings": list(self._warnings),
        }


def _present(value: Any) -> bool:
    return value is not None and str(value) != ""


def _require_manifest(manifest: Any) -> Mapping[str, Any]:
    # refusal:no-manifest
    if not isinstance(manifest, Mapping) or not manifest:
        raise NoManifest()
    return manifest


def _require_manifest_fields(manifest: Mapping[str, Any]) -> None:
    for field in REQUIRED_FIELDS:
        # refusal:unresolvable-manifest
        if not _present(manifest.get(field)):
            raise UnresolvableField(field)


def _require_resolver(resolver: Any) -> Resolver:
    if resolver is None:
        raise BindError(MSG_NO_RESOLVER)
    return resolver


def _dev_major_minor(st: Any) -> tuple[int, int]:
    import os
    rdev = getattr(st, "st_rdev", 0) or 0
    return os.major(rdev), os.minor(rdev)


def _require_observed_fields(ident: Mapping[str, Any]) -> None:
    for field in REQUIRED_FIELDS:
        # refusal:unresolvable-observed
        if not _present(ident.get(field)):
            raise UnresolvableField(field)


def _require_majmin(fd_maj: int, fd_min: int, ident: Mapping[str, Any]) -> None:
    try:
        ident_maj = int(ident["major"])
        ident_min = int(ident["minor"])
    except (KeyError, TypeError, ValueError):
        raise UnresolvableField("major:minor") from None
    # refusal:majmin
    if (ident_maj, ident_min) != (fd_maj, fd_min):
        raise IdentityMismatch("major:minor", (fd_maj, fd_min), (ident_maj, ident_min))


def _require_identity(manifest: Mapping[str, Any], ident: Mapping[str, Any]) -> None:
    for field in REQUIRED_FIELDS:
        expected = str(manifest[field])
        observed = str(ident[field])
        # refusal:identity-mismatch
        if observed != expected:
            raise IdentityMismatch(field, expected, observed)


def _require_unique_serial(resolver: Resolver, serial: str) -> None:
    matches = list(resolver.devices_with_serial(serial))
    # refusal:ambiguous-serial
    if len(matches) != 1:
        raise AmbiguousSerial(serial)


def _require_read_only(resolver: Resolver, fd: int) -> None:
    # refusal:not-readonly — must run on the verified fd, never via the path
    if not resolver.is_read_only(fd):
        raise NotReadOnly()


def _fingerprint_policy(
    manifest: Mapping[str, Any], ident: Mapping[str, Any]
) -> tuple[bool, Optional[str], list[str]]:
    warnings: list[str] = []
    media = manifest.get("media_class")
    usb = bool(ident.get("usb_bridge"))
    allow = bool(manifest.get("allow_fingerprint"))

    if usb:
        warnings.append(SKIP_USB_BRIDGE)

    if media == "failing":
        return True, SKIP_FAILING, warnings
    if not allow:
        reason = SKIP_UNSET_CLASS if media is None else SKIP_NOT_ALLOWED
        return True, reason, warnings
    if usb:
        return True, SKIP_USB_BRIDGE, warnings
    return False, None, warnings


def open_device_readonly(path: str) -> int:
    """Low-level RO open. Callers must still go through assert_bound().

    Prefix check happens before the syscall so a /Volumes argument is refused
    without touching that tree. This is the Python-side /Volumes guard for
    device nodes; the C daemon has a separate, deliberately duplicated check.
    """
    import os
    if path == "/Volumes" or path.startswith("/Volumes/"):
        raise BindError(MSG_VOLUMES)
    return os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)


def assert_bound(path: str, manifest: Any, *, resolver: Resolver) -> BoundDevice:
    """Open path, verify identity, return a BoundDevice holding the fd.

    `path` is used only as the open argument. It is not compared, stored, or
    returned. Manifest `path` / `device` keys, if present, are ignored.
    """
    manifest = _require_manifest(manifest)
    _require_manifest_fields(manifest)
    resolver = _require_resolver(resolver)

    fd = resolver.open(path)
    try:
        st = resolver.fstat(fd)
        fd_maj, fd_min = _dev_major_minor(st)
        ident = dict(resolver.identity_from_fd(fd))
        _require_observed_fields(ident)
        _require_majmin(fd_maj, fd_min, ident)
        _require_identity(manifest, ident)
        _require_unique_serial(resolver, str(ident["serial"]))
        _require_read_only(resolver, fd)
        skipped, reason, warnings = _fingerprint_policy(manifest, ident)
        fp = None
        if not skipped:
            fp = resolver.fingerprint(fd)
        bound = BoundDevice(
            fd,
            major=fd_maj,
            minor=fd_min,
            serial=str(ident["serial"]),
            partuuid=str(ident["partuuid"]),
            fs_uuid=str(ident["fs_uuid"]),
            fingerprint=fp,
            fingerprint_skipped=skipped,
            fingerprint_skip_reason=reason,
            warnings=warnings,
        )
        return bound
    except Exception:
        try:
            resolver.close(fd)
        except Exception:
            pass
        raise
