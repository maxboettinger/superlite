"""#178 (T6 concern): `hooks/superlite-state.sh` resolves the run folder in the same order as `state.resolve()`: the cwd's
linked worktree run (a run marker in its .superlite) before the session's binding, so hooks and `sl` write to one run."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from test_run_scripts import SCRIPTS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

HOOK = SCRIPTS.parents[2] / "hooks" / "superlite-state.sh"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
SID = "hook-order-1"
SNIPPET = r'''input="$1"; . "$2"; superlite_state; printf '%s' "$SL_SD"'''


def world(tmp_path):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    wa = main / ".claude" / "worktrees" / "wa"
    (wa / "src").mkdir(parents=True)
    (wa / ".git").write_text(f"gitdir: {main}/.git/worktrees/wa\n", encoding="utf-8")
    other = tmp_path / "other"
    (other / ".superlite").mkdir(parents=True)
    return main, wa, other


def both(monkeypatch, tmp_path, cwd, bound_to):
    home = tmp_path / "home"
    (home / "sessions").mkdir(parents=True)
    if bound_to is not None:
        (home / "sessions" / SID).write_text(f"{bound_to}\n", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("SUPERLITE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    monkeypatch.chdir(cwd)
    py = state._abs(state.resolve(strict=False))
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(cwd))
    r = subprocess.run([BASH, "-c", SNIPPET, "_", json.dumps({"session_id": SID, "cwd": str(cwd)}), str(HOOK)],
                       capture_output=True, text=True, env=env, cwd=cwd)
    return Path(r.stdout) if r.stdout else None, py


@pytest.mark.parametrize("marker", ["stable.json", "prime.md", "pool.json"])
@pytest.mark.parametrize("sub", ["", "src"])
def test_worktree_run_beats_the_binding(tmp_path, monkeypatch, marker, sub):
    main, wa, other = world(tmp_path)
    (wa / ".superlite").mkdir()
    (wa / ".superlite" / marker).write_text("{}", encoding="utf-8")
    sh, py = both(monkeypatch, tmp_path, wa / sub, other / ".superlite")
    assert py == wa / ".superlite"
    assert sh == py


def test_worktree_without_a_marker_keeps_the_binding(tmp_path, monkeypatch):
    main, wa, other = world(tmp_path)
    (wa / ".superlite").mkdir()
    sh, py = both(monkeypatch, tmp_path, wa, other / ".superlite")
    assert py == other / ".superlite"
    assert sh == py
    with pytest.raises(state.Foreign):
        state.resolve()


def test_main_checkout_marker_does_not_beat_the_binding(tmp_path, monkeypatch):
    main, wa, other = world(tmp_path)
    (main / ".superlite").mkdir()
    (main / ".superlite" / "pool.json").write_text("{}", encoding="utf-8")
    sh, py = both(monkeypatch, tmp_path, main, other / ".superlite")
    assert py == other / ".superlite"
    assert sh == py


def test_no_binding_no_marker_uses_the_launch_folder(tmp_path, monkeypatch):
    main, wa, other = world(tmp_path)
    sh, py = both(monkeypatch, tmp_path, wa, None)
    assert py == wa / ".superlite"
    assert sh == py
