"""Package review, run tooling batch 6: a repeated `finish` adds no duplicate `auto` feedback entries (#140), and two plans
of one session each keep their own run folder (#178)."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from test_run_scripts import SCRIPTS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import feedback  # noqa: E402
import finish  # noqa: E402
import state  # noqa: E402


def stop(tool, target):
    return {"kind": "rule-block", "agent": "coordinator", "tool": tool, "target": target}


def run_folder(root, rows):
    sl = root / ".superlite"
    sl.mkdir(parents=True)
    (sl / "pool.json").write_text("{}", encoding="utf-8")
    (sl / "progress.md").write_text("- commit T1 abc1234567 slug\n", encoding="utf-8")
    (sl / "incidents.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    plan = root / "plan.md"
    plan.write_text("# plan\n", encoding="utf-8")
    return plan, sl


def inbox(home):
    p = Path(home) / "feedback.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_repeated_finish_adds_no_duplicates(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    plan, sl = run_folder(tmp_path / "run", [stop("block-coordinator-edits", f"src/{c}.py") for c in "abc"])
    for _ in range(2):
        assert finish.main(["--plan", str(plan)]) == 0
    capsys.readouterr()
    assert len(inbox(home)) == 3  # three distinct stops, once each
    with open(sl / "incidents.jsonl", "a", encoding="utf-8") as f:  # a new stop of the same signature still counts
        f.write(json.dumps(stop("block-coordinator-edits", "src/d.py")) + "\n")
    assert finish.main(["--plan", str(plan)]) == 0
    assert len(inbox(home)) == 4


def test_two_plans_keep_their_own_run(tmp_path, monkeypatch):
    runs = []
    for n in ("a", "b"):
        wt = tmp_path / n
        wt.mkdir()
        (wt / ".git").write_text(f"gitdir: {tmp_path}/.git/worktrees/{n}\n", encoding="utf-8")
        (wt / ".superlite").mkdir()
        (wt / ".superlite" / "pool.json").write_text("{}", encoding="utf-8")
        (wt / "plan.md").write_text("# p\n", encoding="utf-8")
        runs.append(wt)
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    monkeypatch.chdir(runs[0])
    assert state.for_plan(runs[1] / "plan.md") == runs[1] / ".superlite"
    assert state.resolve() == runs[0] / ".superlite"
