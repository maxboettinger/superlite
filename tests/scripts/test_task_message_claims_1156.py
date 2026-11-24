"""A ledger `Ruling: Tn also commits F - why` line puts F on Tn's message as `Also edit (claimed):`, never under `Do not touch` (#1156)."""
import json
from pathlib import Path
from test_plan_tools import make_plan
import fleet_io as io

CLAIMED = "Also edit (claimed): a.py (ruled to this task in the run's ledger by commit_task --claim or --also; commit_task commits them with this task)"


def ledger(tmp_path, *lines):
    p = tmp_path / "progress.md"
    p.write_text("".join(f"- Ruling: {ln}\n" for ln in lines), encoding="utf-8")
    return p


def plan_of(tmp_path, t7=None):
    return make_plan(tmp_path, [{"id": "T5", "owns": "a.py"}, {"id": "T7", "owns": "b.py", **(t7 or {})}])


def test_claimed_files_reads_ruling_lines(tmp_path):
    lg = ledger(tmp_path, "T7 also commits Sources/FakeStore.swift - T7 adds members")
    assert io.claimed_files(lg, ["T7"]) == ["Sources/FakeStore.swift"]
    assert io.claimed_files(lg, ["T5"]) == []
    assert io.claimed_files(tmp_path / "missing.md", ["T7"]) == []
    lg = ledger(tmp_path, "T7 also commits a.py - x", "T7 also commits dir/ - y", "T7 also commits a.py - x", "T5 also commits c.py - z")
    assert io.claimed_files(lg, ["T7"]) == ["a.py", "dir/"]
    assert io.claimed_files(lg, ["T5", "T7"]) == ["a.py", "dir/", "c.py"] or set(io.claimed_files(lg, ["T5", "T7"])) == {"a.py", "dir/", "c.py"}


def test_claimed_file_goes_on_its_own_also_edit_line(tmp_path):
    plan = plan_of(tmp_path); lg = ledger(tmp_path, "T7 also commits a.py - x")
    for tier in ("sonnet", "haiku"):
        m = io.task_message(plan, ["T7"], "/sl/sl", "/sl", tier, ledger=lg).split("\n")
        i = next(k for k, ln in enumerate(m) if ln.startswith("Owns:"))
        assert m[i + 1] == CLAIMED
        if tier == "haiku":
            assert "a.py" not in next(ln for ln in m if ln.startswith("Do not touch:"))
    plan = plan_of(tmp_path, {"features": "x"})
    text = plan.read_text().replace("**Owns:** b.py\n", "**Owns:** b.py\n**Also-touches:** d.py\n")
    plan.write_text(text)
    m = io.task_message(plan, ["T7"], "/sl/sl", "/sl", ledger=lg).split("\n")
    i = next(k for k, ln in enumerate(m) if ln.startswith("Also edit:"))
    assert "d.py" in m[i] and m[i + 1] == CLAIMED


def test_no_claim_keeps_message_byte_identical(tmp_path):
    plan = plan_of(tmp_path); lg = ledger(tmp_path, "T5 also commits a.py - x")
    a = io.task_message(plan, ["T7"], "/sl/sl", "/sl")
    assert a == io.task_message(plan, ["T7"], "/sl/sl", "/sl", ledger=None) == io.task_message(plan, ["T7"], "/sl/sl", "/sl", ledger=lg)


def test_claim_already_in_also_touches_is_not_repeated(tmp_path):
    plan = plan_of(tmp_path)
    plan.write_text(plan.read_text().replace("**Owns:** b.py\n", "**Owns:** b.py\n**Also-touches:** a.py\n"))
    lg = ledger(tmp_path, "T7 also commits a.py - x")
    m = io.task_message(plan, ["T7"], "/sl/sl", "/sl", "haiku", ledger=lg)
    assert "Also edit: a.py" in m and "Also edit (claimed)" not in m


def test_also_touches_of_independent_owner_is_editable(tmp_path):
    plan = plan_of(tmp_path)
    plan.write_text(plan.read_text().replace("**Owns:** b.py\n", "**Owns:** b.py\n**Also-touches:** a.py\n"))
    m = io.task_message(plan, ["T7"], "/sl/sl", "/sl", "haiku")
    assert "Also edit: a.py" in m
    assert "a.py" not in next(ln for ln in m.split("\n") if ln.startswith("Do not touch:"))


def test_send_passes_run_ledger(tmp_path, monkeypatch):
    sd = tmp_path / "sd"; sd.mkdir()
    (sd / "fleet.json").write_text(json.dumps({"on": True, "label": "l", "workspace_id": "w", "root_pane": "w:p1", "accounts": ["c"], "next": 2,
        "workers": {"W1": {"name": "n", "pane_id": "w:p1", "account": "c", "agent": "superlite:implementer", "tier": "sonnet", "state": "ready", "task": None, "started": 1}}}))
    seen = {}
    monkeypatch.setattr(io, "task_message", lambda *a, **k: seen.update(k) or "msg")
    monkeypatch.setattr(io, "_prompt", lambda *a, **k: None)
    monkeypatch.setattr(io, "_busy", lambda *a, **k: None)
    monkeypatch.setattr(io, "pane_label", lambda *a, **k: None)
    monkeypatch.setattr(io, "_tel_dispatch", lambda *a, **k: None)
    io.send(sd, tmp_path / "p.md", "W1", ["T7"], "/sl/sl", "/sl")
    assert seen["ledger"] == Path(sd) / "progress.md"
