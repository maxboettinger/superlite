"""#177/#140 lint: `call=` probe entries, `e.g.` anywhere in the line, hard edges skip EXAMPLE, lint --stable refusals log."""
from __future__ import annotations

import json
import subprocess

from test_plan_tools import SCRIPTS, pt, run


def task(tid, produces=None, consumes=None, eg=(), probe=None):
    lines = [f"### {tid} task {tid.lower()} · Complexity 3 · Est. context 30k",
             f"**Owns:** src/pkg/{tid.lower()}.py, tests/test_{tid.lower()}.py",
             "**Components:** 1", "**LOC owned:** 100", "**Tests:** fast"]
    if produces:
        lines.append(f"**Produces:** {produces}")
    lines += [f"e.g. {x}" for x in eg]
    if consumes:
        lines.append(f"**Consumes:** {consumes}")
    if probe:
        lines.append(f"**Probe entry:** {probe}")
    return "\n".join(lines) + "\n\n"


def plan(tmp_path, tasks, edges=(), name="plan.md", header=""):
    head = ("# Plan\n**Goal:** x.\n**Tech stack:** Python\n" + header + "\n```mermaid\n%% taskgraph\nflowchart LR\n"
            + "".join(f"  {a}\n" for a in edges) + "```\n\n")
    p = tmp_path / name
    p.write_text(head + "".join(tasks), encoding="utf-8")
    return p


def lint(p, *extra):
    return run(SCRIPTS / "plan_tools.py", "lint", "--plan", p, *extra).out


def fix_of(tmp_path, p):
    pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    data = json.loads((tmp_path / ".superlite" / "stable.json").read_text(encoding="utf-8"))
    return {f["task"]: f["reasons"] for f in data["fix"]}


TWO = "mod.f(a: str, b: int) -> bool"
ONE = "mod.f(text: str) -> bool"


def test_lint_rejects_multi_arg_call_entry(tmp_path):
    p = plan(tmp_path, [task("T1", TWO, probe="call=mod.f")])
    assert "PROBE: call=mod.f takes 2 required parameters; probes pass one text argument" in lint(p)
    fix = fix_of(tmp_path, p)
    assert "T1" in fix and any(r.startswith("PROBE: call=mod.f takes 2") for r in fix["T1"])


def test_lint_accepts_one_arg_call_entry(tmp_path):
    p = plan(tmp_path, [task("T1", ONE, probe="call=mod.f")], name="one.md")
    assert "PROBE" not in lint(p)
    assert "T1" not in fix_of(tmp_path, p)


def test_lint_counts_only_required_parameters(tmp_path):
    p = plan(tmp_path, [task("T1", "mod.f(text: str, n: int = 3, *rest, **kw) -> bool", probe="call=mod.f")], name="opt.md")
    assert "PROBE" not in lint(p)


def test_lint_unknown_call_target_is_not_a_produces(tmp_path):
    p = plan(tmp_path, [task("T1", ONE, probe="call=mod.h")], name="unk.md")
    assert "PROBE: call=mod.h is not a Produces of this plan" in lint(p)


def test_lint_matches_a_qualified_call_target(tmp_path):
    p = plan(tmp_path, [task("T1", ONE, probe="`call=pkg.mod.f` · run=python -m pkg")], name="q.md")
    assert "PROBE" not in lint(p)


def test_lint_probe_entry_outside_a_task_does_not_block(tmp_path):
    p = plan(tmp_path, [task("T1", TWO)], name="hdr.md", header="**Probe entry:** call=mod.f\n")
    assert "PROBE: call=mod.f takes 2 required parameters" in lint(p)
    assert "T1" not in fix_of(tmp_path, p)  # a plan-scoped issue never blocks a stable task


def test_example_anywhere_in_line(tmp_path):
    eg = 'after record_green(s, "u", "h", {}): changed_files(s, "u", {}) -> []'
    prod = "changed_files(s: State, u: str, o: dict) -> list[str]"
    cons = "changed_files(s: State, u: str, o: dict) -> list[str]"
    p = plan(tmp_path, [task("T1", prod, eg=[eg]), task("T2", None, cons)], ["T1 --> T2"], name="any.md")
    assert "EXAMPLE" not in lint(p)
    no_eg = plan(tmp_path, [task("T1", prod), task("T2", None, cons)], ["T1 --> T2"], name="none.md")
    assert "EXAMPLE: T2 consumes changed_files" in lint(no_eg)


def test_hard_edge_skips_example(tmp_path):
    prod = "lang.parse(src: str) -> Ast"
    p = plan(tmp_path, [task("T1", prod), task("T2", None, prod)], ["T1 -->|hard| T2"], name="hard.md")
    assert "EXAMPLE" not in lint(p)
    soft = plan(tmp_path, [task("T1", prod), task("T2", None, prod)], ["T1 --> T2"], name="soft.md")
    assert "EXAMPLE: T2 consumes lang.parse" in lint(soft)


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def rows(root):
    f = root / ".superlite" / "incidents.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def test_lint_stable_refusal_logs_incident(tmp_path):
    repo = tmp_path.resolve() / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "user.email", "t@t")
    (repo / ".gitignore").write_text(".superlite/\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    d = repo / "docs" / "plans"
    d.mkdir(parents=True)
    p = plan(d, [task("T1", ONE)], name="p.md")
    cp = pt("lint", "--plan", p, "--stable", cwd=repo)  # shared checkout, no Worktree: none
    assert cp.returncode == 2 and "shared checkout" in cp.err
    got = [r for r in rows(repo) if r.get("kind") == "rule-block"]
    assert len(got) == 1 and got[0]["tool"] == "lint --stable" and "shared checkout" in got[0]["target"]


def test_lint_stable_human_gate_refusal_logs_incident(tmp_path):
    p = plan(tmp_path, [task("T1", ONE)], name="p.md")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "orchestrator.json").write_text(json.dumps({"mode": "human", "approved": False}), encoding="utf-8")
    cp = pt("lint", "--plan", p, "--stable", cwd=tmp_path)
    assert cp.returncode == 4 and "BLOCKED" in cp.err
    got = [r for r in rows(tmp_path) if r.get("kind") == "rule-block"]
    assert len(got) == 1 and got[0]["tool"] == "lint --stable" and got[0]["target"].startswith("BLOCKED: human orchestrator")
