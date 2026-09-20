# SPDX-License-Identifier: GPL-2.0-or-later
"""Install/control-plane verification. Never runs make test (FUSE mounts)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .doctor import doctor
from .policy import PolicyError, VOLUMES_MSG, check_observe_path
from .setup import setup


def _run(argv: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, env=merged)
    return {
        "cmd": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "ok": result.returncode == 0,
    }


def verify_quick(project_root: Path) -> dict[str, Any]:
    """Doctor, setup dry-run, policy refusals, scan, example bind. No mounts."""
    root = Path(project_root)
    sg = [sys.executable, str(root / "sg")]
    checks: list[dict[str, Any]] = []

    info = doctor(root)
    checks.append({"name": "doctor", "ok": True, "detail": f"can_mount={info['can_mount']}"})

    plan = setup(root, dry_run=True)
    checks.append({"name": "setup-dry-run", "ok": True, "detail": f"{len(plan['steps'])} steps"})

    try:
        check_observe_path("/Volumes/exhibit")
        checks.append({"name": "volumes-refusal", "ok": False, "detail": "did not refuse"})
    except PolicyError as exc:
        checks.append({"name": "volumes-refusal", "ok": str(exc) == VOLUMES_MSG, "detail": str(exc)})

    scan = _run(sg + ["scan", "--root", str(root), "--json"], root)
    checks.append({"name": "scan", "ok": scan["ok"], "detail": "device-shaped open scan"})

    bind = _run(
        sg
        + [
            "bind",
            "--manifest",
            str(root / "macos/Resources/example-manifest.json"),
            "--path",
            "/dev/sda1",
            "--fixture",
            str(root / "macos/Resources/example-fixture.json"),
        ],
        root,
    )
    checks.append({"name": "bind-example", "ok": bind["ok"], "detail": "fixture bind"})

    app = _run(sg + ["app", "--dry-run"], root)
    checks.append({"name": "app-dry-run", "ok": app["ok"], "detail": "bundle helper"})

    help_ = _run(sg + ["--help"], root)
    checks.append({"name": "sg-help", "ok": help_["ok"] and "setup" in help_["stdout"], "detail": "cli help"})

    unmount = _run(sg + ["unmount", "--mount", "/Volumes/exhibit", "--dry-run"], root)
    checks.append(
        {
            "name": "unmount-volumes",
            "ok": unmount["returncode"] == 2 and "Prototype refuses /Volumes paths" in unmount["stderr"],
            "detail": "unmount refuses /Volumes",
        }
    )

    fuse_yes = _run(sg + ["setup", "--install-fuse", "--dry-run", "--json"], root)
    checks.append(
        {
            "name": "fuse-requires-yes",
            "ok": fuse_yes["returncode"] == 2 and "requires --yes" in fuse_yes["stderr"],
            "detail": "FUSE install is never automatic",
        }
    )

    failed = [c["name"] for c in checks if not c["ok"]]
    return {
        "mode": "quick",
        "ok": not failed,
        "failed": failed,
        "checks": checks,
        "can_mount": info["can_mount"],
        "next": info.get("next") or [],
    }


def verify_full(project_root: Path) -> dict[str, Any]:
    root = Path(project_root)
    quick = verify_quick(root)
    env = {"SG_REQUIRE_FULL": "1"}
    control = _run([sys.executable, "-B", str(root / "tests/strict.py")], root, env)
    mutations = _run([sys.executable, "-B", str(root / "tests/run_bindcheck_mutations.py")], root, env)
    extra = [
        {"name": "test-control", "ok": control["ok"], "detail": "SG_REQUIRE_FULL=1"},
        {"name": "test-bindcheck", "ok": mutations["ok"], "detail": "mutation controls"},
    ]
    checks = quick["checks"] + extra
    failed = [c["name"] for c in checks if not c["ok"]]
    return {
        "mode": "full",
        "ok": not failed,
        "failed": failed,
        "checks": checks,
        "can_mount": quick["can_mount"],
        "control_tail": control["stdout"][-500:],
    }
