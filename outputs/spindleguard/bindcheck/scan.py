# SPDX-License-Identifier: GPL-2.0-or-later
"""Structural scanner: device-shaped open() must live in bindcheck/.

STRUCTURAL_CANARY_assert_bound — planted so a search that returns zero hits
is distinguishable from a wrapper that silently returned a false zero.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

STRUCTURAL_CANARY = "STRUCTURAL_CANARY_assert_bound"

NON_BLOCK = {
    "null",
    "zero",
    "urandom",
    "random",
    "tty",
    "stdin",
    "stdout",
    "stderr",
    "full",
    "ptmx",
    "console",
    "kmsg",
}
NON_BLOCK_PREFIXES = ("fd/", "pts/", "shm/", "mqueue/")

BLOCK_NAME = re.compile(
    r"^(?:"
    r"r?disk\d+(?:s\d+)*|"
    r"sd[a-z]+\d*|"
    r"hd[a-z]+\d*|"
    r"vd[a-z]+\d*|"
    r"xvd[a-z]+\d*|"
    r"nvme\d+n\d+(?:p\d+)?|"
    r"mmcblk\d+(?:p\d+)?|"
    r"loop\d+|"
    r"nbd\d+(?:p\d+)?|"
    r"md\d+|"
    r"dm-\d+|"
    r"mapper/.+|"
    r"dasd[a-z]+\d*|"
    r"zd\d+(?:p\d+)?"
    r")$"
)

OPEN_FUNCS = {
    "open",
    "os.open",
    "os.openat",
    "posix.open",
    "posix.openat",
    "io.open",
    "builtins.open",
}
SYSCALL_OPEN = {
    "os.open",
    "os.openat",
    "posix.open",
    "posix.openat",
}

C_OPEN = re.compile(
    r"\b(?:open|openat|open64|fopen)\s*\(",
    re.MULTILINE,
)
C_STRING = re.compile(r'"([^"\\]|\\.)*"')
C_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)
C_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

SOURCE_SUFFIXES = {".py", ".c", ".h"}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    message: str

    def as_text(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def is_non_block_dev(rest: str) -> bool:
    if rest in NON_BLOCK:
        return True
    return any(rest.startswith(prefix) for prefix in NON_BLOCK_PREFIXES)


def is_device_shaped_string(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if value in ("/dev", "/dev/"):
        return True
    if not value.startswith("/dev/"):
        return False
    rest = value[5:]
    if is_non_block_dev(rest):
        return False
    if BLOCK_NAME.match(rest):
        return True
    # Fail closed on unknown /dev/ nodes (not /dev/null and friends).
    return True


def looks_like_dev_prefix(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith("/dev") or is_device_shaped_string(value)


def in_bindcheck(path: Path, root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = Path(*path.parts)
    return "bindcheck" in rel.parts


def _qualname(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parent = _qualname(func.value)
        if parent:
            return parent + "." + func.attr
        return func.attr
    return ""


def _expr_device_shaped(node: ast.AST, env: dict[str, bool]) -> bool:
    if isinstance(node, ast.Constant):
        return is_device_shaped_string(node.value) or (
            isinstance(node.value, str) and node.value in ("/dev", "/dev/")
        )
    if isinstance(node, ast.Name):
        return bool(env.get(node.id))
    if isinstance(node, ast.JoinedStr):
        return any(
            isinstance(part, ast.Constant) and looks_like_dev_prefix(part.value)
            for part in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _expr_device_shaped(node.left, env) or _expr_device_shaped(
            node.right, env
        )
    if isinstance(node, ast.Call):
        name = _qualname(node.func)
        if name in {"os.path.join", "posixpath.join", "ntpath.join"}:
            return any(_expr_device_shaped(arg, env) for arg in node.args)
        if name in {"pathlib.Path", "Path"}:
            return any(_expr_device_shaped(arg, env) for arg in node.args)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return _expr_device_shaped(node.func.value, env)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "join":
            return _expr_device_shaped(node.func.value, env) or any(
                _expr_device_shaped(arg, env) for arg in node.args
            )
    return False


def _is_open_call(node: ast.Call) -> tuple[bool, int]:
    """Return (is_open, path_arg_index). openat path is the second argument."""
    name = _qualname(node.func)
    if name in {"os.openat", "posix.openat"}:
        return True, 1
    if name in OPEN_FUNCS or name.endswith(".open"):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
            return True, 0
        if name in OPEN_FUNCS:
            return True, 0
    if isinstance(node.func, ast.Name) and node.func.id == "open":
        return True, 0
    return False, 0


def _record_assign(node: ast.AST, env: dict[str, bool]) -> None:
    if isinstance(node, ast.Assign):
        shaped = _expr_device_shaped(node.value, env)
        for target in node.targets:
            if isinstance(target, ast.Name):
                env[target.id] = shaped
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        if node.value is not None:
            env[node.target.id] = _expr_device_shaped(node.value, env)


def python_violations(source: str, filename: str) -> list[Violation]:
    tree = ast.parse(source, filename=filename)
    found: list[Violation] = []
    env: dict[str, bool] = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.local = [env]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.local.append(dict(self.local[-1]))
            self.generic_visit(node)
            self.local.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Assign(self, node: ast.Assign) -> None:
            _record_assign(node, self.local[-1])
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            _record_assign(node, self.local[-1])
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            name = _qualname(node.func)
            if name in SYSCALL_OPEN:
                found.append(
                    Violation(
                        filename,
                        getattr(node, "lineno", 1),
                        "os.open/os.openat outside bindcheck",
                    )
                )
            is_open, idx = _is_open_call(node)
            if is_open:
                args = list(node.args)
                if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
                    if _expr_device_shaped(node.func.value, self.local[-1]):
                        found.append(
                            Violation(
                                filename,
                                getattr(node, "lineno", 1),
                                "device-shaped Path.open() outside bindcheck",
                            )
                        )
                if len(args) > idx and _expr_device_shaped(args[idx], self.local[-1]):
                    found.append(
                        Violation(
                            filename,
                            getattr(node, "lineno", 1),
                            "device-shaped open() outside bindcheck",
                        )
                    )
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _strip_c_comments(source: str) -> str:
    source = C_BLOCK_COMMENT.sub("", source)
    source = C_LINE_COMMENT.sub("", source)
    return source


def c_violations(source: str, filename: str) -> list[Violation]:
    stripped = _strip_c_comments(source)
    found: list[Violation] = []
    # A function-sized window is overkill: flag a device-path string in a
    # translation unit that also calls open/openat/fopen.
    device_strings: list[tuple[int, str]] = []
    for match in C_STRING.finditer(stripped):
        raw = match.group(0)[1:-1]
        if is_device_shaped_string(raw) or raw in ("/dev", "/dev/"):
            line = stripped[: match.start()].count("\n") + 1
            device_strings.append((line, raw))
    if not device_strings:
        return found
    if not C_OPEN.search(stripped):
        return found
    for line, raw in device_strings:
        found.append(
            Violation(
                filename,
                line,
                f"device-shaped C string {raw!r} in a file that calls open/openat",
            )
        )
    return found


def scan_source(source: str, filename: str) -> list[Violation]:
    lower = filename.lower()
    if lower.endswith(".py"):
        return python_violations(source, filename)
    if lower.endswith(".c") or lower.endswith(".h"):
        return c_violations(source, filename)
    return []


def iter_source_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        if "__pycache__" in path.parts:
            continue
        yield path


def scan_tree(root: Path) -> list[Violation]:
    root = Path(root)
    found: list[Violation] = []
    for path in iter_source_files(root):
        if in_bindcheck(path, root):
            continue
        text = path.read_text(encoding="utf-8")
        rel = str(path)
        try:
            rel = str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            pass
        found.extend(scan_source(text, rel))
    return found
