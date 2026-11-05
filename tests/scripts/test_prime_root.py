"""The prime names the run's root folder on one `Root:` line; the agent files tell agents to cd there."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from test_plan_tools import SCRIPTS, run
from test_slim_prime import make

BUILD_PRIME = SCRIPTS / "build_prime.py"
AGENTS = SCRIPTS.parents[2] / "agents"
OWNED = ["implementer", "implementer-haiku", "fixer-sonnet", "fixer-sonnet-high", "fixer-opus", "package-reviewer"]


def build(tmp_path, plan, *extra):
    out = tmp_path / "p.md"
    cp = run(BUILD_PRIME, "--plan", plan, "--out", out, *extra, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return out.read_text(encoding="utf-8")


def test_root_line_in_every_prime_kind(tmp_path):
    plan = make(tmp_path)
    for extra in ((), ("--tier", "haiku"), ("--prime", "full")):
        text = build(tmp_path, plan, *extra)
        lines = text.split("\n")
        hits = [i for i, ln in enumerate(lines) if re.match(r"^Root: /", ln)]
        first_h2 = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
        assert len(hits) == 1, extra
        assert hits[0] < first_h2, extra


def test_root_is_the_plans_toplevel(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs" / "plans").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    plan = make(repo / "docs" / "plans", stable=None)
    text = build(tmp_path, plan)
    assert f"\nRoot: {repo.resolve().as_posix()}\n" in text
    outside = tmp_path / "loose"
    outside.mkdir()
    plan2 = make(outside, stable=None)
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import plan_tools
    want = plan_tools.stable_root(str(plan2)).resolve().as_posix()
    assert f"\nRoot: {want}\n" in build(tmp_path, plan2)


def test_agent_files_name_root():
    for name in OWNED:
        t = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
        assert "Root:" in t and "`cd`" in t, name
