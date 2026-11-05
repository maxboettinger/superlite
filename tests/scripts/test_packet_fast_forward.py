"""Review packet after a mid-run fast-forward: merged files are not the run's changes (#100)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_autocommit import ENV, checkpoint, git, make_repo, run, write  # noqa: E402

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


def test_diff_stat_without_moved_run_file_matches_git(ff_repo, pt_review):
    """#109: the stat is built from --numstat; with no run file the merge changed it reads as git's own --stat."""
    repo, _ = ff_repo
    native = git(repo, "diff", "--stat", *pt_review.diff_range(repo, "HEAD"))
    assert pt_review.git_diff_stat(repo, "HEAD").strip() == native  # the helper strips the leading space


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


@pytest.mark.parametrize("which", ["HEAD", "start"])
def test_diff_stat_counts_only_run_lines_of_merged_owned_file(ff_shared, pt_review, which):
    """#109: the stat counts the same lines as the hunk: T2's 3 lines in src/b.py, not the 3 merged ones too."""
    repo, start = ff_shared
    stat = pt_review.git_diff_stat(repo, "HEAD" if which == "HEAD" else start)
    rows = {ln.split("|")[0].strip(): ln.split("|")[1].strip() for ln in stat.splitlines() if "|" in ln}
    assert rows == {"src/a.py": "2 ++", "src/b.py": "3 +++"}
    assert stat.splitlines()[-1].strip() == "2 files changed, 5 insertions(+)"


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


def test_stat_and_hunks_read_one_per_file_range(ff_shared, pt_review, monkeypatch):
    """#113: a per-file range change reaches the stat and the hunks together; here src/a.py gets an empty range."""
    repo, _ = ff_shared
    rr = pt_review.run_ranges(repo, "HEAD")
    assert rr.of("src/b.py") == ["HEAD", pt_review.diff_head(repo)]  # moved: HEAD against the checkpoint
    assert rr.of("src/a.py") == pt_review.diff_range(repo, "HEAD")
    of = pt_review.RunRanges.of
    monkeypatch.setattr(pt_review.RunRanges, "of", lambda self, f: ["HEAD", "HEAD"] if f == "src/a.py" else of(self, f))
    stat = pt_review.git_diff_stat(repo, "HEAD")
    assert "src/a.py" not in stat and "src/b.py" in stat
    _, diffs = pt_review.changed_diffs(repo, "HEAD", [])
    assert [f for f, _ in diffs] == ["src/b.py"]


def test_packet_lists_moved_files_once(ff_shared, pt_review, monkeypatch):
    """#113: one packet resolves the files HEAD changed since the run started once, for the stat and the hunks."""
    repo, start = ff_shared
    real, calls = pt_review.subprocess.run, []

    def spy(cmd, *a, **kw):
        calls.append(list(cmd))
        return real(cmd, *a, **kw)

    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(pt_review.subprocess, "run", spy)
    assert pt_review.main(["packet", "--plan", "plan.md", "--root", str(repo), "--base", "HEAD",
                           "--wait-timeout", "0"]) == 0
    assert sum(c[-5:] == ["diff", "--name-only", "-z", start, "HEAD"] for c in calls) == 1


def fast_forward(repo, tmp_path, files):
    """Fast-forward repo's HEAD over a commit that writes `files` ({path: text}) on a side branch."""
    git(repo, "branch", "-f", "social", "HEAD")
    side = tmp_path / "social"
    if not side.exists():
        git(repo, "worktree", "add", "-q", str(side), "social")
    for rel, text in files.items():
        write(side, rel, text)
    git(side, "add", "-A")
    git(side, "commit", "-q", "-m", "social")
    git(repo, "merge", "-q", "--ff-only", "social")


def packet_for(repo, base):
    r = run("pt_review", "packet", "--plan", "plan.md", "--root", str(repo), "--base", base,
            "--wait-timeout", "0", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    return (repo / ".superlite" / "review-packet.md").read_text(encoding="utf-8")


def test_ff_glob_owns_post_merge_checkpoint(tmp_path, pt_review):
    """#158: T4 owns the directory docs/; a fast-forward adds docs/merged.md before its checkpoint."""
    repo = make_repo(tmp_path)
    old = git(repo, "rev-parse", "HEAD")
    write(repo, "src/a.py", "def parse(t):\n    return t.split()\n")
    assert checkpoint(repo, "T1").returncode == 0
    fast_forward(repo, tmp_path, {"docs/merged.md": "merged\n"})
    write(repo, "docs/mine.md", "mine\n")
    r = checkpoint(repo, "T4")
    assert r.returncode == 0, r.stdout + r.stderr
    new = git(repo, "rev-parse", "HEAD")
    assert new != old
    changed, diffs = pt_review.changed_diffs(repo, new, [])
    assert "docs/merged.md" not in changed and "docs/mine.md" in changed
    assert "docs/merged.md" not in pt_review.git_diff_stat(repo, new)
    assert "docs/merged.md" not in packet_for(repo, new)


def test_ff_merged_file_checkpointed_before_merge(tmp_path, pt_review):
    """#158: the run checkpoints src/b.py, then a fast-forward changes lines of it the run did not touch."""
    repo = make_repo(tmp_path)
    write(repo, "src/b.py", "def lex(t):\n    return list(t)\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "b")
    write(repo, "src/b.py", "def lex(t):\n    return list(t)\n\n\nRUN_LINE = 2\n")
    assert checkpoint(repo, "T2").returncode == 0
    git(repo, "checkout", "-q", "--", "src/b.py")  # git refuses a fast-forward over a dirty tracked file
    fast_forward(repo, tmp_path, {"src/b.py": "MERGED = 1\n\n\ndef lex(t):\n    return list(t)\n"})
    new = git(repo, "rev-parse", "HEAD")
    changed, diffs = pt_review.changed_diffs(repo, new, [])
    assert changed == ["src/b.py"]
    lines = dict(diffs)["src/b.py"]
    assert "+RUN_LINE = 2" in lines and "+MERGED = 1" not in lines
    assert not any(ln.startswith("-") and not ln.startswith("---") for ln in lines)
    packet = packet_for(repo, new)
    assert "+MERGED = 1" not in packet


def test_ff_non_ascii_file_checkpointed_before_merge(tmp_path, pt_review):
    """#158: a path git quotes in numstat (non-ASCII, space) still picks the run range for a merged file."""
    repo = make_repo(tmp_path)
    name = "docs/\u00e4 b.md"
    write(repo, name, "def lex(t):\n    return list(t)\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "b")
    write(repo, name, "def lex(t):\n    return list(t)\n\n\nRUN_LINE = 2\n")
    assert checkpoint(repo, "T4").returncode == 0
    git(repo, "checkout", "-q", "--", name)
    fast_forward(repo, tmp_path, {name: "MERGED = 1\n\n\ndef lex(t):\n    return list(t)\n"})
    new = git(repo, "rev-parse", "HEAD")
    changed, diffs = pt_review.changed_diffs(repo, new, [])
    assert changed == [name]
    lines = dict(diffs)[name]
    assert "+RUN_LINE = 2" in lines and "+MERGED = 1" not in lines
    assert not any(ln.startswith("-") and not ln.startswith("---") for ln in lines)


def test_ff_explicit_sha_base(ff_repo, pt_review):
    """#158: an explicit sha as --base gives the same files and stat as the word HEAD."""
    repo, _ = ff_repo
    new = git(repo, "rev-parse", "HEAD")
    assert pt_review.git_diff_stat(repo, new) == pt_review.git_diff_stat(repo, "HEAD")
    assert pt_review.changed_diffs(repo, new, []) == pt_review.changed_diffs(repo, "HEAD", [])
    packet = packet_for(repo, new)
    assert "social/feed.py" not in packet and "src/b.py" in packet


def _shown(pt_review, repo):
    new = git(repo, "rev-parse", "HEAD")
    changed, diffs = pt_review.changed_diffs(repo, new, [])
    return changed, dict(diffs)


def test_ff_run_only_deletes_lines_checkpointed_before_merge(tmp_path, pt_review):
    """#158: a run that only deletes lines of a file the merge then extends shows its deletions, not the merged lines."""
    repo = make_repo(tmp_path)
    write(repo, "src/b.py", "".join(f"L{i} = {i}\n" for i in range(10)))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c")
    write(repo, "src/b.py", "".join(f"L{i} = {i}\n" for i in range(2, 10)))
    assert checkpoint(repo, "T2").returncode == 0
    git(repo, "checkout", "-q", "--", "src/b.py")
    fast_forward(repo, tmp_path, {"src/b.py": "".join(f"L{i} = {i}\n" for i in range(10)) + "M1 = 1\nM2 = 2\n"})
    changed, diffs = _shown(pt_review, repo)
    lines = diffs["src/b.py"]
    assert "-L0 = 0" in lines and "-L1 = 1" in lines
    assert not any("M1" in ln or "M2" in ln for ln in lines)


def test_ff_run_only_deletes_lines_checkpointed_after_merge(tmp_path, pt_review):
    repo = make_repo(tmp_path)
    write(repo, "src/b.py", "".join(f"L{i} = {i}\n" for i in range(10)))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c")
    fast_forward(repo, tmp_path, {"src/b.py": "".join(f"L{i} = {i}\n" for i in range(10)) + "M1 = 1\nM2 = 2\n"})
    write(repo, "src/b.py", "".join(f"L{i} = {i}\n" for i in range(2, 10)) + "M1 = 1\nM2 = 2\n")
    assert checkpoint(repo, "T2").returncode == 0
    changed, diffs = _shown(pt_review, repo)
    lines = diffs["src/b.py"]
    assert "-L0 = 0" in lines and not any("M1" in ln for ln in lines)


def test_ff_merge_deletes_file_run_changed(tmp_path, pt_review):
    repo = make_repo(tmp_path)
    write(repo, "src/b.py", "A = 1\nB = 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "d")
    write(repo, "src/b.py", "A = 1\nB = 2\nRUN = 3\n")
    assert checkpoint(repo, "T2").returncode == 0
    git(repo, "checkout", "-q", "--", "src/b.py")
    git(repo, "branch", "-f", "social", "HEAD")
    side = tmp_path / "social"
    git(repo, "worktree", "add", "-q", str(side), "social")
    git(side, "rm", "-q", "src/b.py")
    git(side, "commit", "-q", "-m", "rm")
    git(repo, "merge", "-q", "--ff-only", "social")
    changed, diffs = _shown(pt_review, repo)
    lines = diffs.get("src/b.py", [])
    assert "+RUN = 3" in lines and "-A = 1" not in lines
