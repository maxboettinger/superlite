"""commit_task --dispatch keeps the run's batch setting (#128): the --batch flag, else the plan's experiment claim.

In-process: `dispatch.run` and `dispatch.render` are replaced by recorders, so the tests see exactly the arguments
commit_task passes; one end-to-end test runs the real dispatch with a claim of batch 1."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_spawn_free import ENV, SCRIPTS, git, make_repo, run, write

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402
import dispatch  # noqa: E402


def claim(repo, plan_path, batch):
    f = repo / ".superlite" / "experiment.json"
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps({"id": "128-batch", "plan": str(Path(plan_path).resolve()), "prime": "full", "batch": batch}),
                 encoding="utf-8")


class Calls(list):
    repo: Path


@pytest.fixture
def seen(tmp_path, monkeypatch):
    """A repo with T1's file written, cwd there, the real tools quiet; -> kwargs of each `dispatch.run` call."""
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "def parse(text):\n    return text.split()\n")
    monkeypatch.chdir(repo)
    for k in ("SUPERLITE_AUTOCOMMIT", "SUPERLITE_PROBE_RUN", "SUPERLITE_BASH"):
        monkeypatch.setenv(k, ENV[k])
    calls = Calls()

    def fake_run(*args, **kw):
        calls.append(kw)
        return ()

    monkeypatch.setattr(dispatch, "run", fake_run)
    monkeypatch.setattr(dispatch, "render", lambda *a, **k: None)
    calls.repo = repo
    return calls


def go(*extra):
    return commit_task.main(["T1", "--plan", "plan.md", "--dispatch", *extra])


def test_batch_flag_reaches_dispatch(seen):
    assert go("--batch", "1") == 0
    assert [c.get("batch") for c in seen] == [1]


def test_no_flag_no_claim_is_none(seen):
    assert go() == 0
    assert [c.get("batch") for c in seen] == [None]


def test_flag_beats_claim(seen):
    claim(seen.repo, seen.repo / "plan.md", 1)
    assert go("--batch", "2") == 0
    assert [c.get("batch") for c in seen] == [2]


def test_claim_for_other_plan_is_ignored(seen):
    claim(seen.repo, seen.repo / "other-plan.md", 1)
    assert go() == 0
    assert [c.get("batch") for c in seen] == [None]


def test_claim_for_this_plan_reaches_dispatch(seen):
    claim(seen.repo, seen.repo / "plan.md", 1)
    assert go() == 0
    assert [c.get("batch") for c in seen] == [1]


def test_dispatch_uses_experiment_batch(tmp_path):
    """Real tools: with a claim of batch 1 no `next:` line is a batch (`Tn,Tm`); without it the control run batches."""
    def next_lines(sub, with_claim):
        repo = make_repo(tmp_path / sub)
        write(repo, "src/a.py", "def parse(text):\n    return text.split()\n")
        write(repo, "src/b.py", "def lex(text):\n    return list(text)\n")
        if with_claim:
            claim(repo, repo / "plan.md", 1)
        r = run("commit_task", "T1", "T2", "--plan", "plan.md", "--dispatch", cwd=repo)
        assert r.returncode == 0, r.stdout + r.stderr
        out = r.stdout.splitlines()
        return [ln.split()[0] for ln in out[out.index("next:") + 1:] if ln.strip()]

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    solo = next_lines("a", True)
    assert solo and all("," not in t for t in solo), solo
    assert sorted(solo) == ["T3", "T4", "T5"]
    assert any("," in t for t in next_lines("b", False))  # control: the same run without the claim batches


OWNED_PLAN = """# P

## 9. Implementation plan

### T2 · two · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/f.py`

### T3 · three · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/c.py`

### T4 · four · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/f.py`
"""
OWNED_NOTE = "left uncommitted (owned by T2, changed after its checkpoint; run commit_task T2): src/f.py"


def owned_repo(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "owned.md", OWNED_PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    monkeypatch.chdir(repo)
    for k in ("SUPERLITE_AUTOCOMMIT", "SUPERLITE_PROBE_RUN", "SUPERLITE_BASH"):
        monkeypatch.setenv(k, ENV[k])
    write(repo, "src/f.py", "F = 1\n")
    assert commit_task.main(["T2", "--plan", "owned.md"]) == 0
    write(repo, "src/f.py", "F = 2\n")
    write(repo, "src/c.py", "C = 1\n")
    return repo


def test_owned_note_skipped_when_later_call_task_commits(tmp_path, monkeypatch, capsys):
    repo = owned_repo(tmp_path, monkeypatch)
    capsys.readouterr()
    assert commit_task.main(["T3", "T4", "--plan", "owned.md"]) == 0
    cap = capsys.readouterr()
    assert "owned by" not in cap.err
    sha = cap.out.splitlines()[-1].split()[1]
    assert git(repo, "show", f"{sha}:src/f.py") == "F = 2"


def test_owned_note_kept_when_nobody_commits_it(tmp_path, monkeypatch, capsys):
    owned_repo(tmp_path, monkeypatch)
    capsys.readouterr()
    assert commit_task.main(["T3", "--plan", "owned.md"]) == 0
    assert capsys.readouterr().err.count(OWNED_NOTE) == 1
