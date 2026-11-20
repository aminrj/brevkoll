#!/usr/bin/env python3
"""Mutation testing (mutmut 2.x) on the source files a PR changes.

  mutation.py [--base origin/main] [--files a.py b.py] [--out mutation.json]

The time limit, target score and mode come from quality/policy.toml [mutation]. In `warn` mode the
script always exits 0; in `enforce` mode it exits 1 when any file is below the target.
Output: a table on stdout and a JSON file (schema in docs/data-contracts of the factory repo).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import tomllib
from pathlib import Path

CACHE = Path(".mutmut-cache")
KILLED = {"ok_killed"}
SURVIVED = {"bad_survived", "bad_timeout", "ok_suspicious"}


def changed_sources(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", "src"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [f for f in out if f.endswith(".py") and not f.endswith("__init__.py")]


def read_results(path: str) -> dict:
    """Per-file counts and survivors from the mutmut cache."""
    if not CACHE.exists():
        return {"killed": 0, "survived": 0, "survivors": []}
    con = sqlite3.connect(CACHE)
    rows = con.execute(
        "select m.status, l.line_number, l.line from Mutant m join Line l on m.line = l.id "
        "join SourceFile s on l.sourcefile = s.id where s.filename = ?",
        (path,),
    ).fetchall()
    con.close()
    killed = sum(1 for s, _, _ in rows if s in KILLED)
    survivors = sorted({(n + 1, text.strip(), s) for s, n, text in rows if s in SURVIVED})
    return {
        "killed": killed,
        "survived": sum(1 for s, _, _ in rows if s in SURVIVED),
        "survivors": [{"line": n, "code": t, "status": s} for n, t, s in survivors],
    }


def run_file(path: str, seconds: float) -> bool:
    """Returns True if mutmut finished within the budget."""
    if CACHE.exists():
        CACHE.unlink()
    cmd = [
        "mutmut",
        "run",
        "--paths-to-mutate",
        path,
        "--runner",
        "python -m pytest -x -q tests/unit tests/integration",
        "--tests-dir",
        "tests/",
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=max(seconds, 1),
        )
        return True
    except subprocess.TimeoutExpired:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--out", default="mutation.json")
    ap.add_argument("--policy", default="quality/policy.toml")
    a = ap.parse_args()
    policy = tomllib.loads(Path(a.policy).read_text())["mutation"]
    files = a.files if a.files is not None else changed_sources(a.base)
    deadline = time.monotonic() + policy["time_limit_minutes"] * 60
    report = {
        "mode": policy["mode"],
        "target_percent": policy["target_percent"],
        "time_limit_minutes": policy["time_limit_minutes"],
        "files": [],
    }
    for i, path in enumerate(files):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            report["files"].append({"file": path, "status": "skipped_time_limit"})
            continue
        finished = run_file(path, remaining / (len(files) - i))
        res = read_results(path)
        total = res["killed"] + res["survived"]
        score = round(100 * res["killed"] / total, 1) if total else None
        report["files"].append(
            {
                "file": path,
                "status": "complete" if finished else "timed_out",
                "score_percent": score,
                **res,
            }
        )
    Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    below = False
    print(f"mutation testing (mode={policy['mode']}, target={policy['target_percent']}%)")
    if not files:
        print("no changed source files under src/, nothing to mutate")
    for f in report["files"]:
        score = f.get("score_percent")
        print(f"- {f['file']}: {f['status']}, score {score if score is not None else 'n/a'}%")
        for s in f.get("survivors", []):
            print(f"    survived {f['file']}:{s['line']}  {s['code']}")
        below = below or (score is not None and score < policy["target_percent"])
    if below:
        print("some files are below the target score")
    return 1 if below and policy["mode"] == "enforce" else 0


if __name__ == "__main__":
    sys.exit(main())
