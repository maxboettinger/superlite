from __future__ import annotations

from test_plan_tools import SCRIPTS, run
from test_stable_lapse import cli_plan
from test_stable_split import DISPATCH

REASON = "unstable=T2 T2: Owns has a placeholder; rerun sl lint --stable"


def setup(tmp_path, ledger_text="", stable=True):
    from test_stable_lapse import STABLE
    p = cli_plan(tmp_path, STABLE if stable else None)
    led = tmp_path / ".superlite" / "progress.md"
    led.write_text(ledger_text, encoding="utf-8")
    return ("--plan", p, "--pool", tmp_path / "pool.json", "--ledger", led)


def lines(cp):
    return cp.out.splitlines()


def test_dispatch_offers_lapsed_fix_task(tmp_path):
    args = setup(tmp_path, "- commit T1 abcdef1234 a\n- commit T2 abcdef1234 b\n")
    assert any(ln.startswith("T3 ") for ln in lines(run(DISPATCH, *args, cwd=tmp_path)))


def test_dispatch_prints_unstable_reason(tmp_path):
    args = setup(tmp_path, "- commit T1 abcdef1234 a\n")
    cp = run(DISPATCH, *args, cwd=tmp_path)
    assert not any(ln.startswith("T") for ln in lines(cp))
    assert REASON in cp.err


def test_dispatch_committed_flag_spaces(tmp_path):
    args = setup(tmp_path)
    assert any(ln.startswith("T3 ") for ln in lines(run(DISPATCH, *args, "--committed", "T1 T2", cwd=tmp_path)))
    cp = run(DISPATCH, *args, "--committed", "T1,T7", cwd=tmp_path)
    assert "warning: --committed: T7 is not a task of the plan" in cp.err


def test_dispatch_held_task_not_unstable(tmp_path):
    args = setup(tmp_path, "- commit T1 abcdef1234 a\n- Hold T2: waits\n")
    cp = run(DISPATCH, *args, cwd=tmp_path)
    assert "held=T2 waits" in cp.err
    assert "unstable=T2" not in cp.err


def test_dispatch_without_stable_json_silent(tmp_path):
    args = setup(tmp_path, "", stable=False)
    assert "unstable=" not in run(DISPATCH, *args, cwd=tmp_path).err
