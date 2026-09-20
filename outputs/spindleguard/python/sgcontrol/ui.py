# SPDX-License-Identifier: GPL-2.0-or-later
"""Loopback preview of the native app. Does not mount or open /dev.

Purge only deletes bucketed ui-session directories under the session parent.
"""
from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .policy import PolicyError, is_dev_path, is_volumes_path

BLOCKED_FLAGS = ("--install-fuse", "--full", "--allow-missing-marker")
ALLOWED_COMMANDS = {
    "doctor",
    "setup",
    "verify",
    "session-create",
    "session-load",
    "session-list",
    "session-bucket",
    "session-restore",
    "session-purge",
    "policy-check",
    "start",
    "unmount",
    "scan",
    "bind",
    "rotate-manifest",
    "topology",
    "probe-log",
    "app",
}


def _validate_argv(argv: list[str]) -> None:
    if not argv:
        raise PolicyError("a subcommand is required")
    command = argv[0]
    if command not in ALLOWED_COMMANDS:
        raise PolicyError(f"preview refuses command {command}")
    joined = " ".join(argv)
    for flag in BLOCKED_FLAGS:
        if flag in argv:
            raise PolicyError(f"preview refuses {flag}")
    if "--yes" in argv and command != "session-purge":
        raise PolicyError("preview refuses --yes")
    if command == "session-purge" and "--yes" not in argv and "--dry-run" not in argv:
        raise PolicyError("preview purge requires --yes")
    if command == "start" and "--dry-run" not in argv:
        raise PolicyError("preview start requires --dry-run")
    if command == "unmount" and "--dry-run" not in argv:
        raise PolicyError("preview unmount requires --dry-run")
    if command == "verify" and "--quick" not in argv:
        argv.append("--quick")
    for item in argv[1:]:
        if item.startswith("-"):
            continue
        if is_volumes_path(item):
            raise PolicyError("Prototype refuses /Volumes paths. Use disposable directories.")
        if is_dev_path(item) and not (command == "bind" and "--fixture" in argv):
            raise PolicyError("Prototype refuses /dev paths. Use disposable directories.")
    if command == "setup" and "--install-fuse" in joined:
        raise PolicyError("preview refuses FUSE install")


def serve_preview(project_root: Path, *, host: str, port: int, open_browser: bool) -> int:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("preview binds loopback only")
    root = Path(project_root)
    page = root / "macos" / "preview.html"
    if not page.is_file():
        raise OSError(f"missing {page}")
    sg = root / "sg"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("ui: " + (format % args) + "\n")

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ("/", "/index.html", "/preview.html"):
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/api/health":
                self._send(200, b'{"ok":true,"preview":true}', "application/json")
                return
            self._send(404, b'{"error":"not found"}', "application/json")

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/sg":
                self._send(404, b'{"error":"not found"}', "application/json")
                return
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
                argv = [str(x) for x in payload.get("argv") or []]
                _validate_argv(argv)
            except (json.JSONDecodeError, PolicyError, TypeError, ValueError) as exc:
                body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self._send(400, body, "application/json")
                return
            result = subprocess.run(
                [sys.executable, str(sg), *argv],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
            out: dict[str, Any] = {
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stderr": result.stderr[-4000:],
            }
            try:
                out["data"] = json.loads(result.stdout) if result.stdout.strip() else None
            except json.JSONDecodeError:
                out["data"] = result.stdout
            self._send(200, json.dumps(out).encode("utf-8"), "application/json")

    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(json.dumps({"ok": True, "url": url, "preview": True}, indent=2, sort_keys=True), flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0
