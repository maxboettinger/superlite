"""The Python telemetry writer (#933): line shape, cut, rotation, fail-open, off switches, deferred run end."""
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import telemetry  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in ("SUPERLITE_TELEMETRY", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR",
                "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_WORKER", "CLAUDE_CONFIG_DIR", "SUPERLITE_HARNESS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()


def home() -> Path:
    return Path(os.environ["SUPERLITE_HOME"])


def test_kind_tests_line_shape(tmp_path):
    assert telemetry.emit("tests", mode="fast", passed=3, failed=0, skipped=1, seconds=2.5, task="T2") is True
    (line,) = telemetry.read_events()
    assert telemetry.validate(line) == []
    assert list(line) == list(telemetry.COMMON) + list(telemetry.KINDS["tests"])
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$", line["t"])
    assert line["v"] == 1 and line["kind"] == "tests" and line["harness"] == "claude-code"
    assert line["repo_root"] == str(tmp_path.resolve()) or line["repo_root"] == str(tmp_path)
    assert (line["mode"], line["passed"], line["seconds"], line["task"]) == ("fast", 3, 2.5, "T2")
    assert line["session"] is None and line["run"] is None and line["worker"] is None


def test_kind_gate_cut_to_4096():
    assert telemetry.emit("gate", hook="h", decision="block", rule="r", tool="Bash", target="x" * 10000)
    assert telemetry.emit("gate", hook="h", decision="block", rule="r" * 9000, tool="Bash", target="y" * 200)
    raw = (home() / "events.jsonl").read_bytes().splitlines()
    assert len(raw) == 2
    for r in raw:
        assert len(r) + 1 <= 4096 and r.endswith(b"}")
        assert telemetry.validate(json.loads(r)) == []
    assert len(json.loads(raw[0])["target"]) == 200


def test_unknown_kind_and_extra_keys():
    assert telemetry.emit("nope", x=1) is False
    assert not (home() / "events.jsonl").exists()
    assert telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1", stray="no")
    (line,) = telemetry.read_events()
    assert "stray" not in line


def test_validate_missing_field():
    telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    (line,) = telemetry.read_events()
    del line["task"]
    assert telemetry.validate(line) == ["tests: missing task"]


def test_dispatch_writer_role_from_env(monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_ROLE", "lead")
    assert telemetry.emit("dispatch", task="T1", role="implementer")
    (line,) = telemetry.read_events()
    assert line["role"] == "implementer" and line["writer_role"] == "lead"
    assert list(line)[-1] == "writer_role" and telemetry.validate(line) == []


def test_rotation_keeps_five(monkeypatch):
    monkeypatch.setattr(telemetry, "MAX_BYTES", 100)
    for _ in range(8):
        assert telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    names = sorted(p.name for p in home().glob("events.jsonl*"))
    assert names == ["events.jsonl", "events.jsonl.1", "events.jsonl.2", "events.jsonl.3", "events.jsonl.4",
                     "events.jsonl.5"]


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions and a non-root user")
def test_read_only_home_fails_open(capfd):
    home().mkdir(parents=True)
    home().chmod(0o500)
    try:
        assert telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1") is False
    finally:
        home().chmod(0o700)
    assert capfd.readouterr().err == ""


def test_off_switches(monkeypatch):
    assert telemetry.events_path() == home() / "events.jsonl"
    monkeypatch.setenv("SUPERLITE_TELEMETRY", "0")
    assert telemetry.events_path() is None
    assert telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1") is False
    monkeypatch.delenv("SUPERLITE_TELEMETRY")
    home().mkdir(parents=True, exist_ok=True)
    (home() / "telemetry-off").write_text("")
    assert telemetry.events_path() is None
    (home() / "telemetry-off").unlink()
    monkeypatch.delenv("SUPERLITE_HOME")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    assert telemetry.events_path() is None


def test_run_id_from_stable_json(tmp_path, monkeypatch):
    sd = tmp_path / "p" / ".superlite"
    sd.mkdir(parents=True)
    (sd / "stable.json").write_text(json.dumps({"run_id": "20261116T130500Z-a1b2c3"}))
    assert telemetry.run_id(sd) == "20261116T130500Z-a1b2c3"
    assert telemetry.run_id(None) is None
    assert telemetry.run_id(tmp_path / "missing") is None
    telemetry.emit("tests", sd=sd, mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    assert telemetry.read_events()[0]["run"] == "20261116T130500Z-a1b2c3"
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(sd))
    telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    assert telemetry.read_events()[1]["run"] == "20261116T130500Z-a1b2c3"


def test_new_run_id():
    rid = telemetry.new_run_id(datetime(2026, 11, 16, 13, 5, 0, tzinfo=timezone.utc))
    assert re.fullmatch(r"20261116T130500Z-[0-9a-f]{6}", rid)


def test_session_mode_reads_file(monkeypatch):
    d = home() / "telemetry" / "sessions"
    d.mkdir(parents=True)
    (d / "s1.mode").write_text("feature\n")
    assert telemetry.session_mode("s1") == "feature"
    assert telemetry.session_mode("s2") is None
    assert telemetry.session_mode(None) is None
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    assert telemetry.session_mode() == "feature"


def test_session_mode_rejects_bad_id():
    (home() / "telemetry").mkdir(parents=True)
    (home() / "telemetry" / "x.mode").write_text("regular")
    assert telemetry.session_mode("../x") is None
    assert telemetry.session_mode("a/b") is None
    assert telemetry.session_mode("") is None


def test_session_from_env_and_param(monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "fallback")
    telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "primary")
    telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    telemetry.emit("tests", session="given", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    assert [e["session"] for e in telemetry.read_events()] == ["fallback", "primary", "given"]


def test_read_events_skips_bad_lines():
    assert telemetry.read_events() == []
    telemetry.emit("tests", mode="fast", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    with open(home() / "events.jsonl", "a") as f:
        f.write("not json\n[1]\n")
    assert len(telemetry.read_events()) == 1


def test_count_reads_current_and_first_rotation():
    for i in range(3):
        telemetry.emit("tests", mode="fast", passed=i, failed=0, skipped=0, seconds=1, task="T1")
    telemetry.emit("tests", mode="full", passed=1, failed=0, skipped=0, seconds=1, task="T1")
    p = home() / "events.jsonl"
    p.rename(home() / "events.jsonl.1")
    telemetry.emit("tests", mode="fast", passed=9, failed=0, skipped=0, seconds=1, task="T1")
    assert telemetry.count("tests", None) == 5
    assert telemetry.count("tests", None, mode="fast") == 4
    assert telemetry.count("tests", "other") == 0
    assert telemetry.count("gate", None) == 0


def test_batch_key_uses_main_repository_name(tmp_path):
    main = tmp_path / "superlite"
    (main / ".git" / "worktrees" / "b233").mkdir(parents=True)
    wt = main / ".claude" / "worktrees" / "b233"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'b233'}\n")
    assert telemetry.batch_key(wt, "B233") == "superlite-B233"


def _run_ends():
    return [e for e in telemetry.read_events() if e["kind"] == "run_end"]


FIELDS = {"wall_s": 10, "cost_usd": 1.5, "tasks": 3}


def test_kind_run_end_deferred_either_order():
    assert telemetry.defer_run_end("k1", dict(FIELDS, outcome="done"))
    assert _run_ends() == []
    assert telemetry.finish_deferred("k1", "shipped") is True
    (line,) = _run_ends()
    assert telemetry.validate(line) == []
    assert line["outcome"] == "shipped" and line["wall_s"] == 10 and line["tasks"] == 3
    assert telemetry.finish_deferred("k1", "shipped") is not None  # a second finish never writes a line
    assert len(_run_ends()) == 1

    assert telemetry.finish_deferred("k2", "parked", "why") is True
    assert _run_ends()[1:] == []
    assert telemetry.defer_run_end("k2", dict(FIELDS)) is True
    ends = _run_ends()
    assert len(ends) == 2 and ends[1]["outcome"] == "parked" and ends[1]["reason"] == "why"
    assert telemetry.validate(ends[1]) == []


def test_deferred_unsafe_key_is_refused():
    assert telemetry.defer_run_end("../x", dict(FIELDS)) is False
    assert telemetry.finish_deferred("a/b", "done") is False


def test_cli_export_bad_date_exits_2():
    r = subprocess.run([sys.executable, str(SCRIPTS / "telemetry.py"), "export", "--since", "nope"],
                       capture_output=True, text=True, env=dict(os.environ))
    assert r.returncode == 2


def test_cli_agent_stop_fails_open_silently(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "telemetry.py"), "agent-stop", "--transcript",
                        str(tmp_path / "none.jsonl"), "--agent-type", "superlite:implementer"],
                       capture_output=True, text=True, env=dict(os.environ))
    assert r.returncode == 0 and r.stderr == ""


def test_session_and_key_ids_reject_trailing_newline():
    (home() / "telemetry" / "sessions").mkdir(parents=True)
    (home() / "telemetry" / "sessions" / "s1\n.mode").write_text("feature")
    assert telemetry.session_mode("s1\n") is None
    assert telemetry.defer_run_end("k\n", dict(FIELDS)) is False
    assert telemetry.finish_deferred("k\n", "done") is False
