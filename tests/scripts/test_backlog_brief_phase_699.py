# tests/scripts/test_backlog_brief_phase_699.py
import sys

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven", "8": "Eight"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}, "text": "default"}
TWO = {"id": "B1", "topic": "x", "issues": [7, 8], "files": ["a.py"]}
ONE = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "decisions": []}
TAIL = "superlite:subagent-driven-development with fleet on"


def test_plan_phase_default():
    t = bb.lead_brief(TWO, {**CTX, "phase": "plan"})
    assert "Plan: superlite:brainstorming (AI orchestrator, no questions), superlite:writing-plans, then stop: this is the plan phase" in t
    assert "Status: DONE planned: <plan path from the worktree root>" in t
    for s in (TAIL, "Ship: allowed", "Simulators:", "Acceptance:"):
        assert s not in t


def test_plan_phase_lean():
    t = bb.lead_brief(ONE, {**CTX, "text": "lean", "phase": "plan"})
    assert "skip superlite:brainstorming" in t and "Both paths then stop: this is the plan phase" in t
    assert "Both paths then run" not in t


def test_build_phase():
    t = bb.lead_brief(TWO, {**CTX, "phase": "build", "plan": "docs/plans/p.md", "summaries": ["/r/B1.md"]})
    for s in ("You are the build lead of batch B1", "A planning lead wrote and linted the plan docs/plans/p.md",
              "Build (build lead, plan docs/plans/p.md): no superlite:brainstorming", TAIL, "Ship: allowed",
              "Rulings from shipped batches: applied in the plan"):
        assert s in t
    assert "/r/B1.md" not in t and "superlite:writing-plans, superlite" not in t


def test_no_phase_unchanged():
    t = bb.lead_brief(TWO, CTX)
    assert t == bb.lead_brief(TWO, {**CTX, "phase": None})
    assert ("Build: superlite:brainstorming (AI orchestrator, no questions), superlite:writing-plans, "
            "superlite:subagent-driven-development with fleet on") in t


def test_pick_summaries():
    sh = [{"id": f"B{n}", "path": f"/r/B{n}.md", "files": [f"f{n}.py"], "text": ""} for n in range(1, 9)]
    sh[1]["files"] = ["s/x.py"]
    sh[2]["text"] = "Ruling: x.py now ..."
    got = bb.pick_summaries({"files": ["s/x.py", "docs/tools.md"]}, sh, last=2)
    assert got == (["/r/B2.md", "/r/B3.md", "/r/B7.md", "/r/B8.md"], 4)


def test_short_basename_ignored():
    sh = [{"id": "B1", "path": "/r/B1.md", "files": [], "text": "run sl backlog"}]
    assert bb.pick_summaries({"files": ["skills/x/scripts/sl"]}, sh, last=0) == ([], 1)


def test_shared_file_ignored():
    sh = [{"id": f"B{n}", "path": f"/r/B{n}.md", "files": [], "text": "docs/tools.md" if n < 12 else ""} for n in range(40)]
    sh[30]["text"] = "see a/b.py"
    sh[12]["text"] = "docs/tools.md"
    got = bb.pick_summaries({"files": ["docs/tools.md", "a/b.py"]}, sh, last=0)
    assert got == (["/r/B30.md"], 39)


def test_more_line():
    t = bb.lead_brief(TWO, {**CTX, "summaries": ["/r/B8.md"], "summaries_more": {"count": 4, "dir": "/r/.superlite/backlog"}})
    lines = t.splitlines()
    i = lines.index("Rulings from shipped batches: /r/B8.md (read each; at most 10 lines).")
    assert lines[i + 1] == ("Other shipped summaries: 4 more in /r/.superlite/backlog "
                            "(one B<n>.md per batch; read one only when a ruling you need is missing).")


def test_brief_shrinks():
    sh = [{"id": f"B{n}", "path": f"/r/.superlite/backlog/B{n}.md", "files": [f"f{n}.py"], "text": ""} for n in range(1, 171)]
    paths, rest = bb.pick_summaries(TWO, sh, last=5)
    small = bb.lead_brief(TWO, {**CTX, "summaries": paths, "summaries_more": {"count": rest, "dir": "/r/.superlite/backlog"}})
    big = bb.lead_brief(TWO, {**CTX, "summaries": [s["path"] for s in sh]})
    assert len(big) - len(small) >= 4500
