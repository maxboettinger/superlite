"""plan_tools lint warns, naming the line, when a plan names an existing path outside the project (#1086)."""
import os, subprocess, uuid
import pytest
from test_plan_tools import PLAN_TOOLS, make_plan, pt

TASK = [{"id": "T1", "components": 1, "loc": 20, "tests": "fast", "model": "sonnet"}]


def lint(tmp_path, header):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, env=env, check=True)
    plan = make_plan(tmp_path, TASK, header=header)
    return pt("lint", "--plan", plan, cwd=tmp_path), plan


@pytest.fixture
def outside(tmp_path):
    d = tmp_path.parent / f"out-{uuid.uuid4().hex[:8]}"
    d.mkdir()
    (d / "spec.md").write_text("s\n")
    return d


def test_lint_warns_on_an_existing_outside_path_with_its_line(tmp_path, outside):
    cp, plan = lint(tmp_path, f"Ruling: mirror {outside}/spec.md (lead's ruling).")
    n = next(i for i, ln in enumerate(plan.read_text().splitlines(), 1) if "Ruling: mirror" in ln)
    hits = [ln for ln in cp.out.splitlines() if "OUTSIDE:" in ln]
    assert len(hits) == 1
    assert hits[0].startswith(f"WARNING: OUTSIDE: line {n} names a path outside the project: {outside}/spec.md")
    base = pt("lint", "--plan", make_plan(tmp_path, TASK, header="", name="base.md"), cwd=tmp_path)
    assert cp.returncode == base.returncode


def test_fenced_missing_and_inside_paths_do_not_warn(tmp_path, outside):
    header = f"```\n{outside}/spec.md\n```\nMissing {outside}/gone.md here.\nInside {tmp_path}/docs/x.md here."
    cp, _ = lint(tmp_path, header)
    assert "OUTSIDE:" not in cp.out


def test_a_path_named_twice_warns_once(tmp_path, outside):
    cp, _ = lint(tmp_path, f"First {outside}/spec.md here.\nSecond {outside}/spec.md here.")
    hits = [ln for ln in cp.out.splitlines() if "OUTSIDE:" in ln]
    assert len(hits) == 1 and "First" not in hits[0] and f"{outside}/spec.md" in hits[0]
