"""#699: with lead.build_model set the planning lead stops after a linted plan and wait starts a build lead on it."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from backlog_fixtures import batch as b
from test_backlog_run import bk, get, put, run  # noqa: F401  (bk is a fixture)
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as real_bb  # noqa: E402
import backlog_run as br  # noqa: E402

BUILD = {"configs": {"default": {"lead": {"build_model": "sonnet", "build_effort": "high"}}}}


@pytest.fixture
def real(bk, monkeypatch, tmp_path):
    """The real brief writer and a private home; spawn_lead calls are recorded as (model, rc)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setitem(sys.modules, "backlog_brief", real_bb)
    seen = []
    orig = sys.modules["fleet_lead"].spawn_lead

    def spawn(main_sd, wt, model="opus", env=None, rc=None):
        seen.append((model, rc))
        return orig(main_sd, wt, model, env, rc)
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", spawn)
    bk.home, bk.seen = home, seen
    return bk


def machine(bk, cfg=BUILD):
    (bk.home / "run-configs.json").write_text(json.dumps(cfg), encoding="utf-8")


def wt_of(bk):
    return bk.root / ".claude" / "worktrees" / "superlite-b1-t"


def brief(wt, name="lead.md"):
    return (wt / ".superlite" / "briefs" / name).read_text(encoding="utf-8")


def planning(bk, phase="plan", **kw):
    wt = wt_of(bk)
    (wt / ".superlite").mkdir(parents=True, exist_ok=True)
    put(bk, b("B1", ["a.py"], "running", lead="W1", agent="sl-m-W1", worktree=str(wt), since=1000, phase=phase,
              leads=[{"id": "W1", "phase": phase, "model": "opus"}], **kw))
    bk.states["sl-m-W1"] = "done"
    return wt


def test_planned_path():
    assert br.planned_path("Status: DONE planned: docs/plans/p.md") == "docs/plans/p.md"
    assert br.planned_path("Status: **DONE** planned: `docs/plans/p.md`") == "docs/plans/p.md"
    assert br.planned_path("Status: DONE") is None
    assert br.planned_path("**Status: DONE planned: p.md**") == "p.md"
    assert br.planned_path("Status: DONE planned: docs/plans/p.md.") == "docs/plans/p.md"


def test_plan_errors_real_lint(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    own = "**Owns:** pkg/a.py, tests/test_a.py"
    lines = ["# Lean plan", "**Goal:** fix it.", "**Tech stack:** Python", f"**Spec:** {tmp_path / 'plan.md'}",
             "**Wave0:** none", "**Worktree:** none", "**Coverage:** off", "",
             "```mermaid", "%% taskgraph", "flowchart LR", "  T1", "```", "",
             "### T1 fix a · Complexity 2 (O-1) · Est. context 20k",
             own, "**Components:** 1", "**LOC owned:** 30", "**Tests:** fast",
             "**Kind:** mechanical", "**Model:** haiku", "", "test_a: a(1) == 2.", ""]
    (tmp_path / "plan.md").write_text("\n".join(lines), encoding="utf-8")
    assert br.plan_errors(tmp_path, "plan.md") == []
    (tmp_path / "bad.md").write_text("\n".join(x for x in lines if x != own), encoding="utf-8")
    errs = br.plan_errors(tmp_path, "bad.md")
    assert errs and "T1" in " ".join(errs)
    assert br.plan_errors(tmp_path, "../x.md") == ["plan ../x.md not found in the worktree"]


def test_start_plan_phase(real, capsys):
    machine(real)
    put(real, b("B1", ["a.py"]))
    assert run(capsys, "start", "B1")[0] == 0
    assert real.seen[0][0] == "opus"
    assert "Status: DONE planned:" in brief(wt_of(real))
    x = get(real, "B1")
    assert x["phase"] == "plan" and x["leads"] == [{"id": "W1", "phase": "plan", "model": "opus"}]


def test_start_single_phase(real, capsys):
    put(real, b("B1", ["a.py"]))
    assert run(capsys, "start", "B1")[0] == 0
    assert "DONE planned" not in brief(wt_of(real))
    x = get(real, "B1")
    assert x["phase"] == "single" and x["leads"][0]["phase"] == "single"


def test_wait_planned_starts_build_lead(real, capsys, monkeypatch):
    wt = planning(real)
    real.n[0] = 1  # the planning lead was W1; the fake's next id is W2
    import run_config
    machine(real)
    rcfg = run_config.resolve(None, real.root)
    (wt / ".superlite" / "run-config.json").write_text(json.dumps(rcfg), encoding="utf-8")
    monkeypatch.setattr(br, "plan_errors", lambda w, p: [])
    real.stops["W1"] = {"t": 2000, "last": "Status: DONE planned: docs/plans/p.md"}
    rc, out = run(capsys, "wait", "--timeout", "0")
    assert real.seen[0][0] == "sonnet" and real.seen[0][1]["lead"]["effort"] == "high"
    text = brief(wt, "lead-build.md")
    assert "You are the build lead" in text and "docs/plans/p.md" in text
    assert ("stop", ["W1"]) in real.calls
    x = get(real, "B1")
    assert x["lead"] == "W2" and x["phase"] == "build" and x["plan"] == "docs/plans/p.md" and len(x["leads"]) == 2
    assert "B1 building lead=W2 model=sonnet plan=docs/plans/p.md" in out


def test_wait_planned_red_returns_once(real, capsys, monkeypatch):
    wt = planning(real)
    monkeypatch.setattr(br, "plan_errors", lambda w, p: ["T1 owns no files"])
    real.stops["W1"] = {"t": 2000, "last": "Status: DONE planned: p.md"}
    run(capsys, "wait", "--timeout", "0")
    sent = [c for c in real.calls if c[0] == "text"]
    assert sent and "does not run: T1 owns no files" in " ".join(sent[0][1])
    x = get(real, "B1")
    assert x["state"] == "running" and x["plan_returned"] is True
    real.stops["W1"] = {"t": 6000, "last": "Status: DONE planned: p.md"}
    rc, out = run(capsys, "wait", "--timeout", "0")
    x = get(real, "B1")
    assert x["state"] == "parked" and x["reason"].startswith("plan does not run: T1 owns no files")


def test_wait_planned_single_parks(real, capsys):
    planning(real, phase="single")
    real.stops["W1"] = {"t": 2000, "last": "Status: DONE planned: p.md"}
    run(capsys, "wait", "--timeout", "0")
    assert get(real, "B1")["state"] == "parked"
    assert not any(c[0] == "spawn" for c in real.calls)


def test_resume_build_phase(real, capsys, monkeypatch):
    monkeypatch.setattr(br, "plan_errors", lambda w, p: [])
    machine(real)
    wt = wt_of(real)
    (wt / ".superlite").mkdir(parents=True, exist_ok=True)
    put(real, b("B1", ["a.py"], "parked", reason="lead pane gone", lead="W7", agent="sl-m-W7", worktree=str(wt),
                phase="build", plan="docs/plans/p.md", leads=[{"id": "W1", "phase": "build", "model": "sonnet"}]))
    assert run(capsys, "start", "B1")[0] == 0
    assert real.seen[0][0] == "sonnet"
    text = brief(wt, "lead-build.md")
    assert "Resume:" in text and "docs/plans/p.md" in text
    assert len(get(real, "B1")["leads"]) == 2


def test_resume_build_phase_missing_plan(real, capsys):
    machine(real)
    wt = wt_of(real)
    (wt / ".superlite").mkdir(parents=True, exist_ok=True)
    put(real, b("B1", ["a.py"], "parked", reason="lead pane gone", lead="W7", agent="sl-m-W7", worktree=str(wt),
                phase="build", plan="docs/plans/p.md", plan_returned=True,
                leads=[{"id": "W1", "phase": "build", "model": "sonnet"}]))
    assert run(capsys, "start", "B1")[0] == 0
    assert real.seen[0][0] == "opus"
    assert "Status: DONE planned:" in brief(wt)
    x = get(real, "B1")
    assert x["phase"] == "plan" and x["plan_returned"] is False and not x.get("plan")


def test_start_summaries_filtered(real, capsys):
    d = real.sd / "backlog"
    d.mkdir(parents=True)
    shipped = []
    for i in range(2, 10):
        (d / f"B{i}.md").write_text(f"# B{i} summary\nbody\n", encoding="utf-8")
        shipped.append(b(f"B{i}", ["a.py"] if i == 2 else [f"z{i}.py"], "shipped"))
    put(real, b("B1", ["a.py"]), *shipped)
    assert run(capsys, "start", "B1")[0] == 0
    text = brief(wt_of(real))
    assert str(d / "B2.md") in text
    for i in range(5, 10):
        assert str(d / f"B{i}.md") in text
    assert str(d / "B3.md") not in text and "Other shipped summaries: 2 more in" in text


def test_wait_planned_lagging_transcript_starts_build_lead(real, capsys, monkeypatch, tmp_path):
    wt = planning(real)
    real.n[0] = 1
    import run_config
    machine(real)
    rcfg = run_config.resolve(None, real.root)
    (wt / ".superlite" / "run-config.json").write_text(json.dumps(rcfg), encoding="utf-8")
    monkeypatch.setattr(br, "plan_errors", lambda w, p: [])
    fio = sys.modules["fleet_io"]
    monkeypatch.setattr(fio, "READ_MS", 10000, raising=False)
    monkeypatch.setattr(fio, "report_text", lambda tr: "", raising=False)
    monkeypatch.setattr(br, "_now_ms", lambda: 60000)
    blank = tmp_path / "blank.jsonl"
    blank.write_text("", encoding="utf-8")
    real.stops["W1"] = {"t": 2000, "last": "Status: DONE planned: docs/plans/p.md", "transcript": str(blank)}
    rc, out = run(capsys, "wait", "--timeout", "0")
    x = get(real, "B1")
    assert "transcript unread" not in out and x["state"] != "parked"
    assert x["phase"] == "build" and x["lead"] == "W2"


def test_spawn_failure_keeps_plan_for_build_restart(real, capsys, monkeypatch):
    wt = planning(real)
    real.n[0] = 1
    machine(real)
    monkeypatch.setattr(br, "plan_errors", lambda w, p: [])
    real.stops["W1"] = {"t": 2000, "last": "Status: DONE planned: docs/plans/p.md"}
    good = sys.modules["fleet_lead"].spawn_lead

    def boom(*a, **k):
        raise SystemExit(1)
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", boom)
    run(capsys, "wait", "--timeout", "0")
    x = get(real, "B1")
    assert x["state"] == "parked" and x["phase"] == "build" and x["plan"] == "docs/plans/p.md"
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", good)
    real.seen.clear()
    real.states.pop("sl-m-W1", None)  # the planning lead's pane is gone
    rc, out = run(capsys, "start", "B1")
    assert rc == 0, out
    assert real.seen[0][0] == "sonnet"
    assert "You are the build lead" in brief(wt, "lead-build.md")
