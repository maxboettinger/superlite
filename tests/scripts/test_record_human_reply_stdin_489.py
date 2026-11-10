"""#489: record-human-reply never waits on stdin: a terminal, a silent open pipe and an endless one all end."""
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPLY = ROOT / "hooks" / "record-human-reply"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    sd = tmp_path / "proj" / ".superlite"
    sd.mkdir(parents=True)
    (sd / "orchestrator.json").write_text(json.dumps({"mode": "human", "approved": False}))
    return tmp_path / "proj"


def env_for(proj, tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(CLAUDE_PROJECT_DIR=str(proj), SUPERLITE_HOME=str(tmp_path / "home"))
    return env


def jsonl(proj):
    return proj / ".superlite" / "human-replies.jsonl"


def test_open_silent_stdin_exits(proj, tmp_path):
    p = subprocess.Popen([BASH, str(REPLY)], stdin=subprocess.PIPE, env=env_for(proj, tmp_path))
    try:
        assert p.wait(timeout=15) == 0
    finally:
        p.kill()
        p.stdin.close()
    assert not jsonl(proj).exists()


def test_endless_stdin_exits(proj, tmp_path):
    p = subprocess.Popen([BASH, str(REPLY)], stdin=subprocess.PIPE, env=env_for(proj, tmp_path))
    stop = threading.Event()

    def feed():
        try:
            while not stop.is_set():
                p.stdin.write(b"y" * 65536)
                p.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    t = threading.Thread(target=feed, daemon=True)
    t.start()
    try:
        assert p.wait(timeout=20) == 0
    finally:
        stop.set()
        p.kill()
        t.join(timeout=5)


@pytest.mark.skipif(os.name == "nt", reason="pty is POSIX only")
def test_tty_stdin_exits_at_once(proj, tmp_path):
    import pty
    master, slave = pty.openpty()
    try:
        p = subprocess.Popen([BASH, str(REPLY)], stdin=slave, env=env_for(proj, tmp_path))
        try:
            assert p.wait(timeout=3) == 0
        finally:
            p.kill()
    finally:
        os.close(master)
        os.close(slave)
    assert not jsonl(proj).exists()


def test_prompt_still_recorded(proj, tmp_path):
    t0 = time.time()
    r = subprocess.run([BASH, str(REPLY)], input=json.dumps({"session_id": "s1", "prompt": "approve"}),
                       text=True, env=env_for(proj, tmp_path), timeout=15)
    assert r.returncode == 0 and time.time() - t0 < 3
    last = jsonl(proj).read_text().splitlines()[-1]
    assert '"approves":true' in last and '"text":"approve"' in last


def test_oversize_input_cut(proj, tmp_path):
    big = json.dumps({"prompt": "a" * 2_000_000})
    r = subprocess.run([BASH, str(REPLY)], input=big, text=True, env=env_for(proj, tmp_path), timeout=20)
    assert r.returncode == 0
