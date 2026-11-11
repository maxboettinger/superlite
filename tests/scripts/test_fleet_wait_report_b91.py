"""Seam: a labelled report reaches fleet wait whole; --full reaches a final reviewer; the docs name the Checked lines (B91)."""
import json
from pathlib import Path
from test_fleet_io import assistant, io, rec, stop_at, user, world, HOOK  # noqa: F401  (world is a fixture)
from test_fleet_io_ask_470 import setw, prompts  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
LAB = ("Status: DONE_WITH_CONCERNS\n\nFiles changed:\n- `skills/a.py`\n- tests/test_a.py: new cases\n* docs/a.md\n\n"
       "Test: tests (fast): 37 passed, 0 failed\nRed run: tests (fast): 2 failed\nConcerns:\n- slow path untested\n- **name clash** with b.py\n")


def test_wait_collects_a_labelled_report_in_full(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w1.jsonl"; rec(tr, user("task"), assistant(LAB)); stop_at(world, tr, sent + 10)
    world.fh.states = [{"sl-proj-w1": "done"}]
    out = io.wait(world.sd, ["W1"], 5000)
    assert out[0]["status"] == "DONE_WITH_CONCERNS"
    rep = json.loads((world.sd / "fleet" / "reports" / "T3.json").read_text())
    assert rep["files"] == ["skills/a.py", "tests/test_a.py", "docs/a.md"]
    assert rep["concerns"] == ["slow path untested", "name clash with b.py"]
    assert "findings=0 concerns=2" in capsys.readouterr().out


def test_labelled_report_beats_a_later_hook_status(tmp_path):
    tr = tmp_path / "t.jsonl"
    rec(tr, user("task"), assistant(LAB), HOOK, assistant("Uncommitted work warning\nStatus: DONE"))
    assert io.report_text(tr) == LAB


def test_full_brief_reaches_the_final_reviewer(world):
    setw(world, "W2", role="final-reviewer")
    p = world.sd / "briefs" / "packet.md"; p.parent.mkdir(exist_ok=True); p.write_text("packet\n")
    assert io.main(["send", "W2", "--brief", str(p), "--full"]) == 0
    assert "Full review: the packet's FAST PATH line does not apply" in prompts(world)[-1][2]


def test_final_reviewer_fast_path_lists_checked():
    doc = (ROOT / "agents" / "final-reviewer.md").read_text()
    line = next(l for l in doc.splitlines() if l.startswith("- Fast path"))
    for s in ("`FAST PATH`", "inline", "`Full review`", "`Checked:`"):
        assert s in line, s
    assert "On the fast path reply with the bare verdict line" not in doc
    skill = (ROOT / "skills" / "subagent-driven-development" / "SKILL.md").read_text()
    assert "fast path too" in skill and "--full" in skill
