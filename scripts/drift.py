#!/usr/bin/env python3
"""Drift report: what was asked, what was planned, what was built. Deterministic, no model.

The validate step used to be a model grading its own work ("exact match, no deviations").
This script is the part of that check that code can do. It compares, for one issue:

  docs/intent.md, docs/architecture.md   the owner's intent: goals G<n>, "must never" N<n>,
                                         invariants I<n>
  thoughts/<n>/spec.md                   acceptance criteria AC<n>, `Serves:`, `Touches:`,
                                         `Decision needed`
  thoughts/<n>/plan.md                   the files and dependencies the plan said it would touch
  git diff <base>...HEAD                 what was really changed

and writes `thoughts/<n>/drift.md`: a headline (`Drift: CLEAN` or `Drift: REVIEW (k)`), a short
card the foreman quotes at Checkpoint 4, then the evidence. It reports and never fails a
build unless asked (`--strict`).

Usage: drift.py <issue> [--root DIR] [--base origin/main] [--write] [--strict]
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATHISH = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+|[\w-]+\.(?:py|md|toml|ya?ml|json|html|css|js|sh|txt|cfg|ini|lock))(?![\w-])"
)
WEAKENED = re.compile(
    r"#\s*type:\s*ignore|#\s*noqa|#\s*pyright:\s*ignore|pytest\.mark\.(?:skip|xfail)|@unittest\.skip|\bcast\(|"
    r"except\s*:|except\s+(?:Base)?Exception\b|\bpytest\.skip\("
)
ALWAYS_OK = ("thoughts/{n}/", "docs/decisions/", "uv.lock")


@dataclass
class Report:
    n: int
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sections: list[tuple[str, list[str]]] = field(default_factory=list)
    card: list[str] = field(default_factory=list)

    def finding(self, text: str) -> None:
        self.findings.append(text)

    def section(self, title: str, lines: list[str]) -> None:
        self.sections.append((title, lines))


def load_trace():
    """scripts/trace.py by path: its name collides with the standard library's `trace`."""
    spec = importlib.util.spec_from_file_location("factory_trace", HERE / "trace.py")
    if spec is None or spec.loader is None:
        raise ImportError("scripts/trace.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules["factory_trace"] = module
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return res.stdout if res.returncode == 0 else ""


# ---------------------------------------------------------------- parsing (pure, unit-tested)


def ids_of(text: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\b{prefix}\d+\b", text))


def intent_ids(text: str) -> tuple[set[str], set[str]]:
    """Goals G<n> and "must never" lines N<n> written as `- **G1**` in docs/intent.md."""
    bold = set(re.findall(r"\*\*([GN]\d+)\*\*", text))
    return {i for i in bold if i[0] == "G"}, {i for i in bold if i[0] == "N"}


def invariant_ids(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and re.fullmatch(r"I\d+", cells[0]):
            out.add(cells[0])
    return out


def spec_refs(text: str) -> dict[str, str]:
    """The spec's `Serves:`, `Touches:` and `Decision needed ...:` lines (comments stripped)."""
    out: dict[str, str] = {}
    for key, pat in (
        ("serves", r"Serves:\s*(.*)"),
        ("touches", r"Touches:\s*(.*)"),
        ("decision", r"Decision needed[^:\n]*:\s*(.*)"),
    ):
        m = re.search(pat, text)
        if m:
            out[key] = re.sub(r"<!--.*?-->", "", m.group(1)).strip().strip("`").strip()
    return out


def decision_needed(text: str) -> bool:
    return spec_refs(text).get("decision", "").lower().startswith("yes")


def plan_paths(plan: str) -> set[str]:
    """Every path-like token in the plan: the scope the owner approved."""
    plan = re.sub(r"```.*?```", lambda m: m.group(0), plan, flags=re.S)
    return {
        m.group(1).strip("./") if m.group(1).startswith("./") else m.group(1)
        for m in PATHISH.finditer(plan)
    }


def planned(path: str, paths: set[str], n: int) -> bool:
    if any(path.startswith(ok.format(n=n)) for ok in ALWAYS_OK):
        return True
    name = path.rsplit("/", 1)[-1]
    for p in paths:
        p = p.rstrip("/")
        if path == p or path.startswith(p + "/") or p == name or path.endswith("/" + p):
            return True
    return False


def added_lines(diff: str) -> list[tuple[str, str]]:
    """(file, line) for every added line of a unified diff."""
    out: list[tuple[str, str]] = []
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            out.append((current, line[1:]))
    return out


def new_dependencies(pyproject_diff: str) -> list[str]:
    deps = []
    for _, line in added_lines(pyproject_diff):
        m = re.match(r'\s*"([A-Za-z0-9_.-]+)\s*(?:[<>=!~\[].*)?"\s*,?\s*(?:#.*)?$', line)
        if m:
            deps.append(m.group(1))
    return deps


# ---------------------------------------------------------------- the checks


def check_intent(r: Report, root: Path, spec: str) -> tuple[set[str], set[str], set[str]]:
    intent, arch = root / "docs" / "intent.md", root / "docs" / "architecture.md"
    goals: set[str] = set()
    nevers: set[str] = set()
    invs: set[str] = set()
    lines: list[str] = []
    for name, path in (("docs/intent.md", intent), ("docs/architecture.md", arch)):
        if not path.exists():
            r.finding(
                f"`{name}` does not exist: there is no written intent to compare this change with."
            )
            lines.append(f"- `{name}`: missing")
        elif re.search(r"(?m)^Status:\s*template\b", path.read_text()):
            r.finding(f"`{name}` is still the template: the owner has not written the intent yet.")
            lines.append(f"- `{name}`: still a template")
        else:
            lines.append(f"- `{name}`: present")
    if intent.exists():
        goals, nevers = intent_ids(intent.read_text())
    if arch.exists():
        invs = invariant_ids(arch.read_text())
    refs = spec_refs(spec)
    if goals or nevers or invs:
        serves, touches = refs.get("serves", ""), refs.get("touches", "")
        if not serves:
            r.finding(
                "The spec has no `Serves:` line: it does not say which goal in `docs/intent.md` "
                "this change moves."
            )
        elif serves.lower().startswith("none"):
            r.finding(
                "The spec says it serves no goal in `docs/intent.md`: decide whether it "
                "belongs in this app."
            )
        elif unknown := ids_of(serves, "G") - goals:
            r.finding(
                f"The spec serves {', '.join(sorted(unknown))}, which `docs/intent.md` "
                "does not define."
            )
        if touches and (unknown := (ids_of(touches, "N") - nevers) | (ids_of(touches, "I") - invs)):
            r.finding(
                f"The spec touches {', '.join(sorted(unknown))}, which the intent or "
                "architecture does not define."
            )
        lines += [
            f"- Serves: {serves or '(not stated)'}",
            f"- Touches: {touches or '(not stated)'}",
        ]
    r.section("Intent", lines)
    return goals, nevers, invs


def check_scope(r: Report, root: Path, n: int, base: str, changed: list[str], plan: str) -> None:
    paths = plan_paths(plan)
    unplanned = [f for f in changed if not planned(f, paths, n) and not f.startswith("tests/")]
    new_tests = [f for f in changed if f.startswith("tests/")]
    untouched = sorted(
        p
        for p in paths
        if "/" in p
        and not any(
            c == p or c.startswith(p.rstrip("/") + "/") or c.endswith("/" + p) for c in changed
        )
        and not p.startswith(("thoughts/", "docs/decisions/", ".factory/", ".claude/"))
    )
    lines = [f"- Files changed against `{base}`: {len(changed)} ({len(new_tests)} under tests/)."]
    if unplanned:
        r.finding(
            "Changed but not in the plan: "
            + ", ".join(f"`{f}`" for f in unplanned[:10])
            + (" ..." if len(unplanned) > 10 else "")
            + "."
        )
        lines += ["- **Not in the plan:**"] + [f"  - `{f}`" for f in unplanned]
    else:
        lines.append("- Every changed file outside tests/ is named in the plan.")
    if untouched:
        lines += ["- Named in the plan, not changed (check it was not forgotten):"] + [
            f"  - `{p}`" for p in untouched[:10]
        ]
    r.section("Scope: the diff against the plan", lines)


def rel_to(root: Path, ref: str) -> str:
    return ref.removeprefix(root.as_posix() + "/")


def check_tests(r: Report, root: Path, n: int, spec: str, changed: list[str]) -> None:
    trace = load_trace()
    roots = [root / "tests", root / "thoughts" / str(n)]
    where = trace.covered_map([p for p in roots if p.exists()])

    def mine(ref: str) -> bool:
        return (
            ref.split("::")[0].removeprefix(f"{root.as_posix()}/") in changed
            or f"/{n}/" in ref
            or f"issue_{n}" in ref
        )

    lines: list[str] = []
    for key in sorted(trace.acceptance_criteria_of(spec)):
        refs = sorted(where.get(key, set()))
        own = [ref for ref in refs if mine(ref)]
        if own:
            lines.append(
                f"- {key}: "
                + ", ".join(f"`{x.removeprefix(root.as_posix() + '/')}`" for x in own[:3])
            )
        elif refs:
            r.finding(
                f"{key} is matched only by a test from another change: "
                + f"`{refs[0].removeprefix(root.as_posix() + '/')}`. Its own test is missing."
            )
            lines.append(
                f"- {key}: **only a test by the same name from elsewhere** "
                f"(`{rel_to(root, refs[0])}`)"
            )
        else:
            r.finding(f"{key} has no test.")
            lines.append(f"- {key}: **no test**")
    r.section(
        "Acceptance criteria and where a test checks each",
        lines or ["- The spec lists no `AC<n>`."],
    )
    r.card.append(
        f"Acceptance criteria: {len(lines)}; without their own test: "
        f"{sum(1 for x in lines if '**' in x)}."
    )


def check_invariants(
    r: Report, root: Path, spec: str, invs: set[str], changed: list[str], plan: str
) -> None:
    arch_changed = "docs/architecture.md" in changed or "docs/intent.md" in changed
    says_no_impact = (
        bool(re.search(r"(?i)architecture[^\n]*\n?[^\n]*`?\bno\b`?", plan)) if plan else False
    )
    touched = ids_of(spec_refs(spec).get("touches", ""), "I")
    lines = [f"- Invariants touched by the spec: {', '.join(sorted(touched)) or 'none stated'}."]
    if arch_changed:
        lines.append(
            "- `docs/intent.md` or `docs/architecture.md` is in this diff: read what moved."
        )
        r.finding(
            "`docs/intent.md` or `docs/architecture.md` changed in this diff. Read it as a "
            "decision, not as a detail."
        )
    elif touched and not says_no_impact:
        lines.append(
            "- The plan does not say `no` to an architecture impact: check the picture "
            "still matches."
        )
    if (
        root.joinpath("docs", "architecture.md").exists()
        and not invs
        and not re.search(
            r"Status:\s*template", root.joinpath("docs", "architecture.md").read_text()
        )
    ):
        r.finding("`docs/architecture.md` lists no invariant `I<n>`.")
    r.section("Architecture", lines)


def check_diff_content(r: Report, root: Path, n: int, base: str, plan: str) -> None:
    diff = git(
        root, "diff", "-U0", f"{base}...HEAD", "--", ".", ":(exclude)thoughts", ":(exclude)uv.lock"
    )
    weak = [
        (f, line.strip()[:90])
        for f, line in added_lines(diff)
        if WEAKENED.search(line) and not f.endswith((".md", ".sh", ".yml", ".yaml"))
    ]
    lines: list[str] = []
    if weak:
        r.finding(
            f"{len(weak)} added line(s) weaken a check (ignore, skip, cast, broad except). First: "
            f"`{weak[0][0]}`: `{weak[0][1]}`."
        )
        lines += [f"- `{f}`: `{text}`" for f, text in weak[:10]]
    else:
        lines.append(
            "- No added line weakens a check (type ignore, noqa, skip, cast, broad except)."
        )
    pyproject = git(root, "diff", "-U0", f"{base}...HEAD", "--", "pyproject.toml")
    deps = [d for d in new_dependencies(pyproject) if d.lower() not in plan.lower()]
    if deps:
        r.finding(
            "A dependency is added that the plan does not name: "
            + ", ".join(f"`{d}`" for d in deps)
            + "."
        )
        lines.append(
            "- Dependencies added without being in the plan: " + ", ".join(f"`{d}`" for d in deps)
        )
    if stray := uncollected_tests(
        root, git(root, "diff", "--name-only", f"{base}...HEAD").splitlines()
    ):
        r.finding(
            "Test file(s) pytest never collects (the name must start with `test_`): "
            + ", ".join(f"`{f}`" for f in stray)
            + "."
        )
        lines += [f"- Never collected: `{f}`" for f in stray]
    r.section("What the diff contains", lines)


def uncollected_tests(root: Path, changed: list[str]) -> list[str]:
    """Changed tests/*.py files that define `def test_` under a name pytest never collects."""
    out = []
    for f in changed:
        name = f.rsplit("/", 1)[-1]
        if not (f.startswith("tests/") and f.endswith(".py")):
            continue
        if name.startswith("test_") or name.endswith("_test.py") or not (root / f).exists():
            continue
        if re.search(r"(?m)^\s*(?:async\s+)?def test_", (root / f).read_text(errors="ignore")):
            out.append(f)
    return out


def check_owner_files(r: Report, root: Path, n: int, changed: list[str]) -> None:
    adrs = [
        f for f in changed if f.startswith("docs/decisions/") and not f.endswith("0000-template.md")
    ]
    acc = root / "thoughts" / str(n) / "acceptance.md"
    lines = ["- ADRs in this change: " + (", ".join(f"`{a}`" for a in adrs) if adrs else "none")]
    if not acc.exists() or "<what a person does" in acc.read_text():
        r.finding(
            "`acceptance.md` is missing or still the template: Checkpoint 4 can only show "
            "the generic checklist."
        )
        lines.append("- `acceptance.md`: missing, so the owner's phone checklist is generic")
    else:
        lines.append("- `acceptance.md`: written")
    r.section("What the owner needs to try it", lines)


# ---------------------------------------------------------------- the report


def first_paragraph(text: str, heading: str) -> str:
    m = re.search(rf"(?ms)^#+\s*{re.escape(heading)}[^\n]*\n+(.*?)(?=^#|\Z)", text)
    return " ".join(m.group(1).split())[:280] if m else ""


def build(root: Path, n: int, base: str) -> Report:
    r = Report(n)
    t = root / "thoughts" / str(n)
    spec = (t / "spec.md").read_text() if (t / "spec.md").exists() else ""
    plan = (t / "plan.md").read_text() if (t / "plan.md").exists() else ""
    if not spec:
        r.finding("There is no `spec.md` for this issue: nothing to compare the change with.")
    if not plan:
        r.finding("There is no `plan.md` for this issue.")
    merge_base = git(root, "merge-base", base, "HEAD").strip() or base
    changed = [f for f in git(root, "diff", "--name-only", f"{merge_base}..HEAD").splitlines() if f]
    stat = git(root, "diff", "--shortstat", f"{merge_base}..HEAD").strip()
    asked = first_paragraph(spec, "What v1 does") or first_paragraph(spec, "Problem")
    r.card = [f"Asked for: {asked or '(no spec)'}"]
    _, _, invs = check_intent(r, root, spec)
    check_scope(r, root, n, base, changed, plan)
    check_tests(r, root, n, spec, changed)
    check_invariants(r, root, spec, invs, changed, plan)
    check_diff_content(r, root, n, base, plan)
    check_owner_files(r, root, n, changed)
    r.card.append(f"Built: {stat or 'no change against ' + base}.")
    if decision_needed(spec):
        r.finding("The spec says a decision from the owner is needed before any code.")
    return r


def render(r: Report) -> str:
    head = "Drift: CLEAN" if not r.findings else f"Drift: REVIEW ({len(r.findings)})"
    out = [
        f"# Drift report: #{r.n}",
        "",
        head,
        "",
        "_Written by `scripts/drift.py` from the spec, the plan and the diff. "
        "No model wrote this._",
        "",
        "## Card",
        "",
    ] + [f"- {x}" for x in r.card]
    out += ["", "## Findings", ""] + (
        [f"{i}. {f}" for i, f in enumerate(r.findings, 1)] or ["None."]
    )
    for title, lines in r.sections:
        out += ["", f"## {title}", ""] + lines
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("issue", type=int)
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--write", action="store_true", help="write thoughts/<n>/drift.md")
    ap.add_argument("--strict", action="store_true", help="exit 1 when there is a finding")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    report = build(root, a.issue, a.base)
    text = render(report)
    if a.write:
        (root / "thoughts" / str(a.issue)).mkdir(parents=True, exist_ok=True)
        (root / "thoughts" / str(a.issue) / "drift.md").write_text(text)
    print(text)
    return 1 if (a.strict and report.findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
