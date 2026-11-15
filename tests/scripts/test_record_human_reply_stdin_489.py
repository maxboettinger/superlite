"""#489: record-human-reply never waits on stdin; #852: short yes-words approve, veto words in English and German block."""
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


# ---- #852: short yes-words approve a short reply; veto words in English and German ----

def approves(proj, tmp_path, prompt, ascii_json=False):
    jsonl(proj).unlink(missing_ok=True)
    raw = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}, ensure_ascii=ascii_json)
    r = subprocess.run([BASH, str(REPLY)], input=raw.encode("utf-8"), capture_output=True,
                       env=env_for(proj, tmp_path), timeout=15)
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""
    (line,) = jsonl(proj).read_text(encoding="utf-8").splitlines()
    return json.loads(line)["approves"]


SHORT_WORDS = ["ok", "okay", "sure", "yep", "yeah", "fine", "good", "great", "perfect", "alright", "go",
               "ja", "jo", "jep", "passt", "mach", "machs", "los", "klar", "gut", "genau", "gerne", "gern",
               "perfekt", "super", "prima", "weiter", "einverstanden"]


@pytest.mark.parametrize("word", SHORT_WORDS)
def test_short_yes_word_alone_approves(proj, tmp_path, word):
    assert approves(proj, tmp_path, word) is True
    assert approves(proj, tmp_path, word.capitalize() + "!") is True


@pytest.mark.parametrize("prompt", [
    "ja, passt", "Passt so.", "ok mach", "Mach's", "ok, mach weiter", "Ja bitte", "sure, thanks",
    "sounds good", "klingt gut", "let's go", "Let’s go", "passt für mich", "ok dann mach mal", "  OK  ",
    "Sieht gut aus, leg los", "Genehmigt.", "Plan freigegeben, danke dir für die Arbeit an den Tests",
    "Der Plan sieht gut aus und die Tests decken alles ab",
])
def test_short_and_german_replies_approve(proj, tmp_path, prompt):
    assert approves(proj, tmp_path, prompt) is True


GERMAN_VETO = ["nein", "nicht", "kein", "keine", "aber", "warte", "warten", "moment", "stopp", "ändere", "Ändere",
               "ändern", "Änderung", "aendere", "aendern", "statt", "stattdessen"]


@pytest.mark.parametrize("word", GERMAN_VETO)
def test_german_veto_word_blocks(proj, tmp_path, word):
    assert approves(proj, tmp_path, "Sieht gut aus, " + word + " den Titel") is False
    assert approves(proj, tmp_path, "approve, " + word) is False


def test_veto_control_approves(proj, tmp_path):
    assert approves(proj, tmp_path, "Sieht gut aus, den Titel") is True
    assert approves(proj, tmp_path, "approve, ok") is True


@pytest.mark.parametrize("prompt", [
    "ja, aber nimm einen anderen Namen", "ok warte", "passt, ändere aber den Titel", "Ändere den Titel, dann ok",
    "Nein, mach das", "leg los, aber ohne Tests", "genehmigt, keine Doku", "Sieht gut aus, stattdessen Variante B",
    "ok but rename it", "sure, wait", "looks good, but change the name", "go ahead, no tests", "lgtm, stop",
])
def test_veto_words_block(proj, tmp_path, prompt):
    assert approves(proj, tmp_path, prompt) is False


@pytest.mark.parametrize("prompt", [
    "ok so I think we should rework the parser first and then look at the export",
    "ok, schreib zuerst die Tests für den Parser und den Export",
    "ok rename the file", "ja den Export auch", "ok?", "passt das?", "ja? mach",
    "ok " * 30, "so", "bitte", "thanks", "okey dokey", "gutes Wetter heute",
])
def test_long_or_questioning_reply_does_not_approve(proj, tmp_path, prompt):
    assert approves(proj, tmp_path, prompt) is False


def test_veto_hidden_by_json_escape(proj, tmp_path):
    assert approves(proj, tmp_path, "Sieht gut aus, Ändere den Titel", ascii_json=True) is False
    assert approves(proj, tmp_path, "Sieht gut aus, ändere den Titel", ascii_json=True) is False
    assert approves(proj, tmp_path, "passt für mich", ascii_json=True) is True
    assert approves(proj, tmp_path, "Let’s go", ascii_json=True) is True
