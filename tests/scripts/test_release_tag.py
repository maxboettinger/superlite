import json, os, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import release_tag as rt  # noqa: E402
import backlog_state as bs  # noqa: E402
from test_backlog_ship import sh, ship, locked, b1  # noqa: E402,F401


def test_level_examples():
    assert rt.level("1.5.244", "1.5.245") == "patch"
    assert rt.level("1.5.244", "1.6.0") == "minor"
    assert rt.level("1.5.244", "2.0.0") == "major"


def test_level_invalid():
    assert rt.level("1.5.244", "1.5.243") == "invalid" and rt.level("1.5", "1.6.0") == "invalid" and rt.level("1.5.244", "x") == "invalid"
    assert rt.level("1.5.244", "1.5.244") == "none"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main"); (tmp_path / "f").write_text("x")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "c")
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True); subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    return tmp_path


def test_tag_annotated(repo):
    head = git(repo, "rev-parse", "HEAD")
    assert rt.tag(repo, "1.5.245", head, push=False) == "tag v1.5.245 created"
    assert git(repo, "cat-file", "-t", "v1.5.245") == "tag"
    assert git(repo, "tag", "-n1", "v1.5.245").endswith("Version 1.5.245")


def test_tag_exists(repo):
    head = git(repo, "rev-parse", "HEAD"); rt.tag(repo, "1.5.245", head, push=False)
    (repo / "f").write_text("y"); git(repo, "commit", "-qam", "d")
    before = git(repo, "rev-parse", "v1.5.245^{}")
    assert rt.tag(repo, "1.5.245", git(repo, "rev-parse", "HEAD"), push=False) == "tag v1.5.245 exists"
    assert git(repo, "rev-parse", "v1.5.245^{}") == before and git(repo, "tag").split() == ["v1.5.245"]


def test_tag_never_raises(repo):
    r = rt.tag(repo, "1.5.245", "nosuchsha", push=False)
    assert r.startswith("tag v1.5.245 failed: ") and len(r.splitlines()) == 1


def test_tag_push_cmd(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(rt, "_run", lambda cmd, cwd=None, timeout=None: (calls.append(cmd), (0, ""))[1])
    assert rt.tag(tmp_path, "1.5.245", "abc1234") == "tag v1.5.245 pushed"
    assert calls == [["git", "fetch", "origin"], ["git", "tag", "-a", "v1.5.245", "-m", "Version 1.5.245", "abc1234"],
                     ["git", "push", "origin", "refs/tags/v1.5.245"]]


def _setup_version(sh, cur):
    (sh.wt / "scripts" / "bump-version.sh").write_text(""); (sh.wt / "package.json").write_text(json.dumps({"version": cur}))
    (sh.wt / ".version-bump.json").write_text(json.dumps({"files": [{"path": "package.json", "field": "version"}]}))


def test_bump_refuses_minor(sh, capsys):
    locked(sh, capsys); _setup_version(sh, "1.5.244")
    assert ship(capsys, "B1", "bump", "--version", "1.6.0") == (2, "refused: a lead bumps the patch number only (sl release minor|major)\n")
    assert not any(c[:2] == ["bash", "scripts/bump-version.sh"] for c in sh.calls)


def test_bump_patch_ok(sh, capsys):
    locked(sh, capsys); _setup_version(sh, "1.5.244")
    assert ship(capsys, "B1", "bump", "--version", "1.5.245") == (0, "B1 version 1.5.245\n")
    (sh.wt / "package.json").write_text('{"version": "1.5.245"}'); bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").pop("version", None))
    assert ship(capsys, "B1", "bump") == (0, "B1 version 1.5.246\n")


def _merge(sh, capsys, monkeypatch, tag_result):
    import release_tag
    locked(sh, capsys); bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"version": "1.5.245"}))
    body = sh.wt / "b.md"; body.write_text("Batch B1.\n"); tags = []
    monkeypatch.setattr(release_tag, "tag", lambda root, v, sha, push=True: (tags.append((v, sha)), tag_result)[1])
    sh.replies = {"maxapp ship": (0, "merged #12 as abc\n"), "gh pr view 12 --json mergeCommit -q .mergeCommit.oid": (0, "abc1234def\n")}
    return ship(capsys, "B1", "merge", "--title", "t", "--body-file", str(body)), tags


def test_merge_tags(sh, capsys, monkeypatch):
    (rc, out), tags = _merge(sh, capsys, monkeypatch, "tag v1.5.245 pushed")
    assert rc == 0 and "tag v1.5.245 pushed" in out
    assert tags == [("1.5.245", "abc1234def")]
    assert ["gh", "pr", "view", "12", "--json", "mergeCommit", "-q", ".mergeCommit.oid"] in sh.calls


def test_merge_tag_failure_keeps_exit(sh, capsys, monkeypatch):
    (rc, out), _ = _merge(sh, capsys, monkeypatch, "tag v1.5.245 failed: boom")
    assert rc == 0 and "tag v1.5.245 failed: boom" in out
