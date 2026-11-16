"""The bash telemetry writer hooks/telemetry.sh (#933): same line shape as the Python writer, fail open."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetry  # noqa: E402

LIB = ROOT / "hooks" / "telemetry.sh"
BASH = shutil.which("bash")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in ("SUPERLITE_TELEMETRY", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR",
                "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_WORKER", "CLAUDE_CONFIG_DIR", "SUPERLITE_HARNESS",
                "SL_SD", "SL_TEL_SESSION", "SL_TEL_CWD", "PYTEST_CURRENT_TEST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()


def home() -> Path:
    return Path(os.environ["SUPERLITE_HOME"])


def sh(script, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    e.update(env)
    return subprocess.run([BASH, "-c", f". '{LIB}'; {script}"], capture_output=True, text=True, env=e)


def test_bash_json_helper():
    r = sh("""sl_tel_json V 'a"b\\c'; echo "$V"; sl_tel_json V ''; echo "$V"; sl_tel_json V abcdefgh 3; echo "$V\"""")
    assert r.returncode == 0
    assert r.stdout.splitlines() == ['"a\\"b\\\\c"', "null", '"abc"']


def test_kind_gate_bash_example():
    r = sh("SL_TEL_SESSION=s1 SL_TEL_CWD=/tmp/p; sl_tel_gate block-unsafe-kill block kill-pattern Bash 'pkill -f node'")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (line,) = telemetry.read_events()
    assert telemetry.validate(line) == []
    assert line["v"] == 1 and line["kind"] == "gate" and line["session"] == "s1" and line["harness"] == "claude-code"
    assert (line["hook"], line["decision"], line["rule"], line["tool"], line["target"]) == (
        "block-unsafe-kill", "block", "kill-pattern", "Bash", "pkill -f node")
    assert line["version"] == json.loads((ROOT / "package.json").read_text())["version"]


def test_kind_mode_bash_fragment():
    r = sh("""sl_tel_json M feature; sl_tel_emit mode "\\"mode\\":$M\"""", CLAUDE_CODE_SESSION_ID="abc")
    assert r.returncode == 0
    (line,) = telemetry.read_events()
    assert telemetry.validate(line) == []
    assert line["mode"] == "feature" and line["session"] == "abc"


def test_bash_escapes_quotes_backslash_newline():
    target = 'a"b\\c\nd\te'
    r = sh('sl_tel_gate h block r Bash "$T"', T=target)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    raw = (home() / "events.jsonl").read_text().splitlines()
    assert len(raw) == 1
    line = json.loads(raw[0])
    assert telemetry.validate(line) == []
    assert line["target"] == 'a"b\\c d e'


def test_bash_target_cut_and_line_cap():
    sh('sl_tel_gate h block r Bash "$T"', T="x" * 1000)
    (line,) = telemetry.read_events()
    assert len(line["target"]) == 200
    assert len((home() / "events.jsonl").read_bytes()) <= 4096


def test_bash_line_matches_python_keys(tmp_path):
    sh("sl_tel_gate h block r Bash t")
    assert telemetry.emit("gate", hook="h", decision="block", rule="r", tool="Bash", target="t")
    a, b = telemetry.read_events()
    assert list(a) == list(b)
    assert telemetry.validate(a) == [] and telemetry.validate(b) == []
    assert a["repo_root"] == b["repo_root"] or Path(a["repo_root"]).resolve() == Path(b["repo_root"]).resolve()


def test_bash_read_only_home_silent(tmp_path):
    h = tmp_path / "ro"
    h.mkdir()
    h.chmod(0o500)
    try:
        r = sh("sl_tel_gate h block r Bash t; sl_tel_emit mode '\"mode\":\"x\"'; echo done", SUPERLITE_HOME=str(h))
    finally:
        h.chmod(0o700)
    assert r.returncode == 0 and r.stdout == "done\n" and r.stderr == ""
    assert list(h.iterdir()) == []


def test_bash_off_switches(tmp_path):
    sh("sl_tel_gate h block r Bash t", SUPERLITE_TELEMETRY="0")
    assert not (home() / "events.jsonl").exists()
    home().mkdir(parents=True, exist_ok=True)
    (home() / "telemetry-off").write_text("")
    sh("sl_tel_gate h block r Bash t")
    assert not (home() / "events.jsonl").exists()
    (home() / "telemetry-off").unlink()
    e = {k: v for k, v in os.environ.items() if k != "SUPERLITE_HOME"}
    e["PYTEST_CURRENT_TEST"] = "x"
    e["HOME"] = str(tmp_path / "fakehome")
    subprocess.run([BASH, "-c", f". '{LIB}'; sl_tel_gate h block r Bash t"], env=e, capture_output=True)
    assert not (tmp_path / "fakehome").exists()
    assert sh("sl_tel_gate h block r Bash t").returncode == 0
    assert len(telemetry.read_events()) == 1


def test_bash_run_from_sl_sd(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "stable.json").write_text('{"x": 1, "run_id" : "R1"}')
    sh("sl_tel_gate h block r Bash t", SL_SD=str(sd))
    sh("sl_tel_gate h block r Bash t")
    a, b = telemetry.read_events()
    assert a["run"] == "R1" and b["run"] is None


def test_bash_session_and_fleet_context(tmp_path):
    sh("sl_tel_gate h block r Bash t", SUPERLITE_SESSION_ID="s2", SUPERLITE_FLEET_WORKER="W1",
       SUPERLITE_FLEET_ROLE="implementer", SL_TEL_CWD=str(tmp_path / "sub"))
    (line,) = telemetry.read_events()
    assert (line["session"], line["worker"], line["role"]) == ("s2", "W1", "implementer")
    assert line["repo_root"] == str(tmp_path)


def test_bash_session_file():
    r = sh("sl_tel_session_file s-1_A start; echo \"rc=$?\"; sl_tel_session_file '../x' start; echo \"rc=$?\"; "
           "sl_tel_session_file '' mode; echo \"rc=$?\"")
    out = r.stdout.splitlines()
    assert out[0].endswith("/telemetry/sessions/s-1_A.start") and out[0].startswith(str(home()))
    assert out[1:] == ["rc=0", "rc=1", "rc=1"]


def test_bash_timestamp_fallback_without_epochrealtime():
    r = sh("unset EPOCHREALTIME; sl_tel_gate h block r Bash t; EPOCHREALTIME=; sl_tel_gate h block r Bash t")
    assert r.returncode == 0
    lines = telemetry.read_events()
    assert len(lines) == 2 and all(telemetry.validate(x) == [] for x in lines)


def test_bash32_lint_passes():
    from test_hooks_bash32 import offences
    text = LIB.read_text(encoding="utf-8")
    assert offences(text) == []
    assert b"\r" not in LIB.read_bytes()
    assert subprocess.run([BASH, "-n", str(LIB)]).returncode == 0
