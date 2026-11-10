import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import compact_text  # noqa: E402

BATCH = {"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "depends": [], "decisions": [], "state": "planned"}
MODE_FILE = "orchestrator" + ".json"
BACKLOG_FILE = "backlog" + ".json"


def _sl(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / MODE_FILE).write_text(json.dumps({"mode": "ai", "time": "2026-11-10T10:00:00", "by": "user"}),
                                encoding="utf-8")
    return sl


def test_continuation_tells_how_to_go_on_and_shows_state(tmp_path):
    text = compact_text.continuation(str(_sl(tmp_path)))
    assert "compacted automatically" in text
    assert "Trust the run state below over the summary" in text
    assert "without asking for confirmation" in text
    assert "do not start it again" in text
    assert "orchestrator: AI" in text          # a line of `sl status`


def test_continuation_adds_an_open_backlog(tmp_path):
    sl = _sl(tmp_path)
    (sl / BACKLOG_FILE).write_text(json.dumps({"version": 1, "repo": "o/r", "batches": [BATCH]}), encoding="utf-8")
    text = compact_text.continuation(str(sl))
    assert "backlog o/r: 1 batches" in text
    assert "B1 | #1 | planned" in text


def test_continuation_leaves_out_a_shipped_backlog(tmp_path):
    sl = _sl(tmp_path)
    (sl / BACKLOG_FILE).write_text(json.dumps({"version": 1, "batches": [dict(BATCH, state="shipped")]}),
                                   encoding="utf-8")
    assert "backlog" not in compact_text.continuation(str(sl))


def test_state_block_is_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(compact_text, "_state_lines", lambda sd: ["x" * 1000] * 50)
    text = compact_text.continuation(str(_sl(tmp_path)))
    state = text.split("Run state:\n", 1)[1]
    assert len(state) <= 3000
    assert all(len(ln) <= 300 for ln in state.splitlines())
    assert state.splitlines()[0].endswith("...")


def test_state_lines_lose_control_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(compact_text, "_state_lines", lambda sd: ["a\x1b[31mb\x00c\td  e"])
    text = compact_text.continuation(str(_sl(tmp_path)))
    assert text.split("Run state:\n", 1)[1] == "a[31mbc d e"   # the hook puts this text into a JSON string


def test_failing_state_falls_back_to_the_command(tmp_path, monkeypatch):
    def boom(sd):
        raise RuntimeError("corrupt")
    monkeypatch.setattr(compact_text, "_state_lines", boom)
    text = compact_text.continuation(str(_sl(tmp_path)))
    assert "compacted automatically" in text
    assert "sl status" in text and "Run state:" not in text


def test_slow_state_falls_back_to_the_command(tmp_path, monkeypatch):
    monkeypatch.setattr(compact_text, "_STATE_LIMIT_S", 0.05)
    monkeypatch.setattr(compact_text, "_state_lines", lambda sd: time.sleep(2) or ["late"])
    started = time.monotonic()
    text = compact_text.continuation(str(_sl(tmp_path)))
    assert time.monotonic() - started < 1.5
    assert "sl status" in text and "late" not in text
