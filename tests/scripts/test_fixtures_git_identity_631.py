"""_fixtures gives a host without a git identity one, in git's own global-config order, and leaves a repo's own identity first (#631)."""
import os
import subprocess

import _fixtures

SESSION_GLOBAL = os.environ.get("GIT_CONFIG_GLOBAL")  # the value every test here must leave behind


def git(repo, *args):  # inherits os.environ as monkeypatch set it
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def includes(cfg):  # as git itself parses them
    r = subprocess.run(["git", "config", "--file", str(cfg), "--get-all", "include.path"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def no_identity_host(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "unset")  # set first: delenv of an unset var records nothing to undo, and
    monkeypatch.delenv("GIT_CONFIG_GLOBAL")  # _git_identity writes os.environ directly
    base = tmp_path / "base"
    base.mkdir()
    return home, base


def test_includes_xdg_then_home_gitconfig(tmp_path, monkeypatch):
    home, base = no_identity_host(tmp_path, monkeypatch)
    _fixtures._git_identity(base)
    assert os.environ["GIT_CONFIG_GLOBAL"] == str(base / "gitconfig")
    assert includes(base / "gitconfig") == [str(tmp_path / "xdg" / "git" / "config"), str(home / ".gitconfig")]


def test_a_set_global_config_is_included_alone(tmp_path, monkeypatch):
    _, base = no_identity_host(tmp_path, monkeypatch)
    own = tmp_path / "own.gitconfig"
    own.write_text("[init]\n\tdefaultBranch = trunk\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(own))
    _fixtures._git_identity(base)
    assert includes(base / "gitconfig") == [str(own)]
    repo = tmp_path / "repo"
    repo.mkdir()
    assert git(repo, "init", "-q").returncode == 0
    assert git(repo, "branch", "--show-current").stdout.strip() == "trunk"  # the host's own config still reads


def test_commit_works_and_a_repo_identity_wins(tmp_path, monkeypatch):
    _, base = no_identity_host(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    _fixtures._git_identity(base)
    assert git(repo, "commit", "-q", "--allow-empty", "-m", "a").returncode == 0
    assert git(repo, "log", "-1", "--format=%an <%ae>").stdout.strip() == "superlite tests <tests@superlite.invalid>"
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "commit", "-q", "--allow-empty", "-m", "b")
    assert git(repo, "log", "-1", "--format=%an <%ae>").stdout.strip() == "Test <test@example.com>"


def test_a_host_with_an_identity_is_untouched(tmp_path, monkeypatch):
    _, base = no_identity_host(tmp_path, monkeypatch)
    own = tmp_path / "own.gitconfig"
    own.write_text("[user]\n\tname = Host\n\temail = host@example.com\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(own))
    _fixtures._git_identity(base)
    assert os.environ["GIT_CONFIG_GLOBAL"] == str(own)
    assert not (base / "gitconfig").exists()


def test_odd_paths_round_trip(tmp_path, monkeypatch):
    _, base = no_identity_host(tmp_path, monkeypatch)
    own = tmp_path / ("a b #c;d" + ('' if os.name == "nt" else ' "e\\f')) / "own.gitconfig"  # a Windows name holds no quote or backslash
    own.parent.mkdir()
    own.write_text("[init]\n\tdefaultBranch = trunk\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(own))
    _fixtures._git_identity(base)
    assert includes(base / "gitconfig") == [str(own)]


def test_quote_escapes_backslash_and_quote():
    assert _fixtures._git_quote('C:\\Users\\a "b"') == '"C:\\\\Users\\\\a \\"b\\""'


def test_session_global_config_left_as_it_was():  # runs last in this file: no test above leaked its tmp config
    assert os.environ.get("GIT_CONFIG_GLOBAL") == SESSION_GLOBAL
