import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
HOOK = ROOT / "hooks" / "pre-compact"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")

sys.path.insert(0, str(SCRIPTS))

_DROPPED = ("SUPERLITE_STATE_DIR", "CLAUDE_PLUGIN_ROOT", "SUPERLITE_NO_AUTOCOMPACT", "SUPERLITE_FLEET_WORKER",
            "SUPERLITE_FLEET_ROLE", "SUPERLITE_PYTHON")


def _run_dir(tmp_path, marker="orchestrator.json"):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    if marker:
        (sl / marker).write_text("{}", encoding="utf-8")
    return sl


def _run(tmp_path, trigger="auto", **extra):
    env = {k: v for k, v in os.environ.items() if k not in _DROPPED}
    env.update({"CLAUDE_PROJECT_DIR": str(tmp_path), "SUPERLITE_HOME": str(tmp_path / "home")})
    env.update(extra)
    inp = json.dumps({"session_id": "s1", "hook_event_name": "PreCompact", "trigger": trigger,
                      "custom_instructions": None})
    return subprocess.run([BASH, str(HOOK)], input=inp, capture_output=True, text=True, encoding="utf-8",
                          env=env, cwd=str(tmp_path))


def test_prints_instructions_for_a_run(tmp_path):
    _run_dir(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "standing instruction" in r.stdout
    assert "next step" in r.stdout


def test_output_is_plain_text_under_the_cap(tmp_path):
    _run_dir(tmp_path)
    out = _run(tmp_path).stdout
    assert not out.lstrip().startswith("{")   # PreCompact stdout is read as plain instructions
    assert 200 < len(out) < 2000              # Claude Code cuts PreCompact output at 10,000 characters


def test_manual_compact_gets_the_same_text(tmp_path):
    _run_dir(tmp_path)
    assert _run(tmp_path, trigger="manual").stdout == _run(tmp_path, trigger="auto").stdout


@pytest.mark.parametrize("marker", ["orchestrator.json", "backlog.json", "stable.json", "prime.md", "pool.json",
                                    "inline-flow.json"])
def test_each_run_marker_counts(tmp_path, marker):
    _run_dir(tmp_path, marker)
    assert _run(tmp_path).stdout != ""


def test_silent_without_state_folder(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_silent_when_folder_holds_no_run(tmp_path):
    _run_dir(tmp_path, "test-summary.json")
    r = _run(tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_silent_with_opt_out(tmp_path):
    _run_dir(tmp_path)
    r = _run(tmp_path, SUPERLITE_NO_AUTOCOMPACT="1")
    assert r.returncode == 0 and r.stdout == ""


def test_silent_for_fleet_worker(tmp_path):
    _run_dir(tmp_path)
    r = _run(tmp_path, SUPERLITE_FLEET_WORKER="W3", SUPERLITE_FLEET_ROLE="implementer")
    assert r.returncode == 0 and r.stdout == ""


def test_batch_lead_gets_instructions(tmp_path):
    _run_dir(tmp_path)
    r = _run(tmp_path, SUPERLITE_FLEET_WORKER="W3", SUPERLITE_FLEET_ROLE="lead")
    assert "next step" in r.stdout


def test_fails_open_without_python(tmp_path):
    _run_dir(tmp_path)
    r = _run(tmp_path, SUPERLITE_PYTHON=str(tmp_path / "no-such-python"))
    assert r.returncode == 0 and r.stdout == ""


def test_hooks_json_registers_pre_compact_for_auto_and_manual():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    groups = data["PreCompact"]
    assert [h["command"] for g in groups for h in g["hooks"]] == ['bash "${CLAUDE_PLUGIN_ROOT}/hooks/pre-compact"']
    assert all("matcher" not in g for g in groups)   # no matcher: both triggers


def test_instructions_name_what_to_keep_and_drop():
    import compact_text
    text = compact_text.instructions()
    for needle in ("standing instruction", "Decisions", "In flight", "next step", "Drop:"):
        assert needle in text
    assert "\r" not in text
