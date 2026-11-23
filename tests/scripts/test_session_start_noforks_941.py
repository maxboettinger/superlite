"""#941: session-start runs no child process on a normal start and survives a closed stdout."""
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
INPUT = '{"session_id":"s941","source":"startup"}'
DROP = ("SUPERLITE_FLEET_WORKER", "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_AGENT",
        "CLAUDE_ENV_FILE", "SUPERLITE_HOME", "CLAUDE_PID")


def _env(tmp_path, path=None, **extra):
    env = {k: v for k, v in os.environ.items() if k not in DROP}
    env.update(CLAUDE_PLUGIN_ROOT=str(REPO), HOME=str(tmp_path))
    if path is not None:
        env["PATH"] = path
    env.update(extra)
    return env


def _empty_cwd(tmp_path):
    d = tmp_path / "empty"
    d.mkdir(exist_ok=True)
    return d


def _run(tmp_path, path=None, script=None, cwd=None, **extra):
    return subprocess.run([BASH, script or str(REPO / "hooks" / "session-start")], input=INPUT, text=True,
                          capture_output=True, cwd=cwd or _empty_cwd(tmp_path), env=_env(tmp_path, path, **extra))


def test_empty_path_same_output(tmp_path):
    normal = _run(tmp_path)
    empty = _run(tmp_path, path="")
    assert normal.returncode == 0 and empty.returncode == 0
    assert empty.stdout == normal.stdout
    ctx = json.loads(empty.stdout)["hookSpecificOutput"]["additionalContext"]
    version = json.loads((REPO / "package.json").read_text(encoding="utf-8"))["version"]
    assert "You have superlite" in ctx
    assert "Project state: empty folder." in ctx
    assert f"superlite {version} at {os.path.realpath(REPO)}" in ctx
    assert "Error reading" not in ctx


def test_relative_invocation_gives_physical_root(tmp_path):
    # A run's own .superlite files in the repo would say "run in progress": use a folder with code and a hooks link.
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("x", encoding="utf-8")
    (work / "hooks").symlink_to(REPO / "hooks", target_is_directory=True)
    r = _run(tmp_path, script="hooks/session-start", cwd=work)
    assert r.returncode == 0
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert f"at {os.path.realpath(REPO)}:" in ctx
    assert "Project state: existing code." in ctx


def _closed_stdout(tmp_path, **extra):
    p = subprocess.Popen([BASH, str(REPO / "hooks" / "session-start")], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=_empty_cwd(tmp_path),
                         env=_env(tmp_path, **extra))
    p.stdout.close()
    p.stdin.write(INPUT.encode())
    p.stdin.close()
    err = p.stderr.read()
    rc = p.wait(timeout=30)
    p.stderr.close()
    return rc, err


def test_closed_stdout_exits_0(tmp_path):
    rc, err = _closed_stdout(tmp_path)
    assert rc == 0
    assert err == b""


def test_worker_note_closed_stdout_exits_0(tmp_path):
    rc, err = _closed_stdout(tmp_path, SUPERLITE_FLEET_WORKER="W1", SUPERLITE_FLEET_ROLE="research")
    assert rc == 0
    assert err == b""
