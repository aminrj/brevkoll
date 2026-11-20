#!/usr/bin/env python3
"""Code-health metrics as JSON. Stdlib plus radon (and coverage.py for line coverage).

Usage:
  python scripts/health.py [--root DIR] [--out FILE] [--no-coverage] [--coverage-json FILE]

Metrics are measured on `src/` (code) and `tests/` (test ratio). Output keys under "metrics" are the
ones `quality/policy.toml` refers to.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from radon.complexity import cc_visit

SRC, TESTS = "src", "tests"
TEST_DIRS = ("unit", "integration")  # holdout tests are not visible to agents; skip for the ratio


def py_files(root: Path, sub: str, only: tuple[str, ...] | None = None) -> list[Path]:
    base = root / sub
    if not base.is_dir():
        return []
    files = sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    if only:
        files = [p for p in files if any(d in p.relative_to(base).parts for d in only)]
    return files


def line_count(path: Path) -> int:
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def function_lengths(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            out.append((node.name, (node.end_lineno or node.lineno) - node.lineno + 1))
    return out


def complexity(root: Path, files: list[Path]) -> list[dict]:
    blocks = []
    for f in files:
        for b in cc_visit(f.read_text()):
            name = f"{b.classname}.{b.name}" if getattr(b, "classname", None) else b.name
            blocks.append(
                {
                    "file": str(f.relative_to(root)),
                    "function": name,
                    "line": b.lineno,
                    "complexity": b.complexity,
                }
            )
    return blocks


PATTERNS = {
    "type_ignore_count": re.compile(r"#\s*type:\s*ignore"),
    "cast_count": re.compile(r"\bcast\("),
    "bare_except_count": re.compile(r"^\s*except\s*:", re.M),
    "except_exception_count": re.compile(r"\bexcept\s+(?:Exception|BaseException)\b"),
    "noqa_count": re.compile(r"#\s*noqa"),
}


def runtime_dependencies(root: Path) -> int:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return 0
    data = tomllib.loads(pyproject.read_text())
    return len(data.get("project", {}).get("dependencies", []))


def coverage_percent(root: Path, coverage_json: Path | None, run: bool) -> float | None:
    if coverage_json is None and run:
        coverage_json = root / ".coverage.json"
        cmds = [
            [sys.executable, "-m", "coverage", "run", "--source=src", "-m", "pytest", "-q"],
            [sys.executable, "-m", "coverage", "json", "-q", "-o", str(coverage_json)],
        ]
        for cmd in cmds:
            res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
            if res.returncode != 0:
                print(res.stdout[-2000:], res.stderr[-2000:], file=sys.stderr)
                raise SystemExit(f"health.py: {' '.join(cmd[2:5])} failed")
    if coverage_json and coverage_json.exists():
        return round(json.loads(coverage_json.read_text())["totals"]["percent_covered"], 2)
    return None


def measure(root: Path, coverage_json: Path | None = None, run_coverage: bool = True) -> dict:
    src = py_files(root, SRC)
    tests = py_files(root, TESTS, TEST_DIRS)
    blocks = complexity(root, src)
    cc = [b["complexity"] for b in blocks] or [0]
    lengths = [n for f in src for _, n in function_lengths(f)] or [0]
    texts = "\n".join(f.read_text() for f in src)
    src_lines = sum(line_count(f) for f in src)
    test_lines = sum(line_count(f) for f in tests)
    metrics = {
        "max_complexity": max(cc),
        "mean_complexity": round(sum(cc) / len(cc), 2),
        "longest_function_lines": max(lengths),
        "longest_file_lines": max((line_count(f) for f in src), default=0),
        **{name: len(p.findall(texts)) for name, p in PATTERNS.items()},
        "runtime_dependency_count": runtime_dependencies(root),
        "test_to_source_ratio": round(test_lines / src_lines, 2) if src_lines else 0.0,
        "line_coverage_percent": coverage_percent(root, coverage_json, run_coverage),
    }
    worst = sorted(blocks, key=lambda b: -b["complexity"])[:5]
    return {
        "metrics": metrics,
        "worst_functions": worst,
        "source_lines": src_lines,
        "test_lines": test_lines,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out")
    ap.add_argument("--no-coverage", action="store_true")
    ap.add_argument("--coverage-json")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cov = Path(a.coverage_json) if a.coverage_json else None
    result = measure(root, cov, run_coverage=not a.no_coverage)
    text = json.dumps(result, indent=2, sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
