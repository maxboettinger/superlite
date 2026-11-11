"""#491 `**Edges:** hard` header and #496 `call=`/`serve=` Probe entries in non-Python plans."""
from __future__ import annotations

import json

from test_plan_tools import SCRIPTS, pt, run

import plan_tools as ptm  # noqa: E402


def task(tid, owns, produces=None, consumes=None, eg=(), probe=None):
    lines = [f"### {tid} task {tid.lower()} · Complexity 3 · Est. context 30k",
             f"**Owns:** {owns}", "**Components:** 1", "**LOC owned:** 100", "**Tests:** fast"]
    if produces:
        lines.append(f"**Produces:** {produces}")
    lines += [f"e.g. {x}" for x in eg]
    if consumes:
        lines.append(f"**Consumes:** {consumes}")
    if probe:
        lines.append(f"**Probe entry:** {probe}")
    return "\n".join(lines) + "\n\n"


def plan(tmp_path, tasks, edges=(), stack="Python", header="", after="", name="plan.md"):
    head = (f"# Plan\n**Goal:** x.\n**Tech stack:** {stack}\n" + header + "\n```mermaid\n%% taskgraph\nflowchart LR\n"
            + "".join(f"  {a}\n" for a in edges) + "```\n\n" + after)
    p = tmp_path / name
    p.write_text(head + "".join(tasks), encoding="utf-8")
    return p


def lint(p, *extra):
    return run(SCRIPTS / "plan_tools.py", "lint", "--plan", p, *extra).out


def two(tmp_path, header="", name="plan.md"):
    return plan(tmp_path, [task("T1", "src/mod.py, tests/test_mod.py", "mod.parse(text: str) -> Node", eg=['parse("1") -> Node(1)']),
                           task("T2", "src/b.py, tests/test_b.py", consumes="mod.parse(text: str) -> Node (T1)")],
                edges=["T1 --> T2"], header=header, name=name)


HARD = "**Edges:** hard (Swift: whole-package compile)\n"


def test_edges_hard_header_makes_every_edge_hard(tmp_path):
    p = two(tmp_path, HARD)
    assert ptm.hard_edges(ptm.Plan.load(str(p))) == {("T1", "T2")}
    assert "EDGE:" not in lint(p)
    assert "pruned: no removable edges" in run(SCRIPTS / "plan_tools.py", "prune", "--plan", p).out
    assert "T1 --> T2" in p.read_text(encoding="utf-8")


def test_without_header_the_edge_stays_removable(tmp_path):
    p = two(tmp_path)
    assert "EDGE: T2 waits for T1 only for interfaces that have examples" in lint(p)
    assert "pruned: T1->T2" in run(SCRIPTS / "plan_tools.py", "prune", "--plan", p).out


def test_edges_hard_waits_for_the_producer_commit_with_wave0(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "progress.md").write_text("", encoding="utf-8")
    hard = ptm.startable(ptm.Plan.load(str(two(tmp_path, HARD, "a.md"))), sl)
    soft = ptm.startable(ptm.Plan.load(str(two(tmp_path, "", "b.md"))), sl)
    assert hard == {"T1"}
    assert soft == {"T1", "T2"}


def test_edges_header_below_first_section_is_ignored(tmp_path):
    p = two(tmp_path, "")
    p.write_text(p.read_text(encoding="utf-8").replace("```mermaid", "## Design\n**Edges:** hard\n\n```mermaid", 1), encoding="utf-8")
    plan_ = ptm.Plan.load(str(p))
    assert plan_.header_edges_hard() is False
    assert ptm.hard_edges(plan_) == set()


def test_edges_value_other_than_hard_is_ignored(tmp_path):
    p = two(tmp_path, "**Edges:** soft\n")
    assert ptm.hard_edges(ptm.Plan.load(str(p))) == set()


def ts_plan(tmp_path, owns="src/text.ts, tests/text.test.ts", stack="TypeScript", probe="call=firstSentence", after="", name="plan.md"):
    return plan(tmp_path, [task("T1", owns, "firstSentence(text: string) -> string", eg=['firstSentence("a. b") -> "a."'], probe=probe)],
                stack=stack, after=after, name=name)


def fix_of(tmp_path, p):
    pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    return json.loads((tmp_path / ".superlite" / "stable.json").read_text(encoding="utf-8"))


def test_call_entry_in_typescript_plan_is_a_probe_error(tmp_path):
    p = ts_plan(tmp_path)
    r = run(SCRIPTS / "plan_tools.py", "lint", "--plan", p)
    assert r.returncode == 1
    msg = "PROBE: call=firstSentence imports Python, but T1 owns no Python file (TypeScript); use run= with a built command or **Probe entry:** none (<why>)"
    assert "ISSUE: " + msg in r.out
    data = fix_of(tmp_path, p)
    assert any(f["task"] == "T1" and msg in f["reasons"] for f in data["fix"])


def test_call_entry_with_folder_owns_uses_tech_stack(tmp_path):
    p = ts_plan(tmp_path, owns="src/text/", stack="TypeScript 5, Node 20")
    assert "PROBE: call=firstSentence imports Python, but the plan's stack is JavaScript, TypeScript; use run= " in lint(p)


def test_mixed_plan_python_producer_passes(tmp_path):
    p = plan(tmp_path, [task("T1", "src/pkg/a.py", "pkg.a.first(text: str) -> str", eg=['first("a") -> "a"'], probe="call=pkg.a.first"),
                        task("T2", "web/app.ts", "render(text: string) -> string", eg=['render("a") -> "a"'])], stack="Python, TypeScript")
    assert "PROBE" not in lint(p)


def test_mixed_plan_typescript_producer_fails(tmp_path):
    p = plan(tmp_path, [task("T1", "src/pkg/a.py", "pkg.a.first(text: str) -> str", eg=['first("a") -> "a"']),
                        task("T2", "web/app.ts", "render(text: string) -> string", eg=['render("a") -> "a"'], probe="call=render")],
             stack="Python, TypeScript")
    assert "PROBE: call=render imports Python, but T2 owns no Python file (TypeScript); " in lint(p)


def test_serve_entry_in_swift_plan_is_a_probe_error(tmp_path):
    p = plan(tmp_path, [task("T1", "Sources/App/Server.swift", "App.makeServer() -> Server", eg=["makeServer() -> Server()"])],
             stack="Swift", after="## Design\n**Probe entry:** serve=App.makeServer\n\n")
    assert "PROBE: serve=App.makeServer imports Python, but the plan's stack is Swift; " in lint(p)
    data = fix_of(tmp_path, p)
    assert not any("serve=App.makeServer" in r for f in data["fix"] for r in f["reasons"])
    assert any("serve=App.makeServer" in str(x) for x in data["plan_issues"])


def test_run_entry_in_typescript_plan_passes(tmp_path):
    p = ts_plan(tmp_path, probe="run=node dist/cli.js")
    assert "PROBE" not in lint(p)


def test_python_plan_call_checks_unchanged(tmp_path):
    p = plan(tmp_path, [task("T1", "src/mod.py, tests/test_mod.py", "mod.f(a: str, b: int) -> bool", probe="call=mod.f")])
    assert "PROBE: call=mod.f takes 2 required parameters; probes pass one text argument" in lint(p)


def test_owns_note_and_upper_case_extension_count(tmp_path):
    p = plan(tmp_path, [task("T1", "`src/App.TS (entry)`")])
    assert ptm.owned_languages(ptm.Plan.load(str(p)).tasks[0]) == {"TypeScript"}
