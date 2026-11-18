"""budget.py: the cap of a run, the pause gate, `extend` and `raise`."""
from __future__ import annotations

import json
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import budget  # noqa: E402

PLAN_TEXT = "# P\n\n**Goal:** x.\n{hdr}\n"


def make(tmp_path, cap="3.00", mode=None, ledger=None):
    hdr = f"**Budget-usd:** {cap}\n" if cap else ""
    p = tmp_path / "plan.md"
    p.write_text(PLAN_TEXT.format(hdr=hdr), encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    if mode:
        (sl / "orchestrator.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")
    if ledger:
        (sl / "progress.md").write_text(ledger, encoding="utf-8")
    return p, sl


def fake(cost=3.2, cap=3.0, state="over", need=4.1, extended=False, projected=None):
    return {"cost_usd": cost, "cap_usd": cap, "state": state, "need_usd": need, "extended": extended, "projected_usd": projected,
            "coordinator_usd": 0.0, "agents_usd": cost, "elapsed_min": 1.0, "projected_min": 2.0, "target_min": None,
            "pct_cap": 1.0, "stats": "n=0", "hint": None, "late": False, "late_path": [], "summaries": None}


def patch(monkeypatch, **kw):
    monkeypatch.setattr(budget, "compute", lambda *a, **k: fake(**kw))


def test_effective_cap_header_then_newest_ledger_line(tmp_path):
    p, sl = make(tmp_path)
    import plan_tools as pt
    plan = pt.Plan.load(str(p))
    assert budget.effective_cap(plan, sl) == 3.0
    (sl / "progress.md").write_text("- Budget cap: 3.75 (extend) - a\n- Budget cap: 6 (raise) - b\n", encoding="utf-8")
    assert budget.effective_cap(plan, sl) == 6.0
    (tmp_path / "plan.md").write_text(PLAN_TEXT.format(hdr=""), encoding="utf-8")
    assert budget.effective_cap(pt.Plan.load(str(p)), tmp_path / "none") is None


def test_gate_line_over_cap_ai_not_extended(tmp_path, monkeypatch):
    p, sl = make(tmp_path, mode="ai")
    patch(monkeypatch)
    assert budget.gate(p, sl) == ("budget: paused: spent $3.20 of $3.00 cap; least cap to finish $4.10; "
                                  f'once: sl budget extend --plan {p} --ruling "<why>" (+25%)')


def test_gate_line_after_extension_names_raise(tmp_path, monkeypatch):
    p, sl = make(tmp_path, mode="ai")
    patch(monkeypatch, extended=True)
    assert budget.gate(p, sl).endswith(f'stop the run; the user raises it: sl budget raise --to 4.10 --ruling "<their words>" --plan {p}')


def test_gate_none_under_cap_and_without_cap(tmp_path, monkeypatch):
    p, sl = make(tmp_path, mode="ai")
    for st in ("warn", "ok"):
        patch(monkeypatch, state=st)
        assert budget.gate(p, sl) is None
    patch(monkeypatch, cap=None, state="ok")
    assert budget.gate(p, sl) is None


def test_gate_never_raises(tmp_path, capsys):
    assert budget.gate(tmp_path / "missing.md", tmp_path / ".superlite") is None
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err == ""


def test_extend_once_adds_25_percent(tmp_path, monkeypatch, capsys):
    p, sl = make(tmp_path, mode="ai")
    patch(monkeypatch)
    assert budget.main(["extend", "--plan", str(p), "--dir", str(sl), "--ruling", "why"]) == 0
    assert capsys.readouterr().out.strip() == "budget: cap $3.00 -> $3.75 (extended once, +25%)"
    assert (sl / "progress.md").read_text(encoding="utf-8") == "- Budget cap: 3.75 (extend) - why\n"
    before = (sl / "progress.md").read_text(encoding="utf-8")
    assert budget.main(["extend", "--plan", str(p), "--dir", str(sl), "--ruling", "again"]) == 2
    assert "already extended" in capsys.readouterr().err
    assert (sl / "progress.md").read_text(encoding="utf-8") == before


def test_extend_refused_for_human_orchestrator(tmp_path, monkeypatch, capsys):
    p, sl = make(tmp_path, mode="human")
    patch(monkeypatch)
    assert budget.main(["extend", "--plan", str(p), "--dir", str(sl), "--ruling", "why"]) == 2
    assert "AI orchestrator" in capsys.readouterr().err
    assert not (sl / "progress.md").exists()


def test_extend_and_raise_need_a_cap_and_a_ruling(tmp_path, monkeypatch):
    patch(monkeypatch)
    p, sl = make(tmp_path, cap=None, mode="ai")
    for cmd in ("extend", "raise"):
        assert budget.main([cmd, "--plan", str(p), "--dir", str(sl), "--ruling", "why", "--to", "9"]) == 2
    p, sl = make(tmp_path, mode="ai")
    for cmd in ("extend", "raise"):
        assert budget.main([cmd, "--plan", str(p), "--dir", str(sl), "--ruling", "", "--to", "9"]) == 2
    assert not (sl / "progress.md").exists()


def test_raise_must_be_above_spend(tmp_path, monkeypatch, capsys):
    p, sl = make(tmp_path, mode="ai")
    patch(monkeypatch)
    assert budget.main(["raise", "--to", "3", "--ruling", "user", "--plan", str(p), "--dir", str(sl)]) == 2
    assert budget.main(["raise", "--to", "6", "--ruling", "user", "--plan", str(p), "--dir", str(sl)]) == 0
    assert "budget: cap $3.00 -> $6.00 (raised)" in capsys.readouterr().out
    import plan_tools as pt
    assert budget.effective_cap(pt.Plan.load(str(p)), sl) == 6.0


def test_need_is_projection_rounded_up():
    assert budget.need_usd(3.2, 4.0934) == 4.10
    assert budget.need_usd(3.2, None) == 3.20
    assert budget.need_usd(3.2, 1.0) == 3.20


def test_flag_only_form_still_prints_the_line(tmp_path, monkeypatch, capsys):
    p, sl = make(tmp_path, mode="ai")
    patch(monkeypatch, state="ok", cost=1.0)
    assert budget.main(["--plan", str(p), "--dir", str(sl)]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("budget:")


def test_warn_names_projection_against_cap():
    out = budget.line(fake(state="warn", cost=1.0, projected=2.4))
    assert "WARN: 70% of the cap reached; projected $2.40 against the $3.00 cap" in out


def test_over_line_says_paused(tmp_path):
    p, sl = make(tmp_path, mode="ai")
    b = fake()
    b["plan"], b["dir"] = str(p), str(sl)
    out = budget.line(b)
    assert "OVER CAP: paused" in out
    assert out.split("OVER CAP: paused: ")[1].startswith("spent $3.20 of $3.00 cap")
