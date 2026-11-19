# tests/scripts/test_plan_tools_subfolder_998.py: plan_tools from a subfolder resolves the checkout's run, never creates run state (#998)
import os, subprocess, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402
import orchestrator  # noqa: E402

SID = "test-998"


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
    top = tmp_path / "top"
    top.mkdir()
    git(top, "init", "-q", "-b", "main")
    sub = top / "skills" / "x" / "scripts"
    sub.mkdir(parents=True)
    (sub / "f.py").write_text("x = 1\n")
    plan_dir = top / "docs" / "plans"
    plan_dir.mkdir(parents=True)
    tasks = [{"id": t, "title": t, "owns": f"src/{t.lower()}.py", "components": 1, "loc": 20, "tests": "fast", "model": "sonnet", "time": 5} for t in ("T1", "T2")]
    plan = make_plan(plan_dir, tasks, edges=[("T1", "T2")], header="**Worktree:** none\n**Wave0:** none\n**Coverage:** off", name="p.md")
    git(top, "add", "-A")
    git(top, "commit", "-qm", "c")
    cd(monkeypatch, top)
    assert orchestrator.main(["set", "ai", "--plan", str(top / ".superlite")]) == 0
    cd(monkeypatch, sub)
    return top, sub, plan


def test_anchor_plan_cases(repo, tmp_path, monkeypatch):
    top, sub, plan = repo
    before = tree(top)
    a = plan_tools.anchor_plan
    assert a("docs/plans/p.md", cwd=str(sub)) == str(top / "docs/plans/p.md")
    assert a("docs/plans/nope.md", cwd=str(sub)) == "docs/plans/nope.md"
    assert a(".superlite", cwd=str(sub)) == str(top / ".superlite")
    assert a(str(plan), cwd=str(sub)) == str(plan)
    assert a("", cwd=str(sub)) == ""
    (sub / "docs" / "plans").mkdir(parents=True)
    (sub / "docs" / "plans" / "p.md").write_text("x")
    assert a("docs/plans/p.md", cwd=str(sub)) == "docs/plans/p.md"
    outside = tmp_path / "outside"
    outside.mkdir()
    assert a("docs/nope.md", cwd=str(outside)) == "docs/nope.md"
    (sub / "docs" / "plans" / "p.md").unlink()
    (sub / "docs" / "plans").rmdir()
    (sub / "docs").rmdir()
    assert tree(top) == before


def test_lint_stable_from_subfolder_binds_top(repo, capsys):
    top, sub, plan = repo
    assert plan_tools.main(["lint", "--plan", "docs/plans/p.md", "--stable"]) in (0, 1)
    assert not (sub / ".superlite").exists()
    assert (top / ".superlite" / "orchestrator.json").exists()
    assert (top / ".superlite" / "session").read_text().strip() == SID
    assert "p.md" in (top / ".superlite" / "stable.json").read_text()


@pytest.mark.parametrize("where", ["sub", "top"])
def test_lint_stable_missing_plan_writes_nothing(repo, capsys, monkeypatch, where):
    top, sub, plan = repo
    if where == "top":
        cd(monkeypatch, top)
    files = [top / ".superlite" / "orchestrator.json", top / ".superlite" / "session"]
    before = [f.read_bytes() for f in files]
    binding = Path(os.environ["SUPERLITE_HOME"]) / "sessions" / SID
    bound = binding.read_text()
    assert plan_tools.main(["lint", "--plan", "docs/plans/nope.md", "--stable"]) == 2
    assert "error: plan not found: docs/plans/nope.md" in capsys.readouterr().err
    assert not (sub / ".superlite").exists()
    assert [f.read_bytes() for f in files] == before
    assert binding.read_text() == bound
    assert bound.splitlines()[0] == str(top / ".superlite")


def test_prune_from_subfolder(repo, capsys):
    top, sub, plan = repo
    assert plan_tools.main(["prune", "--plan", "docs/plans/p.md"]) == 0
    assert capsys.readouterr().out.startswith("pruned: ")
    assert "%% schedule" in plan.read_text()
    assert not (sub / ".superlite").exists()


def test_bare_superlite_from_subfolder(repo, capsys):
    top, sub, plan = repo
    (top / ".superlite" / "stable.json").write_text('{"plan": "%s"}' % plan)
    assert plan_tools.main(["lint", "--plan", ".superlite"]) != 2
    assert "plan not found" not in capsys.readouterr().err
    assert not (sub / ".superlite").exists()


def test_review_command_from_subfolder(repo, monkeypatch, capsys):
    top, sub, plan = repo
    seen = []
    import types
    fake = types.SimpleNamespace(main=lambda argv: seen.append(list(argv)) or 0)
    monkeypatch.setitem(sys.modules, "pt_review", fake)
    assert plan_tools.main(["contract", "--plan", "docs/plans/p.md"]) == 0
    assert "plan not found" not in capsys.readouterr().err
    assert seen[0][seen[0].index("--plan") + 1] == str(top / "docs/plans/p.md")
