import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "session-start"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


def test_session_start_emits_skill_text_verbatim():
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT))
    r = subprocess.run([BASH, str(HOOK)], input="", capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    skill = (ROOT / "skills" / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.replace("\r", "").rstrip("\n") in ctx   # newlines, quotes, backslashes survive
    assert "\r" not in ctx


def run_hook(cwd, stdin="", **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("SUPERLITE_STATE_DIR", "CLAUDE_ENV_FILE")}
    env.update(CLAUDE_PLUGIN_ROOT=str(ROOT), SUPERLITE_HOME=str(cwd / "home"), CLAUDE_PROJECT_DIR=str(cwd), **extra)
    r = subprocess.run([BASH, str(HOOK)], input=stdin, capture_output=True, text=True, encoding="utf-8",
                       cwd=cwd, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_marker_means_run_in_progress(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "stable.json").write_text("{}", encoding="utf-8")
    assert "Project state: run in progress" in run_hook(tmp_path)


def test_orchestrator_file_alone_is_existing_code(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "orchestrator.json").write_text("{}", encoding="utf-8")
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    assert "Project state: existing code" in run_hook(tmp_path)


def test_empty_folder(tmp_path):
    assert "Project state: empty folder" in run_hook(tmp_path)


def test_compact_source_writes_no_stamp(tmp_path):
    stdin = json.dumps({"session_id": "s1", "source": "compact"})
    run_hook(tmp_path, stdin)
    assert not (tmp_path / ".superlite").exists()
    (tmp_path / ".superlite").mkdir()
    run_hook(tmp_path, stdin)
    assert list((tmp_path / ".superlite").iterdir()) == []   # the 30-minute nudge and its stamp are gone


MODE_FILE = "orchestrator" + ".json"
COMPACT = json.dumps({"session_id": "s1", "source": "compact"})


def _run_dir(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / MODE_FILE).write_text(
        json.dumps({"mode": "ai", "time": "2026-11-10T10:00:00", "by": "user"}), encoding="utf-8")


def test_compact_source_adds_continuation_and_state_for_a_run(tmp_path):
    _run_dir(tmp_path)
    ctx = run_hook(tmp_path, COMPACT)
    assert "compacted automatically" in ctx
    assert "orchestrator: AI" in ctx
    skill = (ROOT / "skills" / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.replace("\r", "").rstrip("\n") in ctx          # the bootstrap text stays
    assert ctx.index("compacted automatically") > ctx.index("Project state:")   # and comes first


def test_compact_source_without_a_run_adds_nothing(tmp_path):
    (tmp_path / ".superlite").mkdir()
    assert "compacted automatically" not in run_hook(tmp_path, COMPACT)


def test_startup_and_clear_get_no_continuation(tmp_path):
    _run_dir(tmp_path)
    for source in ("startup", "clear"):
        ctx = run_hook(tmp_path, json.dumps({"session_id": "s1", "source": source}))
        assert "compacted automatically" not in ctx


def test_compact_continuation_respects_opt_out(tmp_path):
    _run_dir(tmp_path)
    assert "compacted automatically" not in run_hook(tmp_path, COMPACT, SUPERLITE_NO_AUTOCOMPACT="1")


def test_compact_worker_keeps_its_short_note(tmp_path):
    _run_dir(tmp_path)
    ctx = run_hook(tmp_path, COMPACT, SUPERLITE_FLEET_WORKER="W2", SUPERLITE_FLEET_ROLE="implementer")
    assert ctx.startswith("You are superlite fleet worker W2") and "compacted automatically" not in ctx


def test_compact_batch_lead_gets_the_continuation(tmp_path):
    _run_dir(tmp_path)
    ctx = run_hook(tmp_path, COMPACT, SUPERLITE_FLEET_WORKER="W4", SUPERLITE_FLEET_ROLE="lead")
    assert ctx.startswith("You are superlite batch lead W4") and "compacted automatically" in ctx


def test_compact_continuation_survives_a_missing_python(tmp_path):
    _run_dir(tmp_path)
    ctx = run_hook(tmp_path, COMPACT, SUPERLITE_PYTHON=str(tmp_path / "no-such-python"))
    assert "Project state:" in ctx and "compacted automatically" not in ctx
