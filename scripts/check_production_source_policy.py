#!/usr/bin/env python3
"""Reject mutable or workstation-specific inputs from production Python code."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = (REPO_ROOT / "src",)

# Historical research is intentionally retained, but is not production code.
HISTORICAL_NOTEBOOK_EXCEPTIONS = (
    REPO_ROOT / "notebooks",
    REPO_ROOT / "notebooks_legacy",
)

ABSOLUTE_AUTHOR_PATH = re.compile(r"^/(?:home|Users|media)/[^/]+/")
DESERIALIZATION_MODULES = {"pickle", "joblib", "cloudpickle", "dill"}
WALL_CLOCK_CALLS = {"now", "today", "utcnow"}


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value.startswith(("http://raw.githubusercontent.com", "https://raw.githubusercontent.com")):
                found.add((node.lineno, "mutable raw.githubusercontent.com input"))
            if ABSOLUTE_AUTHOR_PATH.match(value):
                found.add((node.lineno, "absolute author/workstation path"))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([node.module] if isinstance(node, ast.ImportFrom) else
                     [alias.name for alias in node.names])
            if any(name and name.split(".")[0] in DESERIALIZATION_MODULES for name in names):
                found.add((node.lineno, "model-capable deserialization module"))
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name.split(".")[0] in DESERIALIZATION_MODULES and name.split(".")[-1] in {"load", "loads"}:
                found.add((node.lineno, "model deserialization call"))
            if name.split(".")[-1] in WALL_CLOCK_CALLS:
                found.add((node.lineno, "direct wall-clock selection"))
    return [f"{path.relative_to(REPO_ROOT)}:{line}: {message}" for line, message in sorted(found)]


def main() -> int:
    errors: list[str] = []
    for root in PRODUCTION_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if any(path.is_relative_to(excluded) for excluded in HISTORICAL_NOTEBOOK_EXCEPTIONS):
                continue
            errors.extend(violations(path))
    if errors:
        print("Production source policy violations:", file=sys.stderr)
        print("\n".join(f"  {error}" for error in errors), file=sys.stderr)
        return 1
    print("ok: production source policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
