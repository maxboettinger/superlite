import subprocess
import sys

from test_graphify_gate import SCRIPT, fake_bin, git, make_repo, run_gate  # noqa: F401

sys.path.insert(0, str(SCRIPT.parent))
import graphify_gate  # noqa: E402


def lines(repo):
    f = repo / ".git" / "info" / "exclude"
    return f.read_text().splitlines() if f.exists() else []


def test_use_adds_graphify_out_to_exclude(tmp_path):
    repo = make_repo(tmp_path, 60)
    assert run_gate(repo, tmp_path, with_fake=True)["excluded"] is True
    assert graphify_gate.exclude_output(str(repo)) is True
    assert lines(repo).count("graphify-out/") == 1


def test_small_repo_writes_nothing(tmp_path):
    repo = make_repo(tmp_path, 3)
    r = run_gate(repo, tmp_path, with_fake=True)
    assert r["excluded"] is False
    assert "graphify-out/" not in lines(repo)


def test_worktree_writes_common_exclude(tmp_path):
    repo = make_repo(tmp_path, 60)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", str(wt), "-b", "wt")
    assert run_gate(wt, tmp_path, with_fake=True)["excluded"] is True
    assert "graphify-out/" in lines(repo)
    (wt / "graphify-out").mkdir()
    (wt / "graphify-out" / "g.json").write_text("{}")
    st = subprocess.run(["git", "-C", str(wt), "status", "--porcelain"], capture_output=True, text=True).stdout
    assert "graphify-out" not in st


def test_gitignore_already_covers(tmp_path):
    repo = make_repo(tmp_path, 60)
    (repo / ".gitignore").write_text("graphify-out/\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    assert run_gate(repo, tmp_path, with_fake=True)["excluded"] is True
    assert "graphify-out/" not in lines(repo)


def test_exclude_output_non_repo(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert graphify_gate.exclude_output(str(d)) is False
