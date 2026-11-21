import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ratchet = load("ratchet")
trace = load("trace")


def test_ratchet_fails_on_enforced_regression() -> None:
    policy = {
        "metrics": {"max_complexity": {"direction": "lower", "tolerance": 0, "mode": "enforce"}}
    }
    _, failed = ratchet.check(
        {"metrics": {"max_complexity": 15}}, {"metrics": {"max_complexity": 10}}, policy
    )
    assert failed


def test_ratchet_warn_does_not_fail_and_tighten_only_improves() -> None:
    policy = {
        "metrics": {
            "a": {"direction": "lower", "tolerance": 0, "mode": "warn"},
            "b": {"direction": "higher", "tolerance": 0, "mode": "enforce"},
        }
    }
    base = {"metrics": {"a": 1, "b": 80}}
    _, failed = ratchet.check({"metrics": {"a": 5, "b": 90}}, base, policy)
    assert not failed
    changed = ratchet.tighten({"metrics": {"a": 5, "b": 90}}, base, policy)
    assert base["metrics"] == {"a": 1, "b": 90} and changed == ["b: 80 -> 90"]


def test_trace_finds_missing_ac_and_control(tmp_path: Path) -> None:
    issue = tmp_path / "thoughts" / "7"
    issue.mkdir(parents=True)
    (issue / "spec.md").write_text("- [ ] AC1: a\n- [ ] AC2: b\n")
    (issue / "threat-model.md").write_text(
        "| ID | Cat | Threat | Control | Test | Decision |\n|---|---|---|---|---|---|\n"
        "| T1 | x | y | z | t | ACCEPTED |\n| T2 | x | y | z | t | REJECTED |\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text(
        "import pytest\n\n@pytest.mark.ac('AC1')\ndef test_one():\n    assert 1\n\n"
        "def test_two():\n    # T1\n    assert 1\n"
    )
    _, missing = trace.run(tmp_path, [tests])
    assert missing == ["7/AC2"]


def test_health_json_baseline_is_valid() -> None:
    data = json.loads((ROOT / "quality" / "health.json").read_text())
    assert "max_complexity" in data["metrics"]


def test_trace_accepts_comment_above_the_test(tmp_path: Path) -> None:
    issue = tmp_path / "thoughts" / "1"
    issue.mkdir(parents=True)
    (issue / "spec.md").write_text("- [ ] **AC1** Given x\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text("# AC1\ndef test_one():\n    assert 1\n")
    assert trace.run(tmp_path, [tests])[1] == []
