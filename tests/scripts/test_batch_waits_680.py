"""batch_waits classifies lead and main turns and counts lead wake-ups (#680)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import batch_waits  # noqa: E402

T0 = 1794520000.0
ZERO = {"report": 0, "busy": 0, "timeout": 0, "test_wait": 0, "lock": 0, "prompt": 0}


def stamp(off):
    return datetime.fromtimestamp(T0 + off, timezone.utc).isoformat().replace("+00:00", "Z")


def bash(cmd, uid="u1"):
    return {"type": "tool_use", "id": uid, "name": "Bash", "input": {"command": cmd}}


def use(off, block):
    return {"type": "assistant", "timestamp": stamp(off), "message": {"id": "m" + block["id"], "content": [block]}}


def result(off, uid, text):
    blk = {"type": "tool_result", "tool_use_id": uid, "content": [{"type": "text", "text": text}]}
    return {"type": "user", "timestamp": stamp(off), "message": {"content": [blk]}}


def user_text(off, text, **extra):
    return {"type": "user", "timestamp": stamp(off), "message": {"content": [{"type": "text", "text": text}]}, **extra}


def write(tmp_path, entries):
    p = tmp_path / "lead.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return p


def test_kinds():
    k = batch_waits.lead_kind
    assert k([bash("/x/sl fleet wait --timeout 540000 --plan .superlite")]) == "wait"
    assert k([{"type": "tool_use", "name": "Read", "input": {"file_path": "/x/a.py"}}]) == "read"
    assert k([{"type": "text", "text": "Status: DONE"}]) == "text"
    assert k([bash("/x/sl backlog ship B1 lock x --wait")]) == "wait"
    assert k([bash("/x/sl run_tests --wait /p")]) == "wait"
    assert k([bash("/x/sl run_tests --fast a.py")]) == "test"
    assert k([bash("maxapp ship")]) == "ship"
    assert k([bash("/x/sl fleet spawn --role w --brief b.md")]) == "dispatch"
    assert k([{"type": "tool_use", "name": "Agent", "input": {}}]) == "dispatch"
    assert k([bash("/x/scripts/sl plan x")]) == "sl"
    assert k([{"type": "tool_use", "name": "Edit", "input": {}}]) == "edit"
    assert k([bash("git status")]) == "read"
    assert k([{"type": "tool_use", "name": "Skill", "input": {}}]) == "skill"
    assert k([bash("make")]) == "other"
    assert k([{"type": "text", "text": "x"}, bash("cat a"), {"type": "tool_use", "name": "Edit", "input": {}}]) == "edit"
    m = batch_waits.main_kind
    assert m([bash("/x/sl backlog plan --github")]) == "plan"
    assert m([{"type": "tool_use", "name": "Read", "input": {"file_path": "/x/a"}}]) == "other"
    assert m([]) == "text"


def test_compound_commands():
    k = batch_waits.lead_kind
    assert k([bash("cd /x && grep -n foo a.py")]) == "read"
    assert k([bash("cd /x; sed -n 1,9p a.py")]) == "read"
    assert k([bash("SL=/x/sl; P=p.md; $SL commit_task T1 --plan $P")]) == "sl"
    assert k([bash("D=/x; ls $D | head")]) == "read"
    assert k([bash("cd /x && python3 - <<'EOF'")]) == "other"


def test_spawn_wait_is_a_wait():
    assert batch_waits.lead_kind([bash("sl fleet spawn --role final-reviewer --brief b.md --wait")]) == "wait"


def test_lead_example(tmp_path):
    p = write(tmp_path, [
        user_text(0, "brief"),
        use(10, bash("/x/sl fleet wait --plan .superlite", "a")),
        result(310, "a", "W1 T1 DONE\n"),
        use(320, bash("/x/sl fleet wait --plan .superlite", "b")),
        result(380, "b", "TIMEOUT W2\n"),
        use(390, bash("/x/sl run_tests --wait /p", "c")),
        result(450, "c", "ok"),
        user_text(500, "please continue"),
    ])
    assert batch_waits.waits(p) == {"wakeups": {**ZERO, "report": 1, "timeout": 1, "test_wait": 1, "prompt": 1}, "blocked_wait_s": 420.0}


def test_missing_file(tmp_path):
    assert batch_waits.waits(tmp_path / "missing.jsonl") == {"wakeups": ZERO, "blocked_wait_s": 0.0}


def test_busy_line_is_busy(tmp_path):
    p = write(tmp_path, [use(0, bash("sl fleet wait", "a")), result(5, "a", "note\nBUSY W2 T3\n")])
    assert batch_waits.waits(p)["wakeups"]["busy"] == 1


def test_timeout_wins_over_report(tmp_path):
    p = write(tmp_path, [use(0, bash("sl fleet wait", "a")), result(5, "a", "W1 T1 DONE\nTIMEOUT W2\n")])
    w = batch_waits.waits(p)["wakeups"]
    assert (w["timeout"], w["report"]) == (1, 0)


def test_repeated_tool_use_id_counts_once(tmp_path):
    p = write(tmp_path, [
        use(0, bash("sl fleet wait", "a")),
        use(3, bash("sl fleet wait", "a")),
        result(10, "a", "W1 T1 DONE"),
    ])
    r = batch_waits.waits(p)
    assert r["wakeups"]["report"] == 1
    assert r["blocked_wait_s"] == 10.0


def test_lock_wait(tmp_path):
    p = write(tmp_path, [use(0, bash("sl backlog ship B1 lock x --wait", "a")), result(7, "a", "ok")])
    r = batch_waits.waits(p)
    assert r["wakeups"]["lock"] == 1 and r["blocked_wait_s"] == 7.0


def test_brief_is_not_a_prompt(tmp_path):
    p = write(tmp_path, [
        user_text(0, "the brief"),
        user_text(1, "meta text", isMeta=True),
        user_text(2, "<system-reminder>x"),
        user_text(3, "real follow-up"),
    ])
    assert batch_waits.waits(p)["wakeups"]["prompt"] == 1


def test_negative_blocked_clamped(tmp_path):
    p = write(tmp_path, [use(10, bash("sl fleet wait", "a")), result(5, "a", "W1 T1 DONE")])
    assert batch_waits.waits(p)["blocked_wait_s"] == 0.0
