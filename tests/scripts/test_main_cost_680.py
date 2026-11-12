"""main_cost records main's sessions and writes one main row per plan round (#680)."""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import backlog_state  # noqa: E402

T0 = 1794520000.0


def _main_kind(blocks):
    for b in blocks:
        if b.get("type") == "tool_use":
            cmd = (b.get("input") or {}).get("command", "")
            return "plan" if "plan" in cmd else "wait" if "wait" in cmd else "other"
    return "text"


def _fake_costs_path(root):
    return Path(root) / ".superlite" / "batch-costs.jsonl"


def _fake_read_rows(root):
    p = _fake_costs_path(root)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


@pytest.fixture
def mc(monkeypatch):
    """main_cost with fake batch_waits and batch_cost (their tasks build the real ones)."""
    bw = types.ModuleType("batch_waits")
    bw.main_kind = _main_kind
    bc = types.ModuleType("batch_cost")
    bc.costs_path = _fake_costs_path
    bc.read_rows = _fake_read_rows
    monkeypatch.setitem(sys.modules, "batch_waits", bw)
    monkeypatch.setitem(sys.modules, "batch_cost", bc)
    monkeypatch.delitem(sys.modules, "main_cost", raising=False)
    import main_cost
    yield main_cost
    sys.modules.pop("main_cost", None)


def stamp(off):
    return datetime.fromtimestamp(T0 + off, timezone.utc).isoformat().replace("+00:00", "Z")


def entry(mid, off, cmd=None):
    content = [{"type": "tool_use", "name": "Bash", "input": {"command": cmd}}] if cmd else [{"type": "text", "text": "x"}]
    usage = {"input_tokens": 2, "cache_read_input_tokens": 300, "output_tokens": 30}
    return {"type": "assistant", "timestamp": stamp(off),
            "message": {"id": mid, "model": "claude-sonnet-4-5", "usage": usage, "content": content}}


def write_session(cfg, root, sid, entries):
    import fleet_io
    d = Path(cfg) / "projects" / fleet_io.project_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{sid}.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return p


def abc(cfg, root, extra=()):
    return write_session(cfg, root, "abc", [entry("m1", 0, "sl backlog plan"), entry("m2", 20, "sl backlog wait"),
                                           entry("m3", 40, "sl backlog wait"), *extra])


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    return {"CLAUDE_CONFIG_DIR": str(cfg)}


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "repo"
    (r / ".superlite").mkdir(parents=True)
    return r


def seed(root, **kw):
    p = backlog_state.path(root)
    d = backlog_state.default()
    d.update(kw)
    p.write_text(json.dumps(d))


def test_main_transcript_found_and_missing(mc, root, env):
    p = abc(env["CLAUDE_CONFIG_DIR"], root)
    assert mc.main_transcript(root, "abc", env) == p
    assert mc.main_transcript(root, "gone", env) is None


def test_resolved_root_tried(mc, tmp_path, env):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    p = abc(env["CLAUDE_CONFIG_DIR"], real.resolve())
    assert mc.main_transcript(link, "abc", env) == p


def test_session_noted_once(mc, root, env):
    seed(root)
    e = {**env, "SUPERLITE_SESSION_ID": "abc"}
    assert mc.note_session(root, e) == "abc"
    assert mc.note_session(root, e) == "abc"
    sess = backlog_state.load(backlog_state.path(root))["main_sessions"]
    assert [s["id"] for s in sess] == ["abc"]
    assert isinstance(sess[0]["t"], float)


def test_fallback_session_id(mc, root, env):
    seed(root)
    assert mc.note_session(root, {**env, "CLAUDE_CODE_SESSION_ID": "zzz"}) == "zzz"


def test_no_session_id_no_entry(mc, root, env):
    seed(root)
    assert mc.note_session(root, env) is None
    assert "main_sessions" not in backlog_state.load(backlog_state.path(root))


def test_fleet_worker_not_noted(mc, root, env):
    seed(root)
    e = {**env, "SUPERLITE_SESSION_ID": "abc", "SUPERLITE_FLEET_WORKER": "W2"}
    assert mc.note_session(root, e) is None


def test_main_row_sums_session_and_marks_unmeasured(mc, root, env):
    abc(env["CLAUDE_CONFIG_DIR"], root)
    data = {"round": ["B1", "B2"], "main_sessions": [{"id": "abc", "t": 1.0}, {"id": "gone", "t": 2.0}]}
    row = mc.main_row(root, data, now=T0 + 100, env=env)
    assert row["row"] == "main" and row["v"] == 1
    assert row["round"] == ["B1", "B2"]
    assert row["sessions"] == ["abc", "gone"]
    assert row["unmeasured"] == ["gone"]
    assert row["windows"] == {"abc": [None, T0 + 100]}
    assert row["turns"] == 3
    assert row["tokens"]["input"] == 6 and row["tokens"]["cache_read"] == 900 and row["tokens"]["output"] == 90
    assert row["wall_s"] == 40.0
    assert row["kinds"]["plan"]["turns"] == 1 and row["kinds"]["wait"]["turns"] == 2
    assert row["cost_usd"] > 0


def test_window_starts_at_previous_main_row(mc, root, env):
    cfg = env["CLAUDE_CONFIG_DIR"]
    abc(cfg, root)
    seed(root, round=["B1"], main_sessions=[{"id": "abc", "t": 1.0}])
    first = mc.record_main(root, env)
    assert first["windows"]["abc"][0] is None
    until = first["windows"]["abc"][1]
    abc(cfg, root, extra=[entry("m4", 10**9, "sl backlog plan")])
    seed(root, round=["B2"], main_sessions=[{"id": "abc", "t": 1.0}])
    second = mc.record_main(root, env)
    assert second["windows"]["abc"][0] == until
    assert second["windows"]["abc"][1] >= until


def test_same_round_written_once(mc, root, env):
    abc(env["CLAUDE_CONFIG_DIR"], root)
    seed(root, round=["B1"], main_sessions=[{"id": "abc", "t": 1.0}])
    assert mc.record_main(root, env) is not None
    assert mc.record_main(root, env) is None
    assert len(_fake_read_rows(root)) == 1


def test_no_backlog_json_none(mc, tmp_path, env):
    assert mc.record_main(tmp_path / "nowhere", env) is None
