"""#711: lint names a run= Probe entry with outside effects; probe-plan.md says run= entries run for real with fuzzed arguments."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_plan_edges_probe_stack_491_496 import fix_of, lint, plan, task
from test_plan_tools import SCRIPTS, run

import plan_tools as ptm  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TAIL = ("probes run every run= entry for real with fuzzed arguments appended, so a command that fetches, pushes, "
        "opens pull requests, deploys or restarts a service gets **Probe entry:** none (<why>)")


@pytest.mark.parametrize("cmd, want", [
    ("scripts/nightly.sh --dry-run", ("issue", "has a dry-run flag")),
    ("python -m jobs.nightly --dry_run=1", ("issue", "has a dry-run flag")),
    ("tool -n --DryRun", ("issue", "has a dry-run flag")),
    ("gh pr create --fill", ("issue", "runs gh")),
    ("/usr/bin/git fetch origin", ("issue", "runs git")),
    ("env FOO=1 sudo kubectl apply -f x.yaml", ("issue", "runs kubectl")),
    ("bash scripts/deploy.sh", ("warning", "deploy")),
    ("python tools/publish_docs.py", ("warning", "publish")),
    ("python -m app push", ("warning", "push")),
    ("python -m minisheet", None),
    (".build/debug/Tool", None),
    ("target/release/tool --json", None),
    (".venv/bin/pkgtool sync", None),
    ("node dist/cli.js", None),
    ("python -c 'print(1)'", None),
    ("tool 'unbalanced", None),
    ("", None),
])
def test_run_effect(cmd, want):
    assert ptm.run_effect(cmd) == want


def test_dry_run_entry_fails_lint_for_its_task(tmp_path):
    p = plan(tmp_path, [task("T1", "src/jobs/nightly.py, tests/test_nightly.py", probe="run=python -m jobs.nightly --dry-run")])
    r = run(SCRIPTS / "plan_tools.py", "lint", "--plan", p)
    assert r.returncode == 1
    msg = "PROBE: run=python -m jobs.nightly --dry-run has a dry-run flag: " + TAIL
    assert "ISSUE: " + msg in r.out
    assert any(f["task"] == "T1" and msg in f["reasons"] for f in fix_of(tmp_path, p)["fix"])


def test_outside_tool_entry_in_a_section_is_a_plan_issue(tmp_path):
    p = plan(tmp_path, [task("T1", "src/a.py, tests/test_a.py")], after="## Design\n**Probe entry:** run=gh pr list\n\n")
    assert "PROBE: run=gh pr list runs gh: " + TAIL in lint(p)
    assert any("run=gh pr list" in str(x) for x in fix_of(tmp_path, p)["plan_issues"])


def test_effect_word_is_a_warning_only(tmp_path):
    p = plan(tmp_path, [task("T1", "scripts/deploy.py, tests/test_deploy.py", probe="run=python scripts/deploy.py")])
    out = lint(p)
    assert 'WARNING: PROBE: run=python scripts/deploy.py names "deploy": ' + TAIL in out
    assert "ISSUE: PROBE" not in out


def test_long_command_is_cut(tmp_path):
    long = "scripts/nightly.sh " + "--opt " * 20 + "--dry-run"
    p = plan(tmp_path, [task("T1", "src/a.py, tests/test_a.py", probe="run=" + long)])
    assert "PROBE: run=" + long[:57] + "... has a dry-run flag: " + TAIL in lint(p)


def test_plain_and_fenced_entries_stay_quiet(tmp_path):
    p = plan(tmp_path, [task("T1", "src/minisheet/cli.py, tests/test_cli.py", probe="run=python -m minisheet · raises=ValueError")],
             after="## Design\n```\n**Probe entry:** run=gh pr list\n```\n\n")
    assert "PROBE" not in lint(p)


def test_probe_plan_says_run_entries_run_for_real():
    text = (ROOT / "skills" / "writing-plans" / "probe-plan.md").read_text(encoding="utf-8")
    assert "Every `run=` entry is executed for real with fuzzed arguments appended" in text
    assert "fetches, pushes, opens pull requests, deploys or restarts a service gets `**Probe entry:** none (<why>)`" in text
    assert "scratch `HOME`" in text and "`GH_TOKEN`" in text and "`SSH_AUTH_SOCK`" in text
