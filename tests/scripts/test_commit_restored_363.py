"""commit_task: a file restored to its HEAD content is checkpointed again (#363)."""
import re
import sys

from test_autocommit import ENV, SCRIPTS, git, make_repo, run, write  # noqa: F401

sys.path.insert(0, str(SCRIPTS))


def base(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 0\n")
    write(repo, "src/b.py", "B = 0\n")
    write(repo, "tests/test_a.py", "def test_a():\n    assert 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base2")
    return repo


def ck(repo, *tids):
    return run("commit_task", *tids, "--plan", "plan.md", cwd=repo)


def restored_case(tmp_path):
    repo = base(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "tests/test_a.py", "def test_a():\n    assert 2\n")
    s1 = ck(repo, "T1").stdout.strip()
    git(repo, "checkout", "HEAD", "--", "src/a.py")
    return repo, s1


def test_restored_file_is_checkpointed(tmp_path):
    repo, s1 = restored_case(tmp_path)
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stderr
    s2 = r.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", s2) and s2 != s1
    assert "restored src/a.py (back to its HEAD content)" in r.stderr
    assert git(repo, "show", f"{s2}:src/a.py") == "A = 0"
    assert "assert 2" in git(repo, "show", f"{s2}:tests/test_a.py")
    assert git(repo, "rev-parse", f"{s2}^") == s1


def test_only_restored_file(tmp_path):
    repo = base(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    assert ck(repo, "T1").returncode == 0
    git(repo, "checkout", "HEAD", "--", "src/a.py")
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stderr
    assert "nothing to commit" not in r.stdout + r.stderr
    assert git(repo, "show", f"{r.stdout.strip()}:src/a.py") == "A = 0"


def test_apply_after_restore(tmp_path):
    repo, _ = restored_case(tmp_path)
    assert ck(repo, "T1").returncode == 0
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stderr + r.stdout
    assert git(repo, "show", "HEAD:src/a.py") == "A = 0"
    assert "assert 2" in git(repo, "show", "HEAD:tests/test_a.py")
    assert git(repo, "status", "--porcelain") == ""


def test_rerun_after_restore_says_no_change(tmp_path):
    repo, _ = restored_case(tmp_path)
    s2 = ck(repo, "T1").stdout.strip()
    r = ck(repo, "T1")
    assert r.stdout == f"T1: no change since its last checkpoint {s2}\n"
    assert "restored" not in r.stderr


def test_other_tasks_restored_file_untouched(tmp_path):
    repo = base(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    ck(repo, "T1")
    write(repo, "src/b.py", "B = 1\n")
    ck(repo, "T2")
    git(repo, "checkout", "HEAD", "--", "src/b.py")
    write(repo, "src/a.py", "A = 2\n")
    r = ck(repo, "T1")
    s3 = r.stdout.strip()
    assert git(repo, "show", f"{s3}:src/b.py") == "B = 1"
    assert "restored src/b.py" not in r.stderr


def test_reverted_owned_in_process(tmp_path, monkeypatch):
    repo = base(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    assert ck(repo, "T1").returncode == 0
    git(repo, "checkout", "HEAD", "--", "src/a.py")
    import commit_task
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    assert commit_task.reverted_owned(["src/a.py"], set(), "plan.md") == ["src/a.py"]
    assert commit_task.reverted_owned(["src/a.py"], {"src/a.py"}, "plan.md") == []
    assert commit_task.reverted_owned(["src/b.py"], set(), "plan.md") == []
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "1")
    assert commit_task.reverted_owned(["src/a.py"], set(), "plan.md") == []


def test_docstring_and_comment_match_behaviour():
    text = (SCRIPTS / "commit_task.py").read_text()
    assert "restored F (back to its HEAD content)" in text.split('"""')[1]
    assert "# O(d) stat walk, no spawn" in text
    assert "O(1) git spawn" not in text
