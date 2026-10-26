"""autocommit apply: one commit per task, --no-squash, interleave fallback."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autocommit import SCRIPTS, make_repo, write, git, run, ENV  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402


def cp(repo, monkeypatch, tid, files, **contents):
    monkeypatch.chdir(repo)
    for rel, text in contents.items():
        write(repo, rel.replace("__", "/").replace("_py", ".py"), text)
    return autocommit.checkpoint(tid, "p" if tid == "T1" else "l", files, "plan.md")


def repeated(repo, monkeypatch):
    cp(repo, monkeypatch, "T1", ["a.py"], a_py="v1\n")
    cp(repo, monkeypatch, "T2", ["b.py"], b_py="b\n")
    cp(repo, monkeypatch, "T1", ["a.py", "c.py"], a_py="v2\n", c_py="c\n")


def subjects(repo, base):
    return git(repo, "log", "--format=%s", f"{base}..HEAD").splitlines()


def test_apply_squashes_repeated_task(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    repeated(repo, monkeypatch)
    last_tree = git(repo, "rev-parse", f"{autocommit.load_state()['entries'][-1]['sha']}^{{tree}}")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T2: l", "T1: p"]
    assert git(repo, "show", "HEAD:a.py") == "v2" and git(repo, "show", "HEAD:c.py") == "c"
    assert git(repo, "show", "HEAD:b.py") == "b"
    assert git(repo, "rev-parse", "HEAD^{tree}") == last_tree
    assert git(repo, "for-each-ref", "refs/superlite") == ""


def test_no_squash_keeps_each_checkpoint(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    repeated(repo, monkeypatch)
    r = run("autocommit", "apply", "--no-squash", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T1: p", "T2: l", "T1: p"]


def test_squash_falls_back_on_interleave(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", ["s.py"], s_py="1\n")
    cp(repo, monkeypatch, "T2", ["s.py"], s_py="2\n")
    cp(repo, monkeypatch, "T1", ["s.py", "a.py"], s_py="3\n", a_py="a\n")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "squash skipped: tasks interleave on s.py" in r.stdout
    assert len(subjects(repo, base)) == 3
    assert git(repo, "show", "HEAD:s.py") == "3"


def test_squash_falls_back_on_plan_interleave(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", ["s.py"], s_py="1\n")
    cp(repo, monkeypatch, "T2", ["s.py"], s_py="2\n")
    cp(repo, monkeypatch, "T1", ["a.py"], a_py="a\n")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "squash skipped: tasks interleave on s.py" in r.stdout
    assert subjects(repo, base) == ["T1: p", "T2: l", "T1: p"]


def test_squash_without_overlap(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", ["a.py"], a_py="1\n")
    cp(repo, monkeypatch, "T2", ["b.py"], b_py="b\n")
    cp(repo, monkeypatch, "T1", ["a.py"], a_py="2\n")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "squash skipped" not in r.stdout
    assert subjects(repo, base) == ["T2: l", "T1: p"]


def test_squash_on_moved_head(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    repeated(repo, monkeypatch)
    (repo / "README.md").write_text("moved\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "manual readme")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T2: l", "T1: p", "manual readme"]
    assert git(repo, "show", "HEAD:a.py") == "v2" and git(repo, "show", "HEAD:README.md") == "moved"


def test_squash_entries_cases():
    es = [{"task": "T1", "sha": "a", "title": "T1: p", "files": ["x"]},
          {"task": "T2", "sha": "b", "title": "T2: l", "files": ["y"]},
          {"task": "T1", "sha": "c", "title": "T1: p", "files": ["x", "z"]}]
    assert autocommit.squash_entries(es) == [
        {"task": "T1", "sha": "c", "title": "T1: p", "files": ["x", "z"]},
        {"task": "T2", "sha": "b", "title": "T2: l", "files": ["y"]}]
    assert autocommit.squash_entries([]) == []
    assert autocommit.squash_entries(es[:2]) == es[:2]


def test_apply_unknown_arg_is_usage_error(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    repeated(repo, monkeypatch)
    r = run("autocommit", "apply", "--bogus", cwd=repo)
    assert r.returncode == 2 and "usage" in r.stderr
    assert git(repo, "for-each-ref", "refs/superlite") != ""  # nothing applied or cleaned


def test_squash_keeps_later_deletion(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", ["a.py", "d.py"], a_py="1\n", d_py="d\n")
    cp(repo, monkeypatch, "T2", ["b.py"], b_py="b\n")
    (repo / "d.py").unlink()
    cp(repo, monkeypatch, "T1", ["a.py", "d.py"], a_py="2\n")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert subjects(repo, base) == ["T2: l", "T1: p"]
    assert git(repo, "show", "HEAD:a.py") == "2"
    assert "d.py" not in git(repo, "ls-tree", "-r", "--name-only", "HEAD").split()


def test_squash_added_then_deleted_by_same_task(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    cp(repo, monkeypatch, "T1", ["t.py"], t_py="t\n")
    cp(repo, monkeypatch, "T2", ["b.py"], b_py="b\n")
    (repo / "t.py").unlink()
    cp(repo, monkeypatch, "T1", ["t.py"])
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "t.py" not in git(repo, "ls-tree", "-r", "--name-only", "HEAD").split()
    assert git(repo, "show", "HEAD:b.py") == "b"
