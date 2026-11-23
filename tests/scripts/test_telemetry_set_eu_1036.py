"""hooks/telemetry.sh under a `set -euo pipefail` caller (#1036): session-start stays fail-open."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks"
BASH = shutil.which("bash")
SID = "sess-1036"
DROP = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "SUPERLITE_TELEMETRY", "CLAUDE_ENV_FILE", "CLAUDE_PID",
        "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR", "SL_SD", "SL_TEL_SESSION",
        "SL_TEL_CWD", "SUPERLITE_FLEET_WORKER", "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_AGENT",
        "SUPERLITE_FLEET_PARENT_DIR", "PYTEST_CURRENT_TEST")
# Every public call at the top level of a strict shell: bash 3.2 applies errexit inside a sourced file even where
# the caller's `{ ...; } || true` suppresses it in bash 5, so a top-level `set -e` is the portable stand-in.
CALLS = (r'SL_TEL_SESSION=s1; _sl_tel_on; sl_tel_session_file s1 start; sl_tel_json v ""; '
         r'sl_tel_emit mode "\"mode\":\"regular\""; sl_tel_gate h allow r Bash ls; echo ok')


def env(tmp_path, home=None, **extra):
    e = {k: v for k, v in os.environ.items() if k not in DROP}
    e.update(SUPERLITE_HOME=str(home or tmp_path / "home"), CLAUDECODE="1", **extra)
    return e


def events(tmp_path):
    f = tmp_path / "home" / "events.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def plugin_copy(tmp_path) -> Path:
    """hooks/ and the using-superlite skill, without package.json beside them."""
    plugin = tmp_path / "plugin"
    shutil.copytree(HOOKS, plugin / "hooks")
    skill = plugin / "skills" / "using-superlite"
    skill.mkdir(parents=True)
    shutil.copy(ROOT / "skills" / "using-superlite" / "SKILL.md", skill / "SKILL.md")
    assert not (plugin / "package.json").exists()
    return plugin


def start(tmp_path, plugin, **extra):
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    payload = {"session_id": SID, "source": "startup", "cwd": str(proj)}
    return subprocess.run([BASH, str(plugin / "hooks" / "session-start")], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=proj,
                          env=env(tmp_path, CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(proj), **extra))


def session_line(tmp_path, r):
    assert r.returncode == 0, r.stderr
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "superlite:using-superlite" in ctx
    (line,) = [e for e in events(tmp_path) if e["kind"] == "session_start"]
    assert line["session"] == SID and line["source"] == "startup"
    return line


def test_session_start_without_package_json(tmp_path):
    line = session_line(tmp_path, start(tmp_path, plugin_copy(tmp_path)))
    assert line["version"] is None


def test_session_start_state_dir_without_stable_json(tmp_path):
    sd = tmp_path / "sd"
    sd.mkdir()
    line = session_line(tmp_path, start(tmp_path, ROOT, SUPERLITE_STATE_DIR=str(sd)))
    assert line["run"] is None


@pytest.mark.parametrize("case", ["pkg", "no-pkg", "sd-no-stable", "sd-stable", "home-not-dir"])
def test_library_under_set_euo_pipefail(tmp_path, case):
    lib = (plugin_copy(tmp_path) if case == "no-pkg" else ROOT) / "hooks" / "telemetry.sh"
    extra, home = {}, None
    if case.startswith("sd-"):
        sd = tmp_path / "sd"
        sd.mkdir()
        if case == "sd-stable":
            (sd / "stable.json").write_text('{"run_id": "r-1"}\n')
        extra["SUPERLITE_STATE_DIR"] = str(sd)
    if case == "home-not-dir":
        (tmp_path / "file").write_text("")
        home = tmp_path / "file" / "home"
    r = subprocess.run([BASH, "-c", f"set -euo pipefail; . '{lib}'; {CALLS}"], capture_output=True, text=True,
                       cwd=tmp_path, env=env(tmp_path, home=home, **extra))
    assert (r.returncode, r.stdout, r.stderr) == (0, "ok\n", "")
    got = events(tmp_path)
    if case == "home-not-dir":
        assert got == []
        return
    assert [e["kind"] for e in got] == ["mode", "gate"]
    version = json.loads((ROOT / "package.json").read_text())["version"]
    assert got[0]["version"] == (None if case == "no-pkg" else version)
    assert got[0]["run"] == ("r-1" if case == "sd-stable" else None)
