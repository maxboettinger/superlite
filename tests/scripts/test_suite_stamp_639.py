# tests/scripts/test_suite_stamp_639.py
import subprocess
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import suite_stamp as ss  # noqa: E402


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@e", *a],
                          capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, files, msg="c", delete=()):
    for name, body in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    for name in delete:
        (repo / name).unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def tree(repo, rev="HEAD"):
    return git(repo, "rev-parse", rev + "^{tree}")


def stamp(repo, rev="HEAD", platform="macOS", tests="12", tree_id=None, text=None):
    t = tree(repo, rev)
    d = repo / ".git" / "maxapp" / "test"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{t}.{platform}"
    f.write_text(text if text is not None else
                 f"tree={tree_id or t}\nplatform={platform}\ncommit={git(repo, 'rev-parse', rev)}\ntests={tests}\n")
    return f


def repo_with(tmp_path, files=None):
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q")
    commit(r, files or {"src/a.py": "1\n", "docs/x.md": "a\n"}, "base")
    return r


def test_maxapp_platforms():
    assert ss.maxapp_platforms("maxapp test") == ["macOS"]
    assert ss.maxapp_platforms("maxapp test --ios") == ["macOS", "iOS"]
    assert ss.maxapp_platforms("/usr/bin/maxapp test") == ["macOS"]
    assert ss.maxapp_platforms("maxapp test --only A/B") is None
    assert ss.maxapp_platforms("xcodebuild test -scheme X") is None
    assert ss.maxapp_platforms("maxapp test 'unclosed") is None
    assert ss.maxapp_platforms("") is None


def test_is_not_code():
    assert ss.is_not_code("docs/a/b.md", ["docs/**"])
    assert ss.is_not_code("README.md", ["**/*.md"])
    assert ss.is_not_code("a/b/README.md", ["**/*.md"])
    assert not ss.is_not_code("Sources/a.swift", ["docs/**", "**/*.md"])
    assert not ss.is_not_code("a.py", [])


def test_green_base_head_stamped(tmp_path):
    r = repo_with(tmp_path)
    f = stamp(r)
    out = ss.green_base(r, "maxapp test", [])
    assert out == {"commit": git(r, "rev-parse", "HEAD"), "tree": tree(r), "tests": 12,
                   "platforms": ["macOS"], "stamps": [str(f)], "changed": []}


def test_stamp_must_name_tree_and_platform(tmp_path):
    r = repo_with(tmp_path)
    for kw in ({"tree_id": "deadbeef"}, {"text": ""}, {"tests": "0"}, {"tests": "x"},
               {"text": f"tree={tree(r)}\nplatform=iOS\ncommit=x\ntests=3\n"}):
        stamp(r, **kw)
        assert ss.green_base(r, "maxapp test", []) is None, kw


def test_dirty_code_change_is_no_hit(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    (r / "src/a.py").write_text("2\n")
    assert ss.green_base(r, "maxapp test", ["docs/**"]) is None


def test_untracked_code_file_is_no_hit(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    (r / "src/new.py").write_text("x\n")
    assert ss.green_base(r, "maxapp test", ["docs/**"]) is None


def test_docs_commit_after_stamp_hits(tmp_path):
    r = repo_with(tmp_path)
    parent = git(r, "rev-parse", "HEAD")
    stamp(r)
    commit(r, {"docs/x.md": "b\n"})
    out = ss.green_base(r, "maxapp test", ["docs/**"])
    assert out["commit"] == parent and out["changed"] == ["docs/x.md"]


def test_no_globs_needs_exact_tree(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    commit(r, {"docs/x.md": "b\n"})
    assert ss.green_base(r, "maxapp test", []) is None


def test_deleted_code_file_counts(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    commit(r, {}, delete=["src/a.py"])
    assert ss.green_base(r, "maxapp test", ["docs/**"]) is None


def test_ios_needs_both_platforms(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    assert ss.green_base(r, "maxapp test --ios", []) is None
    stamp(r, platform="iOS", tests="5")
    out = ss.green_base(r, "maxapp test --ios", [])
    assert out["tests"] == 17 and out["platforms"] == ["macOS", "iOS"] and len(out["stamps"]) == 2


def test_dot_build_ignored(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    (r / ".build").mkdir()
    (r / ".build/x").write_text("x\n")
    out = ss.green_base(r, "maxapp test", [])
    assert out is not None and out["changed"] == []


def test_not_git_repo(tmp_path):
    assert ss.green_base(tmp_path, "maxapp test", []) is None
    assert ss.sync_change(tmp_path, "a", "b", []) == ("code", [])


def test_non_maxapp_command_is_none(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    assert ss.green_base(r, "pytest", []) is None


def test_sync_change(tmp_path):
    r = repo_with(tmp_path)
    t = git(r, "rev-parse", "HEAD")
    assert ss.sync_change(r, t, t, []) == ("unchanged", [])
    commit(r, {"docs/x.md": "b\n"})
    h1 = git(r, "rev-parse", "HEAD")
    assert ss.sync_change(r, t, h1, ["docs/**"]) == ("not_code", ["docs/x.md"])
    commit(r, {"src/a.py": "2\n"})
    h2 = git(r, "rev-parse", "HEAD")
    assert ss.sync_change(r, t, h2, ["docs/**"]) == ("code", ["docs/x.md", "src/a.py"])
    assert ss.sync_change(r, t, h1, []) == ("code", ["docs/x.md"])
