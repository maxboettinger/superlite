"""#739: the judge's wall-clock budget comes from SUPERLITE_GUARD_SECONDS when valid; the step budget still holds."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_judge  # noqa: E402
from guard_judge import Verdict, judge  # noqa: E402
from test_block_coordinator_edits import bash, proj  # noqa: E402,F401

UNK = Verdict("?", "?", "code")


@pytest.fixture
def P(tmp_path):
    p = (tmp_path / "p").resolve()
    for d in ("src", "docs/plans", ".superlite"):
        (p / d).mkdir(parents=True)
    return str(p)


def test_the_suite_raises_the_time_budget():
    # conftest.py sets it at import: hook subprocesses and nested pytest runs inherit it
    assert guard_judge._seconds() == 30.0


@pytest.mark.parametrize("raw,want", [
    ("30", 30.0), ("0.5", 0.5), ("12", 12.0),
    ("", 1.5), ("abc", 1.5), ("0", 1.5), ("-1", 1.5), ("31", 1.5), ("nan", 1.5), ("inf", 1.5),
])
def test_seconds_reads_the_variable(monkeypatch, raw, want):
    monkeypatch.setenv("SUPERLITE_GUARD_SECONDS", raw)
    assert guard_judge._seconds() == want


def test_seconds_without_the_variable_is_max_seconds(monkeypatch):
    monkeypatch.delenv("SUPERLITE_GUARD_SECONDS", raising=False)
    monkeypatch.setattr(guard_judge, "MAX_SECONDS", 2.5)
    assert guard_judge._seconds() == 2.5


def test_a_spent_time_budget_makes_the_command_unknown(P, monkeypatch, proj):  # noqa: F811
    monkeypatch.setenv("SUPERLITE_GUARD_SECONDS", "1e-9")
    assert judge("echo hi > docs/plans/a.md", P, P, "active") == UNK
    assert bash(proj, "echo hi > docs/plans/a.md").returncode == 2  # the hook's judge reads it too
    monkeypatch.setenv("SUPERLITE_GUARD_SECONDS", "30")
    assert judge("echo hi > docs/plans/a.md", P, P, "active") is None
    assert bash(proj, "echo hi > docs/plans/a.md").returncode == 0


def test_the_step_budget_holds_with_a_raised_time_budget(P, monkeypatch):
    monkeypatch.setenv("SUPERLITE_GUARD_SECONDS", "30")
    monkeypatch.setattr(guard_judge, "MAX_STEPS", 0)
    assert judge("echo hi > docs/plans/a.md", P, P, "active") == UNK
