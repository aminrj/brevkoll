#!/usr/bin/env python3
"""Traceability: every acceptance criterion and every adopted threat-model control has a test.

Sources
  thoughts/*/spec.md          acceptance criteria written as `AC<n>: ...` list items
  thoughts/*/threat-model.md  table rows whose first cell is `T<n>`; a row needs a test when
                              its decision cell starts with ACCEPTED or CHANGED (not REJECTED)
  tests/**/*.py               `@pytest.mark.ac("AC1")`, `@pytest.mark.control("T1")`, or a `# AC1` /
                              `# T1` comment inside the test function (holdout tests use comments)

Usage: trace.py [--root DIR] [--tests DIR ...]     exit 1 if anything has no test
Holdout tests are only readable by humans and CI; this script runs in CI where they exist.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

AC_ITEM = re.compile(r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?\**(AC\d+)\b")
ID_IN_TEXT = re.compile(r"\b(AC\d+|T\d+)\b")
NEEDS_TEST = re.compile(r"^(ACCEPTED|CHANGED)\b", re.I)


def issue_dirs(root: Path) -> list[Path]:
    return sorted(p for p in (root / "thoughts").glob("*") if p.is_dir())


def acceptance_criteria(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for d in issue_dirs(root):
        spec = d / "spec.md"
        if spec.exists():
            for line in spec.read_text().splitlines():
                if m := AC_ITEM.match(line):
                    found[f"{d.name}/{m.group(1)}"] = line.strip()
    return found


def decided_controls(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for d in issue_dirs(root):
        tm = d / "threat-model.md"
        if not tm.exists():
            continue
        for line in tm.read_text().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and re.fullmatch(r"T\d+", cells[0]) and NEEDS_TEST.match(cells[-1]):
                found[f"{d.name}/{cells[0]}"] = line.strip()
    return found


def marker_ids(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    ids: set[str] = set()
    for dec in node.decorator_list:
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr in {"ac", "control"}
        ):
            ids.update(
                a.value
                for a in dec.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            )
    return ids


def comment_lines(text: str) -> dict[int, str]:
    """Real comments only (string contents that look like comments do not count)."""
    out: dict[int, str] = {}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            out[tok.start[0]] = tok.string
    return out


def covered_ids(test_roots: list[Path]) -> set[str]:
    """IDs referenced by test functions. IDs are matched by name across issues (see README)."""
    covered: set[str] = set()
    for base in test_roots:
        for path in base.rglob("test_*.py"):
            text = path.read_text()
            comments = comment_lines(text)
            lines = text.splitlines()
            for node in ast.walk(ast.parse(text)):
                if isinstance(
                    node, ast.FunctionDef | ast.AsyncFunctionDef
                ) and node.name.startswith("test"):
                    covered |= marker_ids(node)
                    first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                    while first - 1 in comments and lines[first - 2].strip().startswith("#"):
                        first -= 1  # comment block directly above the test (holdout style)
                    for line in range(first, (node.end_lineno or node.lineno) + 1):
                        covered.update(ID_IN_TEXT.findall(comments.get(line, "")))
    return covered


def run(root: Path, test_roots: list[Path]) -> tuple[list[str], list[str]]:
    covered = covered_ids(test_roots)
    acs, controls = acceptance_criteria(root), decided_controls(root)
    missing = [k for k in {**acs, **controls} if k.split("/")[1] not in covered]
    report = [
        f"acceptance criteria: {len(acs)}, decided controls: {len(controls)}, "
        f"ids found in tests: {len(covered)}"
    ]
    return report, sorted(missing)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--tests", nargs="*", default=None)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    test_roots = [Path(t) for t in a.tests] if a.tests else [root / "tests"]
    report, missing = run(root, test_roots)
    print("\n".join(report))
    for item in missing:
        print(f"::error::no test for {item}")
    if missing:
        print(f"trace: {len(missing)} item(s) without a test", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
