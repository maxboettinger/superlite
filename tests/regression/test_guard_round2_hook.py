"""Guard round 2 (hook side): Write through symlinks and hard links, a planted Python cache, idle `.superlite` mentions."""
import json
import os
import shutil
import stat
import subprocess
import sys

import pytest

from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "block-coordinator-edits"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"
    for d in (".superlite", "docs", "src"):
        (p / d).mkdir(parents=True)
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / ".superlite" / "orchestrator.json").write_text("{}")
    (p / "src" / "app.py").write_text("x = 1\n")
    (p / "docs" / "b.md").write_text("b\n")
    (tmp_path / "home").mkdir()
    return p


def go(proj, tool, tool_input, **env):
    raw = json.dumps({"tool_name": tool, "tool_input": tool_input})
    e = {k: v for k, v in os.environ.items() if k not in ("SUPERLITE_CACHE_DIR", "XDG_CACHE_HOME", "SUPERLITE_PYTHON")}
    e.update({"CLAUDE_PROJECT_DIR": str(proj), "HOME": str(proj.parent / "home"), **env})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e, cwd=str(proj))


def write(proj, rel, **env):
    return go(proj, "Write", {"file_path": str(proj / rel)}, **env)


def sh(proj, cmd, **env):
    return go(proj, "Bash", {"command": cmd}, **env)


def cache_dir(proj):
    return proj.parent / "home" / ".cache" / "superlite"


# --- 1. symlinks and hard links inside an allowed folder ---------------------------------------------------------

@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_write_through_symlink_to_code_blocks(proj):
    os.symlink("../src/app.py", proj / "docs" / "link.md")
    assert write(proj, "docs/link.md").returncode == 2


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_write_through_symlink_outside_the_project_blocks(proj):
    (proj.parent / "outside.txt").write_text("o")
    os.symlink(str(proj.parent / "outside.txt"), proj / "docs" / "out.md")
    assert write(proj, "docs/out.md").returncode == 2


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_write_below_a_symlinked_folder_blocks(proj):
    os.symlink("../src", proj / "docs" / "plans")
    assert write(proj, "docs/plans/new.md").returncode == 2


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_symlink_to_a_protected_file_blocks(proj):
    os.symlink("orchestrator.json", proj / ".superlite" / "o.md")
    r = write(proj, ".superlite/o.md")
    assert r.returncode == 2 and "orchestrator.json" in r.stderr


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_symlink_to_an_allowed_file_passes(proj):
    os.symlink("b.md", proj / "docs" / "alias.md")
    assert write(proj, "docs/alias.md").returncode == 0
    assert write(proj, "docs/new.md").returncode == 0


def test_hard_link_to_code_blocks(proj):
    os.link(proj / "src" / "app.py", proj / "docs" / "h.md")
    assert write(proj, "docs/h.md").returncode == 2
    assert write(proj, "docs/b.md").returncode == 0


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_idle_does_not_judge_links(proj):
    (proj / ".superlite" / "pool.json").unlink()
    os.symlink("../src/app.py", proj / "docs" / "link.md")
    assert write(proj, "docs/link.md").returncode == 0


# --- 2. the Python cache -------------------------------------------------------------------------------------

def test_write_to_the_cache_blocks_in_every_state(proj):
    path = cache_dir(proj) / "python"
    for active in (True, False):
        pool = proj / ".superlite" / "pool.json"
        pool.write_text("{}") if active else (pool.unlink() if pool.exists() else None)
        r = go(proj, "Write", {"file_path": str(path)})
        assert r.returncode == 2, active
        r = go(proj, "Write", {"file_path": str(cache_dir(proj) / ".." / "superlite" / "python")})
        assert r.returncode == 2, active


@pytest.fixture
def fake_cache(proj, tmp_path):
    fake = tmp_path / "fakepy"
    fake.write_text('#!/bin/sh\necho "guard: ok $SUPERLITE_GUARD_NONCE"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    d = cache_dir(proj)
    d.mkdir(parents=True)
    key = f"{os.environ['PATH']}|{proj}|{os.environ.get('VIRTUAL_ENV', '')}"
    (d / "python").write_text(f"{fake}\n{key}\n")
    return d


def test_a_planted_cache_is_not_trusted(proj, fake_cache):
    r = sh(proj, "echo x > src/app.py")
    assert r.returncode == 2, r.stderr


def test_a_cache_naming_the_real_python_still_serves(proj, tmp_path):
    d = cache_dir(proj)
    d.mkdir(parents=True)
    key = f"{os.environ['PATH']}|{proj}|{os.environ.get('VIRTUAL_ENV', '')}"
    (d / "python").write_text(f"{sys.executable}\n{key}\n")
    assert sh(proj, "echo x > src/app.py").returncode == 2
    assert sh(proj, "echo x > docs/a.md").returncode == 0


# --- 3. idle commands that must reach the judge -------------------------------------------------------------

@pytest.fixture
def spy(proj, tmp_path):
    log = tmp_path / "spawned"
    s = tmp_path / "spy.sh"
    s.write_text(f'#!/bin/sh\necho x >> "{log}"\nexec "{sys.executable}" "$@"\n')
    s.chmod(s.stat().st_mode | stat.S_IEXEC)
    (proj / ".superlite" / "pool.json").unlink()   # idle
    return s, log


@pytest.mark.parametrize("cmd", [
    "rsync -a /tmp/p/ .superlite/",
    "cp -r /tmp/p/. .superlite/",
    "cd CACHE && echo /tmp/fakepy > python",
    "echo /tmp/fakepy > ~/.cache/superlite/python",
])
def test_idle_command_reaches_the_judge(proj, spy, cmd):
    s, log = spy
    sh(proj, cmd.replace("CACHE", str(cache_dir(proj))), SUPERLITE_PYTHON=str(s))
    assert log.exists(), cmd


@pytest.mark.parametrize("cmd", ["echo hello", "ls -la src", "cd /tmp && python3 x.py"])
def test_idle_plain_command_spawns_nothing(proj, spy, cmd):
    s, log = spy
    assert sh(proj, cmd, SUPERLITE_PYTHON=str(s)).returncode == 0
    assert not log.exists(), cmd
