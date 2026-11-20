#!/usr/bin/env python3
"""Compare current health metrics with the baseline under quality/policy.toml.

  ratchet.py check   [--current F] [--baseline F] [--policy F]   exit 1 on enforced regression
  ratchet.py tighten [--current F] [--baseline F]                write improved values (never worse)

`tighten` is run by the nightly job (and by a human), never by a coding agent.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path


def worse(direction: str, current: float, baseline: float, tolerance: float) -> bool:
    if direction == "lower":
        return current > baseline + tolerance
    return current < baseline - tolerance


def better(direction: str, current: float, baseline: float) -> bool:
    return current < baseline if direction == "lower" else current > baseline


def check(current: dict, baseline: dict, policy: dict) -> tuple[list[list[str]], bool]:
    rows, failed = [], False
    for name, rule in sorted(policy["metrics"].items()):
        cur, base = current["metrics"].get(name), baseline["metrics"].get(name)
        if cur is None or base is None:
            rows.append([name, str(base), str(cur), rule["mode"], "n/a"])
            continue
        bad = worse(rule["direction"], cur, base, rule["tolerance"])
        status = "OK"
        if bad:
            status = "FAIL" if rule["mode"] == "enforce" else "WARN"
            failed = failed or rule["mode"] == "enforce"
        elif better(rule["direction"], cur, base):
            status = "better"
        rows.append([name, str(base), str(cur), rule["mode"], status])
    return rows, failed


def table(rows: list[list[str]]) -> str:
    head = ["metric", "baseline", "current", "mode", "status"]
    widths = [max(len(r[i]) for r in [head, *rows]) for i in range(5)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    return "\n".join(
        [fmt.format(*head), fmt.format(*["-" * w for w in widths])] + [fmt.format(*r) for r in rows]
    )


def tighten(current: dict, baseline: dict, policy: dict) -> list[str]:
    changed = []
    for name, rule in policy["metrics"].items():
        cur, base = current["metrics"].get(name), baseline["metrics"].get(name)
        if cur is not None and base is not None and better(rule["direction"], cur, base):
            baseline["metrics"][name] = cur
            changed.append(f"{name}: {base} -> {cur}")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "tighten"])
    ap.add_argument("--current", default="health.current.json")
    ap.add_argument("--baseline", default="quality/health.json")
    ap.add_argument("--policy", default="quality/policy.toml")
    a = ap.parse_args()
    current = json.loads(Path(a.current).read_text())
    baseline = json.loads(Path(a.baseline).read_text())
    policy = tomllib.loads(Path(a.policy).read_text())
    if a.cmd == "check":
        rows, failed = check(current, baseline, policy)
        print(table(rows))
        if failed:
            print(
                "\nquality ratchet: an enforced metric got worse than the baseline.",
                file=sys.stderr,
            )
        return 1 if failed else 0
    changed = tighten(current, baseline, policy)
    if changed:
        Path(a.baseline).write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    print("\n".join(changed) or "nothing to tighten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
