# tests/scripts/test_fleet_remote_worker_1109_1112.py
import subprocess, sys
import pytest
from test_fleet_remote_worker import world, plan_for, record, start_files, show  # noqa: F401
from test_fleet_remote_collect import env as cenv, worker, host_snapshot, git as cgit, report  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote_collect as frc  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402

FALLBACK = {"GIT_AUTHOR_NAME": "superlite", "GIT_AUTHOR_EMAIL": "superlite@localhost", "GIT_COMMITTER_NAME": "superlite", "GIT_COMMITTER_EMAIL": "superlite@localhost"}


def also_plan(world):
    plan = plan_for(world)
    text = plan.read_text()
    assert "**Owns:** src/a.py" in text
    plan.write_text(text.replace("**Owns:** src/a.py", "**Owns:** src/a.py\n**Also-touches:** docs/n.md", 1))
    return plan


def test_record_owns_also_touches(world, monkeypatch):
    (world.proj / "docs").mkdir(); (world.proj / "docs" / "n.md").write_text("old\n")
    world.git("add", "docs/n.md"); world.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "docs")
    head = world.git("rev-parse", "HEAD")
    monkeypatch.setattr(rw.trees, "base_commit", lambda root: head)
    (world.proj / "docs" / "n.md").write_text("new\n")
    plan = also_plan(world)
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    assert record(world)["remote"]["owns"] == ["src/a.py", "docs/n.md", "tests/regression/**"]
    names, ref = start_files(world)
    assert show(world, ref, "docs/n.md") == "old"


def test_record_owns_without_also_touches_unchanged(world):
    plan = plan_for(world)
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    assert record(world)["remote"]["owns"] == ["src/a.py", "tests/regression/**"]


def test_collect_applies_also_touches_edit(cenv):
    sha = host_snapshot(cenv, {"src/a.py": "two\n", "docs/n.md": "changed\n", "other.txt": "o\n"})
    worker(cenv, snap=sha, owns=("src/*.py", "docs/n.md", "tests/regression/**"))
    out = frc.collect(cenv.sd, "W2", report())
    assert out["collected"]["applied"] == ["docs/n.md", "src/a.py"] or sorted(out["collected"]["applied"]) == ["docs/n.md", "src/a.py"]
    assert out["concerns"] == ["remote changes outside the task not applied: other.txt"]
    assert (cenv.proj / "src" / "a.py").read_text() == "two\n"
    assert (cenv.proj / "docs" / "n.md").read_text() == "changed\n"
    assert not (cenv.proj / "other.txt").exists()


def test_write_worker_env_has_local_identity(world):
    world.git("config", "user.name", "Ada Lead"); world.git("config", "user.email", "ada@example.com")
    b = world.sd / "briefs" / "f.md"; b.write_text("fix")
    rw.spawn(world.sd, "fixer", "sonnet", world.proj, "box", brief=str(b))
    want = {"GIT_AUTHOR_NAME": "Ada Lead", "GIT_AUTHOR_EMAIL": "ada@example.com", "GIT_COMMITTER_NAME": "Ada Lead", "GIT_COMMITTER_EMAIL": "ada@example.com"}
    assert {k: world.panes[0]["env"].get(k) for k in want} == want
    rw.spawn(world.sd, "research", None, world.proj, "box")
    env = world.panes[1]["env"]
    assert "GIT_AUTHOR_NAME" not in env and "GIT_COMMITTER_EMAIL" not in env


def test_git_ident_falls_back_without_config(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing")); monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    d = tmp_path / "r"; d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    assert rw.git_ident(d) == FALLBACK
    subprocess.run(["git", "-C", str(d), "config", "user.name", "Ada"], check=True)
    assert rw.git_ident(d) == FALLBACK
    subprocess.run(["git", "-C", str(d), "config", "user.email", "a@e.com"], check=True)
    assert rw.git_ident(d)["GIT_AUTHOR_EMAIL"] == "a@e.com"


@pytest.mark.parametrize("exc", [OSError("no git"), subprocess.TimeoutExpired(["git"], 1)])
def test_git_ident_falls_back_on_git_error(tmp_path, monkeypatch, exc):
    def boom(*a, **k): raise exc
    monkeypatch.setattr(rw.subprocess, "run", boom)
    assert rw.git_ident(tmp_path) == FALLBACK
