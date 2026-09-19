# SPDX-License-Identifier: GPL-2.0-or-later
"""Prove each named refusal goes RED when that check is deleted.

Mutates in place, expects the targeted unittest to fail, restores original
bytes, and checks sha256. Does not delete files. Does not run proof.py.
Does not touch /Volumes or host /dev.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_unittest(module: str, test: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT)
    env["SG_REQUIRE_FULL"] = "1"
    return subprocess.run(
        [PYTHON, "-B", "-m", "unittest", f"{module}.{test}"],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
        env=env,
    )


@dataclass
class Mutation:
    name: str
    path: Path
    needle: str
    replacement: str
    module: str
    test: str


MUTATIONS = [
    Mutation(
        name="no-manifest",
        path=PROJECT / "bindcheck" / "bind.py",
        needle="    if not isinstance(manifest, Mapping) or not manifest:\n        raise NoManifest()\n",
        replacement="    if False and (not isinstance(manifest, Mapping) or not manifest):\n        raise NoManifest()\n",
        module="tests.test_bindcheck",
        test="AssertBoundTests.test_no_manifest_none",
    ),
    Mutation(
        name="identity-mismatch",
        path=PROJECT / "bindcheck" / "bind.py",
        needle="        if observed != expected:\n            raise IdentityMismatch(field, expected, observed)\n",
        replacement="        if False and observed != expected:\n            raise IdentityMismatch(field, expected, observed)\n",
        module="tests.test_bindcheck_swap",
        test="SwapIncidentTests.test_hardcoded_sda1_refuses_after_swap",
    ),
    Mutation(
        name="not-readonly",
        path=PROJECT / "bindcheck" / "bind.py",
        needle="    if not resolver.is_read_only(fd):\n        raise NotReadOnly()\n",
        replacement="    if False and not resolver.is_read_only(fd):\n        raise NotReadOnly()\n",
        module="tests.test_bindcheck",
        test="AssertBoundTests.test_not_readonly_on_verified_fd",
    ),
    Mutation(
        name="ambiguous-serial",
        path=PROJECT / "bindcheck" / "bind.py",
        needle="    if len(matches) != 1:\n        raise AmbiguousSerial(serial)\n",
        replacement="    if False and len(matches) != 1:\n        raise AmbiguousSerial(serial)\n",
        module="tests.test_bindcheck",
        test="AssertBoundTests.test_ambiguous_serial_two_nodes",
    ),
    Mutation(
        name="unresolvable-observed",
        path=PROJECT / "bindcheck" / "bind.py",
        needle="        if not _present(ident.get(field)):\n            raise UnresolvableField(field)\n",
        replacement="        if False and not _present(ident.get(field)):\n            raise UnresolvableField(field)\n",
        module="tests.test_bindcheck",
        test="AssertBoundTests.test_unresolvable_observed_serial",
    ),
]


def restore(path: Path, original: bytes, digest: str) -> None:
    path.write_bytes(original)
    now = sha256(path.read_bytes())
    if now != digest:
        raise SystemExit(f"RESTORE SHA MISMATCH {path}: {now} != {digest}")


def apply_mutation(mut: Mutation) -> None:
    text = mut.path.read_text(encoding="utf-8")
    count = text.count(mut.needle)
    if count != 1:
        raise SystemExit(f"{mut.name}: needle count {count} in {mut.path}")
    mut.path.write_text(text.replace(mut.needle, mut.replacement, 1), encoding="utf-8")


def mutation_device_open() -> None:
    """Inject os.open of a device node into topology.py; structure test must RED."""
    path = PROJECT / "tools" / "topology.py"
    original = path.read_bytes()
    digest = sha256(original)
    injection = (
        original.decode("utf-8")
        + "\nimport os as _sg_mut_os\n"
        + "_sg_mut_os.open('/dev/sda1', getattr(_sg_mut_os, 'O_RDONLY', 0))\n"
    )
    try:
        path.write_text(injection, encoding="utf-8")
        result = run_unittest(
            "tests.test_bindcheck_structure",
            "LiveTreeTests.test_current_tree_has_no_violations",
        )
        if result.returncode == 0:
            raise SystemExit(
                "MUTATION STAYED GREEN: device open in topology.py\n"
                + result.stdout
                + result.stderr
            )
        print("MUTATION RED: device-open-in-topology", flush=True)
    finally:
        restore(path, original, digest)


def main() -> int:
    tracked = []
    for mut in MUTATIONS:
        original = mut.path.read_bytes()
        tracked.append((mut.path, original, sha256(original)))

    extra = PROJECT / "tools" / "topology.py"
    tracked.append((extra, extra.read_bytes(), sha256(extra.read_bytes())))

    try:
        for mut in MUTATIONS:
            original = mut.path.read_bytes()
            digest = sha256(original)
            try:
                apply_mutation(mut)
                result = run_unittest(mut.module, mut.test)
                if result.returncode == 0:
                    raise SystemExit(
                        f"MUTATION STAYED GREEN: {mut.name}\n{result.stdout}{result.stderr}"
                    )
                print(f"MUTATION RED: {mut.name}", flush=True)
            finally:
                restore(mut.path, original, digest)
        mutation_device_open()
    finally:
        for path, original, digest in tracked:
            if path.read_bytes() != original:
                restore(path, original, digest)
            elif sha256(path.read_bytes()) != digest:
                restore(path, original, digest)

    print("files restored sha256-identical", flush=True)
    seen = set()
    for path, original, digest in tracked:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        now = sha256(path.read_bytes())
        print(f"  {path.relative_to(PROJECT)} {now}", flush=True)
        if now != digest:
            raise SystemExit(f"final digest mismatch: {path}")
    print("ALL BINDCHECK MUTATION CONTROLS RED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
