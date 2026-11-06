from __future__ import annotations

from test_plan_tools import SCRIPTS, run
from test_stable_split import DISPATCH
from test_wave0 import PY, plan


def lines(cp):
    return cp.out.splitlines()


def staged(tmp_path, ledger_text=""):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    run(SCRIPTS / "plan_tools.py", "lint", "--stable", "--plan", p, cwd=tmp_path)
    led = tmp_path / ".superlite" / "progress.md"
    led.write_text(ledger_text, encoding="utf-8")
    args = ("--plan", p, "--pool", tmp_path / "pool.json", "--ledger", led)
    return args, led


def test_dispatch_committed_t0_offers_stub_owner(tmp_path):
    args, _ = staged(tmp_path)
    out = lines(run(DISPATCH, *args, "--committed", "T0", cwd=tmp_path))
    assert any(ln.startswith("T1 ") for ln in out)
    assert not any(ln.startswith("T0 ") for ln in out)


def test_dispatch_skips_held_task(tmp_path):
    args, led = staged(tmp_path, "- commit T0 abcdef1234 skeleton\n- Hold T1: ssh sign-in\n")
    cp = run(DISPATCH, *args, cwd=tmp_path)
    assert not any(ln.startswith("T1 ") for ln in lines(cp))
    assert "held=T1 ssh sign-in" in cp.err
    led.write_text(led.read_text(encoding="utf-8") + "- Release T1\n", encoding="utf-8")
    assert any(ln.startswith("T1 ") for ln in lines(run(DISPATCH, *args, cwd=tmp_path)))


def test_dispatch_held_t0_has_no_wave0_line(tmp_path):
    args, _ = staged(tmp_path, "- Hold T0: waits for the human\n")
    assert not any(ln.startswith("T0 ") for ln in lines(run(DISPATCH, *args, cwd=tmp_path)))


def test_committed_held_task_not_reported(tmp_path):
    args, _ = staged(tmp_path, "- commit T0 abcdef1234 skeleton\n- Hold T1: x\n- commit T1 abcdef1234 t1\n")
    assert "held=T1" not in run(DISPATCH, *args, cwd=tmp_path).err
