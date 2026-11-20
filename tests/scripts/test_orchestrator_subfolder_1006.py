# tests/scripts/test_orchestrator_subfolder_1006.py: orchestrator set/bind/approve from a subfolder resolve the checkout's run, never create or move run state (#1006)
import json, os, subprocess, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import orchestrator  # noqa: E402

SID = "test-1006"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True, env=env)


def cd(monkeypatch, d):
    monkeypatch.chdir(d)
    monkeypatch.setenv("PWD", str(d))


def tree(root):
    return sorted(str(p) for p in Path(root).rglob("*") if ".git" not in p.relative_to(root).parts)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    top = (tmp_path / "top").resolve()
    top.mkdir()
    git(top, "init", "-q", "-b", "main")
    sub = top / "skills" / "x" / "scripts"
    sub.mkdir(parents=True)
    (sub / "f.py").write_text("x = 1\n")
    plans = top / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "p.md").write_text("# p\n")
    (plans / "p.review.md").write_text("# review\n")
    git(top, "add", "-A")
    git(top, "commit", "-qm", "c")
    cd(monkeypatch, top)
    assert orchestrator.main(["set", "ai", "--plan", str(top / ".superlite")]) == 0
    cd(monkeypatch, sub)
    return top, sub


def binding():
    return Path(os.environ["SUPERLITE_HOME"]) / "sessions" / SID


def snap(top):
    return [(p.read_bytes() if p.exists() else None) for p in (top / ".superlite" / "orchestrator.json", top / ".superlite" / "session", binding())]


def test_unanchored_cases(repo, tmp_path, monkeypatch):
    top, sub = repo
    before = tree(top)
    assert orchestrator.unanchored("docs/plans/nope.md") == top
    assert orchestrator.unanchored("docs/plans/p.md") == top
    assert orchestrator.unanchored(".superlite") is None
    assert orchestrator.unanchored(None) is None
    assert orchestrator.unanchored("") is None
    assert orchestrator.unanchored(str(top / "docs/plans/nope.md")) is None
    assert orchestrator.unanchored(str(top / "docs/plans/p.md")) is None
    cd(monkeypatch, top)
    assert orchestrator.unanchored("docs/plans/nope.md") is None
    outside = tmp_path / "outside"
    outside.mkdir()
    cd(monkeypatch, outside)
    assert orchestrator.unanchored("docs/nope.md") is None
    assert tree(top) == before


def test_set_from_subfolder_binds_top(repo):
    top, sub = repo
    assert orchestrator.main(["set", "human", "--plan", "docs/plans/p.md"]) == 0
    assert not (sub / ".superlite").exists()
    assert json.loads((top / ".superlite" / "orchestrator.json").read_text())["mode"] == "human"
    assert (top / ".superlite" / "session").read_text().strip() == SID
    assert binding().read_text().splitlines()[0] == str(top / ".superlite")


def test_bind_from_subfolder_binds_top(repo, capsys):
    top, sub = repo
    assert orchestrator.main(["bind", "--plan", "docs/plans/p.md"]) == 0
    assert capsys.readouterr().out.strip() == f"orchestrator: session bound to {top / '.superlite'}"
    assert not (sub / ".superlite").exists()


@pytest.mark.parametrize("with_plan", [True, False])
def test_approve_review_from_subfolder(repo, monkeypatch, with_plan):
    top, sub = repo
    cd(monkeypatch, top)
    assert orchestrator.main(["set", "human", "--plan", str(top / ".superlite")]) == 0
    mt = int((top / "docs/plans/p.review.md").stat().st_mtime * 1000)
    with open(top / ".superlite" / "human-replies.jsonl", "a") as f:
        f.write(json.dumps({"t": mt + 5000, "approves": True}) + "\n")
    cd(monkeypatch, sub)
    cmd = ["approve", "--review", "docs/plans/p.review.md"] + (["--plan", "docs/plans/p.md"] if with_plan else [])
    assert orchestrator.main(cmd) == 0
    cur = json.loads((top / ".superlite" / "orchestrator.json").read_text())
    assert cur["approved"] is True
    assert cur["review_path"] == str(top / "docs/plans/p.review.md")
    assert not (sub / ".superlite").exists()


@pytest.mark.parametrize("cmd,word", [(["set", "ai"], "set"), (["bind"], "bound"), (["approve", "--review", "docs/plans/p.review.md"], "approved")])
def test_missing_plan_from_subfolder_writes_nothing(repo, capsys, cmd, word):
    top, sub = repo
    before = snap(top)
    assert orchestrator.main([*cmd, "--plan", "docs/plans/nope.md"]) == 2
    assert f"orchestrator: plan not found: docs/plans/nope.md (neither at the cwd nor at {top}); not {word}" in capsys.readouterr().err
    assert not (sub / ".superlite").exists()
    assert snap(top) == before


def test_missing_review_from_subfolder_writes_nothing(repo, capsys):
    top, sub = repo
    before = snap(top)
    assert orchestrator.main(["approve", "--review", "docs/plans/nope.review.md"]) == 2
    assert f"orchestrator: review plan not found: docs/plans/nope.review.md (neither at the cwd nor at {top}); not approved" in capsys.readouterr().err
    assert not (sub / ".superlite").exists()
    assert snap(top) == before


def test_missing_plan_from_top_unchanged(repo, monkeypatch):
    top, sub = repo
    cd(monkeypatch, top)
    assert orchestrator.main(["set", "human", "--plan", "docs/plans/nope.md"]) == 0
    assert json.loads((top / ".superlite" / "orchestrator.json").read_text())["mode"] == "human"


def test_status_from_subfolder_reads_top(repo, capsys):
    top, sub = repo
    assert orchestrator.main(["status", "--plan", "docs/plans/p.md"]) == 0
    assert capsys.readouterr().out.startswith("orchestrator: AI")
    assert not (sub / ".superlite").exists()


def test_takeover_from_subfolder(repo, capsys):
    top, sub = repo
    assert orchestrator.main(["takeover", "--plan", "docs/plans/p.md"]) == 0
    assert str(top / ".superlite") in capsys.readouterr().out
    assert not (sub / ".superlite").exists()
