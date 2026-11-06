"""sl hold: hold and release tasks in the ledger."""
from __future__ import annotations

from test_plan_tools import SCRIPTS, run
from test_wave0 import PY, plan

HOLD = SCRIPTS / "hold.py"


def hold(tmp_path, *args):
    return run(HOLD, *args, "--ledger", tmp_path / "progress.md")


def ledger(tmp_path):
    return (tmp_path / "progress.md").read_text(encoding="utf-8")


def test_hold_appends_line(tmp_path):
    cp = hold(tmp_path, "T5", "--reason", "ssh sign-in")
    assert cp.returncode == 0
    assert cp.out.strip() == "held T5: ssh sign-in"
    assert ledger(tmp_path).endswith("- Hold T5: ssh sign-in\n")


def test_list_shows_reason(tmp_path):
    assert hold(tmp_path).out.strip() == "held: none"
    hold(tmp_path, "T5", "--reason", "ssh sign-in")
    assert hold(tmp_path).out.strip() == "held T5: ssh sign-in"


def test_release(tmp_path):
    hold(tmp_path, "T5", "--reason", "ssh sign-in")
    cp = hold(tmp_path, "--release", "T5")
    assert cp.returncode == 0
    assert cp.out.strip() == "released T5"
    assert "- Release T5" in ledger(tmp_path)
    assert hold(tmp_path).out.strip() == "held: none"


def test_release_not_held_refused(tmp_path):
    hold(tmp_path, "T6", "--reason", "x")
    before = ledger(tmp_path)
    cp = hold(tmp_path, "--release", "T5")
    assert cp.returncode == 2
    assert "T5 is not held" in cp.err
    assert ledger(tmp_path) == before


def test_reason_required(tmp_path):
    assert hold(tmp_path, "T5").returncode == 2
    assert hold(tmp_path, "T5", "--reason", "  ").returncode == 2
    assert not (tmp_path / "progress.md").exists()


def test_bad_id_refused(tmp_path):
    assert hold(tmp_path, "t5", "--reason", "x").returncode == 2
    assert hold(tmp_path, "T", "--reason", "x").returncode == 2
    assert not (tmp_path / "progress.md").exists()


def test_plan_unknown_task_refused(tmp_path):
    p = plan(tmp_path, "Python", "none", PY)
    cp = hold(tmp_path, "T9", "--reason", "x", "--plan", p)
    assert cp.returncode == 2
    assert "T9" in cp.err and "T1 T2" in cp.err
    assert not (tmp_path / "progress.md").exists()


def test_committed_task_refused(tmp_path):
    (tmp_path / "progress.md").write_text("- commit T1 abcdef1234 x\n", encoding="utf-8")
    cp = hold(tmp_path, "T1", "--reason", "x")
    assert cp.returncode == 2
    assert "already committed" in cp.err


def test_multiline_reason_one_line(tmp_path):
    hold(tmp_path, "T5", "--reason", "a\nb")
    assert "- Hold T5: a b\n" in ledger(tmp_path)


def test_two_ids_one_call(tmp_path):
    cp = hold(tmp_path, "T5", "T6", "--reason", "x")
    assert cp.returncode == 0
    assert cp.out.splitlines() == ["held T5: x", "held T6: x"]
    assert ledger(tmp_path).count("- Hold T") == 2
