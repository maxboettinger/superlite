from __future__ import annotations

from test_plan_tools import SCRIPTS, run

FINISH = SCRIPTS / "finish.py"


def summary(tmp_path, text):
    led = tmp_path / "progress.md"
    led.write_text(text, encoding="utf-8")
    return run(FINISH, "--ledger", led, "--log", tmp_path / "incidents.jsonl", cwd=tmp_path).out.splitlines()


def test_finish_lists_held(tmp_path):
    out = summary(tmp_path, "- Hold T5: ssh sign-in\n- Hold T7: App Store sign-in\n")
    i = out.index("held: 2 (still waiting for a human step)")
    assert out[i + 1:i + 4] == ["- T5: ssh sign-in", "- T7: App Store sign-in", "- release one: sl hold --release Tn"]


def test_finish_skips_released_and_committed(tmp_path):
    out = summary(tmp_path, "- Hold T5: x\n- Release T5\n- Hold T6: y\n- commit T6 abcdef1234 t6\n")
    assert not any(ln.startswith("held:") for ln in out)
