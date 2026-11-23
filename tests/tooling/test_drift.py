import importlib.util
import subprocess
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


drift = load("drift")


def test_spec_refs_strip_comments_and_read_the_decision() -> None:
    spec = (
        "- Serves: G2   <!-- goal -->\n- Touches: N1, I3\n"
        "- Decision needed from the owner before any code: yes\n"
    )
    refs = drift.spec_refs(spec)
    assert refs["serves"] == "G2"
    assert refs["touches"] == "N1, I3"
    assert drift.decision_needed(spec)
    assert not drift.decision_needed("- Decision needed from the owner before any code: no\n")


def test_intent_and_invariant_ids() -> None:
    goals, nevers = drift.intent_ids("- **G1** a\n- **G2** b\n- **N1** never\n")
    assert goals == {"G1", "G2"} and nevers == {"N1"}
    assert drift.invariant_ids("| ID | x |\n|---|---|\n| I1 | a |\n| I2 | b |\n") == {"I1", "I2"}


def test_planned_matches_file_directory_and_name() -> None:
    paths = drift.plan_paths("Files: `src/app/ui.py`, `src/app/templates/`, tests/unit/test_ui.py")
    assert drift.planned("src/app/ui.py", paths, 6)
    assert drift.planned("src/app/templates/result.html", paths, 6)
    assert drift.planned("thoughts/6/validation.md", paths, 6)
    assert not drift.planned("src/app/ocr.py", paths, 6)


def test_new_dependencies_and_added_lines() -> None:
    diff = '+++ b/pyproject.toml\n+    "pillow>=13.0.0",\n+    "x-y_z==1.0",\n+version = "1"\n'
    assert drift.new_dependencies(diff) == ["pillow", "x-y_z"]
    assert drift.WEAKENED.search("x = 1  # type: ignore")
    assert not drift.WEAKENED.search("def cast_vote(): pass")


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_report_flags_unplanned_files_missing_tests_and_missing_intent(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "thoughts" / "7").mkdir(parents=True)
    (tmp_path / "thoughts" / "7" / "spec.md").write_text("- [ ] AC1: a\n- [ ] AC2: b\n")
    (tmp_path / "thoughts" / "7" / "plan.md").write_text("- [ ] Files: `src/a.py`\n")
    (tmp_path / "README.md").write_text("x")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "agent/issue-7")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    (tmp_path / "src" / "b.py").write_text("y = 2  # type: ignore\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_issue_7.py").write_text("# AC1\ndef test_one():\n    assert True\n")
    (tmp_path / "tests" / "holdout_test_issue_7.py").write_text(
        "def test_two():\n    assert True\n"
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "work")
    text = drift.render(drift.build(tmp_path, 7, "main"))
    assert "Drift: REVIEW" in text
    assert "`src/b.py`" in text.split("Changed but not in the plan")[1].split("\n")[0]
    assert "AC2 has no test" in text
    assert "docs/intent.md` does not exist" in text
    assert "weaken a check" in text
    assert "acceptance.md" in text
    assert "never collects" in text and "holdout_test_issue_7.py" in text
    assert "AC1: `tests/test_issue_7.py" in text


def test_a_matching_test_from_another_issue_does_not_count(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "thoughts" / "9").mkdir(parents=True)
    (tmp_path / "thoughts" / "9" / "spec.md").write_text("- [ ] AC1: a\n")
    (tmp_path / "thoughts" / "9" / "plan.md").write_text("plan\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_old.py").write_text("# AC1\ndef test_old():\n    assert True\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "agent/issue-9")
    (tmp_path / "x.txt").write_text("x")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "work")
    text = drift.render(drift.build(tmp_path, 9, "main"))
    assert "only a test by the same name from elsewhere" in text
