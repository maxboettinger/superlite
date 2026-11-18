import os
import subprocess
import sys
from pathlib import Path

import pytest

SD = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SD))
import corrections  # noqa: E402

SECRET = "key ghp_abcdefghijklmnopqrstuvwxyz0123456789"


def genv():
    return {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, env=genv())


def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t.example")
    git(r, "config", "user.name", "t")
    git(r, "config", "commit.gpgsign", "false")
    (r / "other.txt").write_text("a\n")
    git(r, "add", "other.txt")
    git(r, "commit", "-q", "-m", "init")
    return r


def f(root):
    return root / corrections.FILE


def test_add_creates_file_with_header_and_line(tmp_path):
    code, msg = corrections.add(tmp_path, "Use uv, never pip")
    assert code == 0 and msg.startswith("corrections: added (1 line, ") and msg.endswith("/2048 bytes)")
    b = f(tmp_path).read_bytes()
    assert b.startswith(b"# Corrections\n\n") and b.endswith(b"- Use uv, never pip\n") and b"\r" not in b
    assert corrections.lines(tmp_path) == ["Use uv, never pip"]


def test_add_collapses_whitespace_to_one_line(tmp_path):
    assert corrections.add(tmp_path, "- Use uv,\n  never \t pip")[0] == 0
    assert corrections.lines(tmp_path) == ["Use uv, never pip"]


def test_add_writes_home_path_as_tilde(tmp_path):
    home = str(Path.home())
    assert corrections.add(tmp_path, f"keep {home}/x tidy")[0] == 0
    assert home not in f(tmp_path).read_text()
    assert corrections.lines(tmp_path) == ["keep ~/x tidy"]


def test_add_refuses_secret_and_email(tmp_path):
    assert corrections.add(tmp_path, SECRET) == (2, "corrections: refused: the text holds a secret or an email address")
    assert corrections.add(tmp_path, "mail a@b.example")[0] == 2
    assert not f(tmp_path).exists()


def test_add_refuses_empty(tmp_path):
    assert corrections.add(tmp_path, "  - ")[0] == 2
    assert not f(tmp_path).exists()


def test_add_refuses_over_300_characters(tmp_path):
    code, msg = corrections.add(tmp_path, "x" * 301)
    assert code == 2 and "300 characters" in msg and not f(tmp_path).exists()
    assert corrections.add(tmp_path, "x" * 300)[0] == 0


def test_add_over_cap_leaves_file_byte_identical(tmp_path):
    i = 0
    while True:
        corrections.add(tmp_path, f"{i:03d} " + "y" * 200)
        i += 1
        if f(tmp_path).stat().st_size > 2048 - 250:
            break
    while f(tmp_path).stat().st_size < 2048 - 20:
        size = f(tmp_path).stat().st_size
        need = 2048 - 20 - size
        if need < 2:
            break
        corrections.add(tmp_path, "z" * min(need - 3, 200) + str(i))
        i += 1
    before = f(tmp_path).read_bytes()
    code, msg = corrections.add(tmp_path, "w" * 40)
    assert code == 2 and "2048-byte cap" in msg and "sl corrections rm" in msg
    assert f(tmp_path).read_bytes() == before


def test_add_duplicate_is_a_noop(tmp_path):
    corrections.add(tmp_path, "Use uv, never pip")
    os.utime(f(tmp_path), (1, 1))
    before = f(tmp_path).read_bytes()
    assert corrections.add(tmp_path, "  USE UV,   never PIP ") == (0, "corrections: already recorded")
    assert f(tmp_path).read_bytes() == before and f(tmp_path).stat().st_mtime == 1


def test_add_commits_only_its_file(tmp_path):
    r = repo(tmp_path)
    (r / "other.txt").write_text("changed\n")
    assert corrections.add(r, "Use uv, never pip")[0] == 0
    assert git(r, "status", "--porcelain").stdout.split() == ["M", "other.txt"]
    assert git(r, "log", "-1", "--format=%s").stdout.startswith("corrections: ")
    assert git(r, "show", "--stat", "--format=", "HEAD").stdout.count("|") == 1
    assert corrections.FILE in git(r, "show", "--stat", "--format=", "HEAD").stdout


def test_add_without_git_writes_and_makes_no_commit(tmp_path):
    code, msg = corrections.add(tmp_path, "Use uv")
    assert code == 0 and "not committed" not in msg and f(tmp_path).exists()
    assert not (tmp_path / ".git").exists()


def test_failed_commit_keeps_the_line_and_says_so(tmp_path):
    r = repo(tmp_path)
    hook = r / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho hook said no >&2\nexit 1\n")
    hook.chmod(0o755)
    code, msg = corrections.add(r, "Use uv")
    assert code == 0 and "; not committed: " in msg and msg.endswith("hook said no")
    assert corrections.lines(r) == ["Use uv"]


def test_remove_drops_line_n_and_refuses_a_bad_n(tmp_path):
    corrections.add(tmp_path, "one")
    corrections.add(tmp_path, "two")
    assert corrections.remove(tmp_path, 1)[0] == 0
    assert corrections.lines(tmp_path) == ["two"]
    assert corrections.remove(tmp_path, 5)[0] == 2
    assert corrections.remove(tmp_path, 0)[0] == 2


def test_section_formats_lines_and_none_without_file(tmp_path):
    assert corrections.section(tmp_path) is None
    corrections.add(tmp_path, "Use uv, never pip")
    corrections.add(tmp_path, "German UI strings")
    assert corrections.section(tmp_path) == (
        "## Corrections (binding, from the user)\n\n- Use uv, never pip\n- German UI strings")


def test_section_ignores_an_oversize_file(tmp_path):
    f(tmp_path).parent.mkdir(parents=True)
    f(tmp_path).write_text("# Corrections\n\n" + "- " + "a" * 3000 + "\n")
    assert corrections.lines(tmp_path) == [] and corrections.section(tmp_path) is None


def cli(*a, cwd):
    return subprocess.run([sys.executable, str(SD / "corrections.py"), *a], capture_output=True, text=True,
                          cwd=cwd, env=genv())


def test_cli_add_list_rm_exit_codes(tmp_path):
    assert cli("list", "--root", str(tmp_path), cwd=tmp_path).stdout.strip() == "corrections: none"
    assert cli("add", "Use uv, never pip", "--root", str(tmp_path), cwd=tmp_path).returncode == 0
    assert "1. Use uv, never pip" in cli("list", "--root", str(tmp_path), cwd=tmp_path).stdout
    assert cli("rm", "9", "--root", str(tmp_path), cwd=tmp_path).returncode == 2
    assert cli("rm", "1", "--root", str(tmp_path), cwd=tmp_path).returncode == 0
