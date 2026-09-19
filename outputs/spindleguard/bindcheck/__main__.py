# SPDX-License-Identifier: GPL-2.0-or-later
"""Non-interactive bindcheck CLI.

Examples:
  python3 -m bindcheck scan --root .
  python3 -m bindcheck bind --manifest FILE --path PATH --fixture FILE
  python3 -m bindcheck rotate-manifest --old FILE --observed FILE --reason TEXT --out FILE --audit FILE
  python3 -m bindcheck rotate-manifest --old FILE --observed FILE --reason TEXT --out FILE --audit FILE --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .bind import BindError, assert_bound
from .fake import FakeResolver, blocks_from_fixture
from .manifest import rotate_manifest
from .scan import STRUCTURAL_CANARY, scan_tree


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: --root is not a directory: {root}", file=sys.stderr)
        print("  python3 -m bindcheck scan --root .", file=sys.stderr)
        return 2
    hits = scan_tree(root)
    if args.json:
        print(json.dumps({"canary": STRUCTURAL_CANARY, "violations": [
            {"path": v.path, "line": v.line, "message": v.message} for v in hits
        ]}, indent=2))
    else:
        print(f"canary: {STRUCTURAL_CANARY}")
        if not hits:
            print("scan: 0 device-shaped open() outside bindcheck")
        for hit in hits:
            print(hit.as_text())
    return 1 if hits else 0


def cmd_bind(args: argparse.Namespace) -> int:
    if not args.manifest:
        print("Error: --manifest is required.", file=sys.stderr)
        print(
            "  python3 -m bindcheck bind --manifest FILE --path PATH --fixture FILE",
            file=sys.stderr,
        )
        return 2
    if not args.path:
        print("Error: --path is required.", file=sys.stderr)
        print(
            "  python3 -m bindcheck bind --manifest FILE --path PATH --fixture FILE",
            file=sys.stderr,
        )
        return 2
    if not args.fixture:
        print(
            "Error: hardware probing is not enabled. Pass a fake --fixture.",
            file=sys.stderr,
        )
        print(
            "  python3 -m bindcheck bind --manifest FILE --path PATH --fixture FILE",
            file=sys.stderr,
        )
        return 2
    try:
        manifest = _load_json(args.manifest)
        fixture = _load_json(args.fixture)
        resolver = FakeResolver(blocks_from_fixture(fixture))
        bound = assert_bound(args.path, manifest, resolver=resolver)
    except (BindError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    payload = bound.as_log()
    if bound.fingerprint_skipped:
        print(
            f"fingerprint skipped: {bound.fingerprint_skip_reason}",
            file=sys.stderr,
        )
    for warning in bound.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    missing = [
        name
        for name, value in (
            ("--old", args.old),
            ("--observed", args.observed),
            ("--reason", args.reason),
            ("--out", args.out),
            ("--audit", args.audit),
        )
        if not value
    ]
    if missing:
        print("Error: missing " + ", ".join(missing), file=sys.stderr)
        print(
            "  python3 -m bindcheck rotate-manifest --old FILE --observed FILE "
            "--reason TEXT --out FILE --audit FILE",
            file=sys.stderr,
        )
        return 2
    try:
        old = _load_json(args.old)
        observed = _load_json(args.observed)
        if args.dry_run:
            from .manifest import fields_changed
            changed = fields_changed(old, observed)
            print(json.dumps({
                "dry_run": True,
                "fields_changed": changed,
                "out": args.out,
            }, indent=2, sort_keys=True))
            return 0
        new = rotate_manifest(
            old,
            observed,
            reason=args.reason,
            out_path=args.out,
            audit_path=args.audit,
        )
    except (BindError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(new, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m bindcheck",
        description="Identity-bind a device fd, scan for unguarded opens, or rotate a manifest.",
    )
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="fail if device-shaped open() exists outside bindcheck/")
    scan.add_argument("--root", default=".", help="tree to scan (default: .)")
    scan.add_argument("--json", action="store_true", help="machine-readable violations")
    scan.set_defaults(func=cmd_scan)

    bind = sub.add_parser("bind", help="assert_bound against a fake fixture (no host /dev)")
    bind.add_argument("--manifest", help="identity manifest JSON")
    bind.add_argument("--path", help="path key in the fixture, not a host open")
    bind.add_argument("--fixture", help="fake block-device table JSON")
    bind.set_defaults(func=cmd_bind)

    rotate = sub.add_parser("rotate-manifest", help="write a new generation; never overwrites")
    rotate.add_argument("--old", help="current manifest JSON")
    rotate.add_argument("--observed", help="observed identity JSON")
    rotate.add_argument("--reason", help="why the old manifest is invalid")
    rotate.add_argument("--out", help="new manifest path (must not exist)")
    rotate.add_argument("--audit", help="append-only JSONL audit path")
    rotate.add_argument("--dry-run", action="store_true", help="print the delta; write nothing")
    rotate.set_defaults(func=cmd_rotate)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help(sys.stderr)
        print("Error: a subcommand is required.", file=sys.stderr)
        print("  python3 -m bindcheck scan --root .", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
