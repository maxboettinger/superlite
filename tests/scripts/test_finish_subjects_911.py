"""finish's checkpoint note lists the subjects `autocommit apply` will write (#911)."""
import json
import sys

from test_finish_last_full_498 import ledger
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402
import finish  # noqa: E402

HEAD = "subjects (apply rebuilds them from the plan: edit its **Ticket:** fields or subject template before apply to change them):"


def note(tmp_path, monkeypatch, entries, plan_path=None):
    p = ledger(tmp_path)
    st = {"run": "r1", "entries": entries}
    if plan_path:
        st["plan"] = str(plan_path)
    (p.parent / "checkpoints.json").write_text(json.dumps(st), encoding="utf-8")
    monkeypatch.setattr(autocommit, "is_on", lambda *a, **k: False)
    return finish.checkpoint_note(p)


def entry(tid, title, plan=None, sha="s"):
    e = {"task": tid, "title": f"{tid}: {title}", "files": [f"{tid}.py"], "sha": sha}
    if plan:
        e["plan"] = str(plan)
    return e


def test_note_lists_subjects(tmp_path, monkeypatch):
    plan = tmp_path / "plan.md"
    plan.write_text("# P\n\n## Tasks\n\n### T1 parser\n**Ticket:** PIX-3\n\n### T2 cli\n", encoding="utf-8")
    lines = note(tmp_path, monkeypatch, [entry("T1", "parser", plan, "a"), entry("T1", "parser", plan, "b"), entry("T2", "cli", plan, "c")], plan)
    i = next(n for n, x in enumerate(lines) if x.startswith("to commit:"))
    assert "(one commit per task, subjects below; add" in lines[i]
    assert lines[i + 1] == HEAD
    assert lines[i + 2:i + 4] == ["- PIX-3 T1: parser", "- T2: cli"]
    assert lines.count("- PIX-3 T1: parser") == 1


def test_note_cuts_at_five(tmp_path, monkeypatch):
    plan = tmp_path / "plan.md"
    plan.write_text("# P\n\n## Tasks\n\n" + "".join(f"### T{n} t{n}\n\n" for n in range(1, 8)), encoding="utf-8")
    lines = note(tmp_path, monkeypatch, [entry(f"T{n}", f"t{n}", plan) for n in range(1, 8)], plan)
    assert sum(x.startswith("- T") for x in lines) == 5
    assert "- ... +2 more" in lines


def test_note_without_plan_uses_stored(tmp_path, monkeypatch):
    lines = note(tmp_path, monkeypatch, [{"task": "T1", "title": "T1 x", "files": ["a.py"], "sha": "s"}])
    assert "- T1 x" in lines
