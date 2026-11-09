"""External repository tasks (#332): the **Repo:** fields, the local Owns view and their lint checks."""
from __future__ import annotations

import subprocess
import sys

from test_plan_tools import SCRIPTS, pt

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402

EDGE = "  T1 --> T2\n"
LOCAL = ("### T2 local user · Est. time 2 min\n**Owns:** src/helper.py, src/app.py\n"
         "**Components:** 1\n**LOC owned:** 20\n**Tests:** fast\n\n")


def head(edges=EDGE, wave0=True):
    return ("# Plan\n**Goal:** test.\n" + ("**Wave0:** none\n" if wave0 else "") + "\n```mermaid\nflowchart LR\n"
            "  T1[a]\n  T2[b]\n  %% taskgraph\n" + edges + "```\n\n")


def shared_repo(tmp_path):
    root = tmp_path / "shared"
    root.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def ext_block(root, test="pytest -q", ship="maxapp ship -C {tree}", owns="src/helper.py, tests/test_helper.py", extra=""):
    lines = ["### T1 shared helper · Est. time 2 min", f"**Owns:** {owns}", f"**Repo:** {root}"]
    if test is not None:
        lines.append(f"**Repo test:** `{test}`")
    if ship is not None:
        lines.append(f"**Repo ship:** `{ship}`")
    return "\n".join(lines) + "\n" + extra + "**Components:** 1\n**LOC owned:** 20\n**Tests:** fast\n\n"


def write(tmp_path, text, name="plan.md", **kw):
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    p = proj / name
    p.write_text(head(**kw) + text, encoding="utf-8")
    return p


def lint(p):
    return pt("lint", "--plan", p, cwd=p.parent)


def test_repo_fields_and_local_owns(tmp_path):
    root = shared_repo(tmp_path)
    plan = plan_tools.Plan.load(str(write(tmp_path, ext_block(root) + LOCAL)))
    t1, t2 = plan.by_id["T1"], plan.by_id["T2"]
    assert t1.repo == {"root": str(root), "test": "pytest -q", "ship": "maxapp ship -C {tree}"}
    assert t1.owns == [] and t1.owned_sources == []
    assert t1.written_owns == ["src/helper.py", "tests/test_helper.py"]
    assert t2.repo is None
    assert t2.owns == t2.written_owns == ["src/helper.py", "src/app.py"]


def test_repo_root_resolution(tmp_path, monkeypatch):
    p = write(tmp_path, LOCAL)
    monkeypatch.setenv("HOME", str(tmp_path))
    want = (tmp_path / "shared").resolve()
    assert plan_tools.repo_root(str(p), "../shared") == want
    assert plan_tools.repo_root(str(p), "~/shared") == want
    assert plan_tools.repo_root(str(p), str(tmp_path / "x" / ".." / "shared")) == want


def test_complete_external_task_lints_clean(tmp_path):
    root = shared_repo(tmp_path)
    cp = lint(write(tmp_path, ext_block(root) + LOCAL))
    assert "ISSUE: T1" not in cp.out and "ISSUE: T2" not in cp.out, cp.out


def test_missing_test_and_ship_flagged(tmp_path):
    root = shared_repo(tmp_path)
    cp = lint(write(tmp_path, ext_block(root, test=None, ship=None) + LOCAL))
    assert "ISSUE: T1: external repo task has no **Repo test:** line (the test command run in its tree)" in cp.out
    assert ("ISSUE: T1: external repo task has no **Repo ship:** line (the commit/ship step, "
            "e.g. maxapp ship -C {tree})") in cp.out


def test_ship_without_tree_or_root_flagged(tmp_path):
    root = shared_repo(tmp_path)
    cp = lint(write(tmp_path, ext_block(root, ship="maxapp ship") + LOCAL))
    assert ("ISSUE: T1: **Repo ship:** names neither {tree} nor {root}; it would run in the coordinator's "
            "checkout") in cp.out
    assert "names neither" not in lint(write(tmp_path, ext_block(root, ship="maxapp ship -C {root}") + LOCAL)).out


def test_root_missing_or_not_git_flagged(tmp_path):
    cp = lint(write(tmp_path, ext_block(tmp_path / "nope") + LOCAL))
    assert f"ISSUE: T1: **Repo:** {tmp_path / 'nope'} is not a folder" in cp.out
    plain = tmp_path / "plain"
    plain.mkdir()
    cp = lint(write(tmp_path, ext_block(plain) + LOCAL))
    assert f"ISSUE: T1: **Repo:** {plain} is not a git checkout" in cp.out


def test_root_is_this_repository_flagged(tmp_path):
    p = write(tmp_path, LOCAL)
    subprocess.run(["git", "init", "-q", str(p.parent)], check=True)
    p.write_text(head() + ext_block(p.parent) + LOCAL, encoding="utf-8")
    assert f"ISSUE: T1: **Repo:** {p.parent} is this repository; drop the Repo lines" in lint(p).out


def test_repo_lines_without_repo_flagged(tmp_path):
    text = ("### T1 x · Est. time 2 min\n**Owns:** src/a.py\n**Repo test:** `pytest`\n"
            "**Components:** 1\n**LOC owned:** 20\n**Tests:** fast\n\n" + LOCAL)
    assert ("ISSUE: T1: **Repo test:** or **Repo ship:** without a **Repo:** line (the other repository's "
            "root)") in lint(write(tmp_path, text)).out


def test_external_and_local_same_path_not_a_conflict(tmp_path):
    root = shared_repo(tmp_path)
    cp = lint(write(tmp_path, ext_block(root, owns="src/helper.py") + LOCAL, edges=""))
    assert "both own" not in cp.out


def test_two_external_tasks_same_root_conflict(tmp_path):
    root = shared_repo(tmp_path)
    second = ext_block(root, owns="src/helper.py").replace("### T1 shared helper", "### T2 shared other")
    cp = lint(write(tmp_path, ext_block(root, owns="src/helper.py") + second, edges=""))
    assert "ISSUE: T1 and T2 can run in parallel but both own src/helper.py" in cp.out


def test_bare_name_checked_against_repo_root(tmp_path):
    root = shared_repo(tmp_path)
    (root / "setup.py").write_text("", encoding="utf-8")
    assert "has no folder" not in lint(write(tmp_path, ext_block(root, owns="src/a.py, setup.py") + LOCAL)).out
    cp = lint(write(tmp_path, ext_block(root, owns="src/a.py, other.py") + LOCAL))
    assert "T1: Owns entry `other.py` has no folder" in cp.out


def test_no_owns_line_still_flagged(tmp_path):
    root = shared_repo(tmp_path)
    text = ext_block(root).replace("**Owns:** src/helper.py, tests/test_helper.py\n", "")
    assert "ISSUE: T1: no **Owns:** line" in lint(write(tmp_path, text + LOCAL)).out


def test_incomplete_external_task_is_a_fix_task(tmp_path):
    root = shared_repo(tmp_path)
    p = write(tmp_path, ext_block(root, test=None) + LOCAL)
    fix = pt("lint", "--stable", "--plan", p, cwd=p.parent).out.split("FIX:")[1]
    assert "T1:" in fix and "**Repo test:**" in fix


def test_startable_waits_for_external_producer(tmp_path):
    root = shared_repo(tmp_path)
    prod = "**Produces:** helper.make(x: int) -> int\n"
    cons = LOCAL.replace("**Components:** 1", "**Consumes:** helper.make(x: int) -> int (T1)\n**Components:** 1", 1)
    sd = tmp_path / "proj" / ".superlite"
    ctrl = write(tmp_path, ext_block(root, extra=prod).replace(f"**Repo:** {root}\n", "") + cons, name="ctrl.md", wave0=False)
    sd.mkdir(exist_ok=True)
    assert plan_tools.startable(plan_tools.Plan.load(str(ctrl)), sd) == {"T1", "T2"}
    plan = plan_tools.Plan.load(str(write(tmp_path, ext_block(root, extra=prod) + cons, wave0=False)))
    assert plan_tools.startable(plan, sd) == {"T1"}
    (sd / "progress.md").write_text("- commit T1 abcdef1234 shared helper\n", encoding="utf-8")
    assert plan_tools.startable(plan, sd) == {"T1", "T2"}


def test_external_brief_lines(tmp_path):
    root = shared_repo(tmp_path)
    p = write(tmp_path, ext_block(root) + LOCAL)
    plan = plan_tools.Plan.load(str(p))
    lines = plan_tools.external_brief(str(p), plan.by_id["T1"], "/x/sl")
    assert lines == [
        "## External repository",
        f"This task changes another repository: {root.resolve()} (**Repo:** {root}). Owns paths are relative to its tree.",
        f"1. Tree: `/x/sl plan_tools external T1 --plan {p}` makes or reuses the task's worktree of that repository "
        "and prints `tree: <path>`; edit only there.",
        f"2. Verify: `/x/sl plan_tools external T1 --plan {p} --test` runs `pytest -q` in the tree; not run_tests.",
        "3. Do not commit or ship: the coordinator runs `--commit`, the **Repo ship:** step and `--done`.",
    ]
    assert plan_tools.external_brief(None, plan.by_id["T1"])[1].startswith(f"This task changes another repository: {root} ")
    assert "`sl plan_tools external T1 --plan $PLAN --test`" in plan_tools.external_brief(None, plan.by_id["T1"])[3]
    assert plan_tools.external_brief(str(p), plan.by_id["T2"]) == []
