# tests/scripts/test_review_hold_741.py
"""#741: a committed task that shares a file with an uncommitted one gets a held line, then one group hint."""
import json, sys
import pytest
from test_fleet_for_review_422 import rw  # noqa: F401
from test_fleet import world  # noqa: F401
from test_commit_task_b94 import run  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io as io  # noqa: E402

PLAN = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

## Package: core (lib)

### T1 first · Complexity 3 · Est. context 30k
**Owns:** src/a.py

### T2 second · Complexity 3 · Est. context 30k
**Owns:** src/a.py, src/b.py

### T3 third · Complexity 3 · Est. context 30k
**Owns:** src/b.py

### T4 alone · Complexity 6 · Est. context 30k
**Owns:** src/z.py
"""


def mk(tmp_path, text=PLAN):
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    plan = proj / "plan.md"; plan.write_text(text, encoding="utf-8")
    return sd, str(plan)


def ledger(sd, *tids):
    (sd / "progress.md").write_text("".join(f"- commit {t} abc1234 x\n" for t in tids), encoding="utf-8")


def test_hint_held_while_sharer_uncommitted(tmp_path):
    sd, plan = mk(tmp_path)
    ledger(sd, "T1")
    assert io.review_hints(sd, plan) == []
    assert io.held_hints(sd, plan) == [("T1", ["T2", "T3"], ["src/a.py", "src/b.py"])]


def test_held_names_waiting_and_shared_file_for_pair(tmp_path):
    sd, plan = mk(tmp_path, PLAN.replace("### T3", "### T9").replace("src/b.py\n\n### T4", "src/q.py\n\n### T4").replace("**Owns:** src/a.py, src/b.py", "**Owns:** src/a.py"))
    ledger(sd, "T1")
    assert io.held_hints(sd, plan) == [("T1", ["T2"], ["src/a.py"])]


def test_group_hint_after_last_commit(tmp_path):
    text = PLAN.replace("### T3 third", "### T9 third").replace("src/b.py\n\n### T4", "src/q.py\n\n### T4").replace("**Owns:** src/a.py, src/b.py", "**Owns:** src/a.py")
    sd, plan = mk(tmp_path, text)
    ledger(sd, "T1", "T2")
    assert io.review_hints(sd, plan) == [("T1 T2", ["T1: seam T1↔T2", "T2: seam T1↔T2", "shared src/a.py"])]
    assert io.held_hints(sd, plan) == []


def test_unshared_task_hint_unchanged(tmp_path):
    sd, plan = mk(tmp_path)
    ledger(sd, "T4")
    assert io.review_hints(sd, plan) == [("T4", ["Complexity 6"])]
    assert io.held_hints(sd, plan) == []


def test_also_touches_counts_as_shared(tmp_path):
    text = PLAN.replace("**Owns:** src/z.py", "**Owns:** src/z.py\n**Also-touches:** src/a.py")
    sd, plan = mk(tmp_path, text)
    pl = io.pt.Plan.load(plan)
    assert "T4" in io.share_group(pl, "T1")
    ledger(sd, "T4")
    assert io.review_hints(sd, plan) == []
    assert io.held_hints(sd, plan)[0][0] == "T4"


def test_transitive_group(tmp_path):
    sd, plan = mk(tmp_path)
    pl = io.pt.Plan.load(plan)
    assert io.share_group(pl, "T1") == ["T1", "T2", "T3"]
    assert io.share_group(pl, "T4") == ["T4"]
    ledger(sd, "T1", "T2")
    assert io.review_hints(sd, plan) == []
    assert [h[0] for h in io.held_hints(sd, plan)] == ["T1", "T2"]
    assert io.held_hints(sd, plan)[0][1] == ["T3"]
    ledger(sd, "T1", "T2", "T3")
    hints = io.review_hints(sd, plan)
    assert [h[0] for h in hints] == ["T1 T2 T3"]
    assert hints[0][1][-1] == "shared src/a.py, src/b.py"


def test_covered_member_left_out_of_label(tmp_path):
    sd, plan = mk(tmp_path)
    ledger(sd, "T1", "T2", "T3")
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W5": {"review": ["T1"]}}}))
    assert io.review_hints(sd, plan)[0][0] == "T2 T3"


def test_hint_lines_text(tmp_path):
    sd, plan = mk(tmp_path)
    ledger(sd, "T1")
    assert io.hint_lines(sd, plan, "/sl") == ["review: T1 held until T2, T3 commit (shared src/a.py, src/b.py)"]
    ledger(sd, "T1", "T2", "T3")
    lines = io.hint_lines(sd, plan, "/sl")
    assert lines == [f"review: T1 T2 T3 ({'; '.join(io.review_hints(sd, plan)[0][1])}); run /sl fleet spawn --for-review T1 T2 T3 --plan {plan}"]
    assert io.hint_lines(sd, plan, "/sl", {"T9"}) == []


def test_for_dispatch_prints_held_line(world, monkeypatch, capsys):
    import dispatch
    sd = world.sd
    (sd / "progress.md").write_text("- commit T1 abc1234 x\n")
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: ([], {}))
    monkeypatch.setattr(dispatch, "render", lambda *a, **k: None)
    plan = world.proj / "p2.md"; plan.write_text(PLAN)
    fleet.main(["on"]); capsys.readouterr()
    fleet.main(["spawn", "--for-dispatch", "--plan", str(plan)])
    out = capsys.readouterr().out
    assert "review: T1 held until T2, T3 commit (shared src/a.py, src/b.py)" in out
    assert "fleet spawn --for-review T1 " not in out


def test_commit_task_dispatch_prints_held_and_group_lines(run, monkeypatch, capsys):
    import dispatch, commit_task
    from test_commit_task_b94 import write
    repo, sd, plan = run
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}}), encoding="utf-8")
    monkeypatch.setattr(io, "review_hints", lambda s, p: [("T1 T7", ["T1: Complexity 6", "shared a.py"]), ("T8", ["x"])])
    monkeypatch.setattr(io, "held_hints", lambda s, p: [("T1", ["T2", "T3"], ["a.py", "b.py"]), ("T9", ["T2"], ["c.py"])])
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: ())
    monkeypatch.setattr(dispatch, "render", lambda *a, **k: None)
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan, "--dispatch"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("review:")]
    sl = commit_task.nt.SCRIPTS / "sl"
    assert lines == [f"review: T1 T7 (T1: Complexity 6; shared a.py); run {sl} fleet spawn --for-review T1 T7 --plan {plan}",
                     "review: T1 held until T2, T3 commit (shared a.py, b.py)"]


def refuse(rw, *args):
    assert fleet.main(["spawn", *args, "--plan", str(rw.plan)]) == 3


def test_for_review_refuses_held_task(rw, capsys):
    rw.plan.write_text(PLAN)
    (rw.sd / "progress.md").write_text("- commit T1 abc1234 x\n")
    capsys.readouterr()
    refuse(rw, "--for-review", "T1")
    assert "BLOCKED: T1 shares src/a.py with T2, T3, not committed yet; run --for-review T1 T2 T3 after T2, T3 commit" in capsys.readouterr().out
    assert rw.spawns == [] and rw.sends == []
    assert not (rw.sd / "briefs" / "review-T1.md").exists()


def test_for_review_refuses_held_package(rw, capsys):
    rw.plan.write_text(PLAN)
    (rw.sd / "progress.md").write_text("- commit T1 abc1234 x\n")
    capsys.readouterr()
    refuse(rw, "--package", "core")
    assert "BLOCKED: T1 shares" in capsys.readouterr().out
    assert rw.spawns == [] and not list((rw.sd / "briefs").glob("review-*.md"))


def test_for_review_single_waiting_text_and_ok_when_all_committed(rw, capsys):
    rw.plan.write_text(PLAN.replace("### T3", "### T9").replace("src/b.py\n\n### T4", "src/q.py\n\n### T4").replace("**Owns:** src/a.py, src/b.py", "**Owns:** src/a.py"))
    (rw.sd / "progress.md").write_text("- commit T1 abc1234 x\n")
    capsys.readouterr()
    refuse(rw, "--for-review", "T1")
    assert "BLOCKED: T1 shares src/a.py with T2, not committed yet; run --for-review T1 T2 after T2 commits" in capsys.readouterr().out
    (rw.sd / "progress.md").write_text("- commit T1 abc1234 x\n- commit T2 abc1235 y\n")
    assert fleet.main(["spawn", "--for-review", "T1", "T2", "--plan", str(rw.plan)]) == 0
