import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
HOOK = ROOT / "hooks" / "compact-nudge"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")

sys.path.insert(0, str(SCRIPTS))
import compact_due  # noqa: E402

MODE_FILE = "orchestrator" + ".json"
_DROPPED = ("SUPERLITE_STATE_DIR", "CLAUDE_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT", "CURSOR_AGENT", "CURSOR_TRACE_ID",
            "SUPERLITE_NO_AUTOCOMPACT", "COPILOT_CLI", "MUSE_PLUGIN_ROOT", "SUPERLITE_FLEET_WORKER",
            "SUPERLITE_FLEET_ROLE", "SUPERLITE_PYTHON")


def _entry(tokens, sidechain=False):
    usage = {"input_tokens": 2, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": tokens - 1002,
             "output_tokens": 70000}
    return json.dumps({"type": "assistant", "isSidechain": sidechain, "message": {"role": "assistant", "usage": usage}})


def _transcript(tmp_path, *lines):
    p = tmp_path / "transcript.jsonl"
    p.write_text("".join(ln + "\n" for ln in lines), encoding="utf-8")
    return p


def _sl(tmp_path, run=True):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    if run:
        (sl / MODE_FILE).write_text("{}", encoding="utf-8")
    return sl


def _run(tmp_path, transcript=None, sid="s1", **extra):
    env = {k: v for k, v in os.environ.items() if k not in _DROPPED}
    env.update({"CLAUDE_PROJECT_DIR": str(tmp_path), "SUPERLITE_HOME": str(tmp_path / "home")})
    env.update(extra)
    inp = {"hook_event_name": "UserPromptSubmit", "prompt": "go on"}
    if sid:
        inp["session_id"] = sid
    if transcript is not None:
        inp["transcript_path"] = str(transcript)
    return subprocess.run([BASH, str(HOOK)], input=json.dumps(inp), capture_output=True, text=True, encoding="utf-8",
                          env=env, cwd=str(tmp_path))


# --- context_tokens: the size of the last main-conversation request -------------------------------------------------

def test_context_tokens_sums_the_input_side_of_the_last_request(tmp_path):
    t = _transcript(tmp_path, _entry(120000), json.dumps({"type": "user", "message": {"content": "x"}}), _entry(612345))
    assert compact_due.context_tokens(str(t)) == 612345      # output tokens are not context


def test_context_tokens_skips_subagent_requests(tmp_path):
    t = _transcript(tmp_path, _entry(300000), _entry(900000, sidechain=True))
    assert compact_due.context_tokens(str(t)) == 300000


def test_context_tokens_reads_only_the_tail(tmp_path):
    big = json.dumps({"type": "user", "message": {"content": "y" * 400000}})
    t = _transcript(tmp_path, _entry(900000), big, _entry(250000))
    assert compact_due.context_tokens(str(t)) == 250000
    assert compact_due.context_tokens(str(_transcript(tmp_path, _entry(900000), big))) is None   # outside the tail


def test_context_tokens_tolerates_bad_input(tmp_path):
    assert compact_due.context_tokens(str(tmp_path / "missing.jsonl")) is None
    assert compact_due.context_tokens("") is None
    t = _transcript(tmp_path, "{not json", json.dumps({"type": "assistant", "message": {"usage": "x"}}), "[1, 2]")
    assert compact_due.context_tokens(str(t)) is None


# --- is_due: over the threshold, once per session -------------------------------------------------------------------

def test_due_only_above_the_threshold(tmp_path):
    sl = _sl(tmp_path)
    assert compact_due.is_due(str(sl), 500000, "s1") is False
    assert compact_due.is_due(str(sl), 500001, "s1") is True
    assert compact_due.is_due(str(sl), None, "s1") is False


def test_not_due_again_once_marked(tmp_path):
    sl = _sl(tmp_path)
    compact_due.mark(str(sl), "s1")
    assert compact_due.is_due(str(sl), 900000, "s1") is False
    assert compact_due.is_due(str(sl), 900000, "s2") is True   # another session has its own hint


def test_unsafe_sid_writes_no_odd_marker(tmp_path):
    sl = _sl(tmp_path)
    compact_due.mark(str(sl), "../../x/y")
    assert [p.name for p in tmp_path.iterdir()] == [".superlite"]
    assert all(p.name.startswith(("compact-hint", MODE_FILE)) for p in sl.iterdir())


def test_nudge_line_names_the_size_and_the_fix():
    line = compact_due.nudge_line(612345)
    assert "612k" in line and "/autocompact 400k" in line and "sl setup" in line


# --- the hook --------------------------------------------------------------------------------------------------------

def test_hook_hints_once_per_session(tmp_path):
    _sl(tmp_path)
    t = _transcript(tmp_path, _entry(650000))
    first = _run(tmp_path, t)
    assert first.returncode == 0 and "/autocompact 400k" in first.stdout
    second = _run(tmp_path, t)
    assert second.returncode == 0 and second.stdout == ""
    assert "/autocompact 400k" in _run(tmp_path, t, sid="s2").stdout


def test_hook_claude_output_shape(tmp_path):
    _sl(tmp_path)
    r = _run(tmp_path, _transcript(tmp_path, _entry(650000)), CLAUDE_PLUGIN_ROOT=str(ROOT))
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "650k" in out["hookSpecificOutput"]["additionalContext"]


def test_hook_silent_below_the_threshold(tmp_path):
    _sl(tmp_path)
    r = _run(tmp_path, _transcript(tmp_path, _entry(400000)))
    assert r.returncode == 0 and r.stdout == ""
    assert not list((tmp_path / ".superlite").glob("compact-hint*"))   # still armed for later


def test_hook_silent_without_a_run(tmp_path):
    t = _transcript(tmp_path, _entry(650000))
    assert _run(tmp_path, t).stdout == ""                 # no state folder
    _sl(tmp_path, run=False)
    assert _run(tmp_path, t).stdout == ""                 # a folder without a run


def test_hook_silent_with_opt_out(tmp_path):
    _sl(tmp_path)
    r = _run(tmp_path, _transcript(tmp_path, _entry(650000)), SUPERLITE_NO_AUTOCOMPACT="1")
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


def test_hook_silent_for_workers_and_leads(tmp_path):
    _sl(tmp_path)
    t = _transcript(tmp_path, _entry(650000))
    for role in ("implementer", "lead"):                   # nobody reads a hint for the user there
        r = _run(tmp_path, t, SUPERLITE_FLEET_WORKER="W1", SUPERLITE_FLEET_ROLE=role)
        assert r.returncode == 0 and r.stdout == ""


def test_hook_silent_without_a_readable_transcript(tmp_path):
    _sl(tmp_path)
    assert _run(tmp_path, None).stdout == ""
    assert _run(tmp_path, tmp_path / "missing.jsonl").stdout == ""
    assert _run(tmp_path, _transcript(tmp_path, "{garbage")).stdout == ""


def test_hook_fails_open_without_python(tmp_path):
    _sl(tmp_path)
    r = _run(tmp_path, _transcript(tmp_path, _entry(650000)), SUPERLITE_PYTHON=str(tmp_path / "no-such-python"))
    assert r.returncode == 0 and r.stdout == ""
