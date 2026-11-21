"""The CI definition itself: it runs on main and tags, and no base-branch step can run on a push."""

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".gitea" / "workflows" / "gates.yml"
PR_ONLY = "if: github.event_name == 'pull_request'"


def steps() -> list[str]:
    """Each step as text: a block that starts with `      - ` and runs to the next one."""
    return re.split(r"(?m)^      - ", WORKFLOW.read_text())[1:]


def test_it_runs_on_pull_requests_main_and_release_tags() -> None:
    head = WORKFLOW.read_text().split("\njobs:")[0]
    assert re.search(r"(?m)^  pull_request:", head)
    push = r"(?m)^  push:\n(?:\s*#.*\n)*\s+branches: \[main\]\n\s+tags: \[\"v\*\"\]"
    assert re.search(push, head)


def test_every_step_that_uses_the_base_branch_runs_on_pull_requests_only() -> None:
    needing_a_base = [s for s in steps() if "BASE_REF" in s]
    # fetch base (twice), holdout guard, new tests fail, quality, mutation
    assert len(needing_a_base) >= 6
    missing = [s.splitlines()[0] for s in needing_a_base if PR_ONLY not in s]
    assert missing == []


def test_the_tree_level_quality_step_exists_for_the_other_events() -> None:
    tree = [s for s in steps() if "QUALITY_TREE_ONLY=1" in s]
    assert len(tree) == 1
    assert "if: github.event_name != 'pull_request'" in tree[0]


def test_the_required_jobs_are_still_there() -> None:
    jobs = WORKFLOW.read_text().split("\njobs:\n")[1]
    assert {"checks", "gates", "security", "holdout", "quality"} <= set(
        re.findall(r"(?m)^  (\w+):\s*$", jobs)
    )
