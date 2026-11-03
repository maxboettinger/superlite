"""Review packet after a mid-run fast-forward: merged files are not the run's changes (#100)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_autocommit import checkpoint, git, make_repo, run, write  # noqa: E402

TASK_FILES = ["src/a.py", "src/b.py", "tests/test_a.py"]


@pytest.fixture()
def ff_repo(tmp_path):
    """T1 checkpoint on A, HEAD fast-forwarded to B (adds social/feed.py), T2 checkpoint after the move."""
    repo = make_repo(tmp_path)
    start = git(repo, "rev-parse", "HEAD")
    git(repo, "branch", "social")
    write(repo, "src/a.py", "def parse(t):\n    return t.split()\n")
    write(repo, "tests/test_a.py", "def test_p():\n    assert 1\n")
    r = checkpoint(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    git(repo, "worktree", "add", "-q", str(tmp_path / "social"), "social")
    write(tmp_path / "social", "social/feed.py", "FEED = []\n")
    git(tmp_path / "social", "add", "-A")
    git(tmp_path / "social", "commit", "-q", "-m", "social feed")
    git(repo, "merge", "-q", "--ff-only", "social")
    write(repo, "src/b.py", "def lex(t):\n    return list(t)\n")
    r = checkpoint(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    return repo, start


@pytest.fixture()
def pt_review():
    sys.path.insert(0, str(HERE.parents[1] / "skills" / "subagent-driven-development" / "scripts"))
    import pt_review as mod
    return mod


@pytest.mark.parametrize("which", ["HEAD", "start"])
def test_diff_stat_and_excerpts_show_only_task_files(ff_repo, pt_review, which):
    repo, start = ff_repo
    base = "HEAD" if which == "HEAD" else start
    stat = pt_review.git_diff_stat(repo, base)
    assert "social/feed.py" not in stat
    assert all(f in stat for f in TASK_FILES)
    changed, diffs = pt_review.changed_diffs(repo, base, [])
    assert sorted(changed) == TASK_FILES
    assert sorted(f for f, _ in diffs) == TASK_FILES


@pytest.fixture()
def ff_shared(tmp_path):
    """T1 checkpoint on A, HEAD fast-forwarded to B (changes src/b.py), T2 edits src/b.py and checkpoints (#104)."""
    repo = make_repo(tmp_path)
    write(repo, "src/b.py", "def lex(t):\n    return list(t)\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "b")
    start = git(repo, "rev-parse", "HEAD")
    git(repo, "branch", "social")
    write(repo, "src/a.py", "def parse(t):\n    return t.split()\n")
    r = checkpoint(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    git(repo, "worktree", "add", "-q", str(tmp_path / "social"), "social")
    write(tmp_path / "social", "src/b.py", "MERGED = 1\n\n\ndef lex(t):\n    return list(t)\n")
    git(tmp_path / "social", "commit", "-q", "-am", "social: b")
    git(repo, "merge", "-q", "--ff-only", "social")
    write(repo, "src/b.py", "MERGED = 1\n\n\ndef lex(t):\n    return list(t)\n\n\nRUN_LINE = 2\n")
    r = checkpoint(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    return repo, start


def added(lines):
    return [ln for ln in lines if ln.startswith("+") and not ln.startswith("+++") and ln.strip("+ ")]


@pytest.mark.parametrize("which", ["HEAD", "start"])
def test_owned_file_the_merge_changed_shows_only_run_lines(ff_shared, pt_review, which):
    """#104: a file T2 checkpointed after the fast-forward holds the merged lines; its hunk shows only T2's."""
    repo, start = ff_shared
    changed, diffs = pt_review.changed_diffs(repo, "HEAD" if which == "HEAD" else start, [])
    assert sorted(changed) == ["src/a.py", "src/b.py"]
    assert added(dict(diffs)["src/b.py"]) == ["+RUN_LINE = 2"]


def test_packet_hunk_of_merged_owned_file_has_no_merged_lines(ff_shared):
    repo, _ = ff_shared
    r = run("pt_review", "packet", "--plan", "plan.md", "--root", str(repo), "--base", "HEAD",
            "--wait-timeout", "0", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    packet = (repo / ".superlite" / "review-packet.md").read_text(encoding="utf-8")
    assert "+RUN_LINE = 2" in packet
    assert "+MERGED = 1" not in packet


def test_packet_after_fast_forward_lists_no_merged_file(ff_repo):
    repo, _ = ff_repo
    r = run("pt_review", "packet", "--plan", "plan.md", "--root", str(repo), "--base", "HEAD",
            "--wait-timeout", "0", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    packet = (repo / ".superlite" / "review-packet.md").read_text(encoding="utf-8")
    assert "social/feed.py" not in packet
    assert "src/b.py" in packet
