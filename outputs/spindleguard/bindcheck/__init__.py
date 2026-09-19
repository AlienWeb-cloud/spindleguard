# SPDX-License-Identifier: GPL-2.0-or-later
"""Identity binding: open by path, trust only the fd."""

from .bind import (
    AmbiguousSerial,
    BindError,
    BoundDevice,
    IdentityMismatch,
    NoManifest,
    NotReadOnly,
    REQUIRED_FIELDS,
    Resolver,
    UnresolvableField,
    assert_bound,
    open_device_readonly,
)
from .scan import STRUCTURAL_CANARY, scan_tree

__all__ = [
    "AmbiguousSerial",
    "BindError",
    "BoundDevice",
    "IdentityMismatch",
    "NoManifest",
    "NotReadOnly",
    "REQUIRED_FIELDS",
    "Resolver",
    "STRUCTURAL_CANARY",
    "UnresolvableField",
    "assert_bound",
    "open_device_readonly",
    "scan_tree",
]
