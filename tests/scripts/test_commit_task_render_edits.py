"""commit_task refuses while render-check edits are applied (B118 follow-up)."""
import json
import sys

import pytest

from test_run_scripts import SCRIPTS, git, make_repo, write

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = """# P

## 9. Implementation plan

### T1 · one · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/a.py`
"""


@pytest.fixture
def run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "docs/plans/p.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: None)
    (repo / ".superlite").mkdir(exist_ok=True)
    write(repo, "src/a.py", "X = 1\n")
    return repo, str(repo / "docs/plans/p.md")


def record(repo, files):
    (repo / ".superlite" / "render-edits.json").write_text(json.dumps({"files": files}), encoding="utf-8")


def test_commit_task_refuses_applied_render_edit(run, capsys):
    repo, plan = run
    record(repo, {"app/View.swift": {"t": 1}})
    before = git(repo, "for-each-ref")
    assert commit_task.main(["T1", "--plan", plan]) == 2
    got = capsys.readouterr()
    assert "BLOCKED: render edits still applied: app/View.swift; run sl render_edit restore first" in got.out + got.err
    ledger = repo / ".superlite" / "progress.md"
    assert not ledger.exists() or "commit" not in ledger.read_text(encoding="utf-8")
    assert git(repo, "for-each-ref") == before


def test_commit_task_runs_without_render_edits(run):
    repo, plan = run
    record(repo, {})
    assert commit_task.main(["T1", "--plan", plan]) == 0


def test_claim_still_runs_with_render_edits(run):
    repo, plan = run
    record(repo, {"app/View.swift": {"t": 1}})
    assert commit_task.main(["T1", "--plan", plan, "--claim", "src/z.py", "--ruling", "R"]) == 0
    assert "R" in (repo / ".superlite" / "progress.md").read_text(encoding="utf-8")
