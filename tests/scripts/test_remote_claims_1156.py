# tests/scripts/test_remote_claims_1156.py
import sys
from pathlib import Path
from test_fleet_remote_worker import world, plan_for, record  # noqa: F401
from test_fleet_remote_collect import env  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote_worker as rw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RULE = "- The files your task message's `Also edit` lines name are yours to edit too; commit_task commits them with your task."


def test_remote_owns_include_ledger_claims(world):
    plan = plan_for(world)
    (world.sd / "progress.md").write_text("- Ruling: T3 also commits c.py - why\n- Ruling: T3 also commits src/a.py - why\n")
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    assert record(world)["remote"]["owns"] == ["src/a.py", "c.py", "tests/regression/**"]


def test_remote_owns_without_ledger_unchanged(world):
    plan = plan_for(world)
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    assert record(world)["remote"]["owns"] == ["src/a.py", "tests/regression/**"]


def test_remote_send_task_passes_ledger(world, monkeypatch):
    plan = plan_for(world)
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    seen = {}
    def fake(*a, **k):
        seen.update(k); return "msg"
    monkeypatch.setattr(rw.fio, "task_message", fake)
    monkeypatch.setattr(rw, "_prompt", lambda *a, **k: None)
    rw.send_task(world.sd, "W1", str(plan), ["T3"], "sl")
    assert seen["ledger"] == Path(world.sd) / "progress.md"


def test_implementer_rules_name_also_edit():
    for name in ("implementer.md", "implementer-haiku.md"):
        lines = (ROOT / "agents" / name).read_text().splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("- Format only the files you changed:"))
        assert lines[i + 1] == RULE


def _collect_owns(env, monkeypatch, ledger):
    from test_fleet_remote_collect import worker, report
    import fleet_remote_collect as frc
    import fleet_state as fs
    worker(env, owns=("src/a.py", "tests/regression/**"), snap="abc")
    data = fs.load(env.sd); data["workers"]["W2"]["task"] = "T1,T3"; fs.save(env.sd, data)
    if ledger:
        (env.sd / "progress.md").write_text(ledger)
    seen = {}
    monkeypatch.setattr(frc.fr, "fetch", lambda *a, **k: "abc")
    def fake(project, start, sha, owns):
        seen["owns"] = owns
        return {"applied": [], "skipped": [], "conflicts": []}
    monkeypatch.setattr(frc.remote_apply, "apply", fake)
    frc.collect(env.sd, "W2", report())
    return seen["owns"]


def test_remote_collect_takes_claims_made_after_spawn(env, monkeypatch):
    owns = _collect_owns(env, monkeypatch, "- Ruling: T3 also commits c.py - why\n- Ruling: T3 also commits src/a.py - why\n- Ruling: T9 also commits d.py - why\n")
    assert owns.count("c.py") == 1 and "d.py" not in owns and owns.count("src/a.py") == 1


def test_remote_collect_without_ledger_owns_unchanged(env, monkeypatch):
    assert "c.py" not in _collect_owns(env, monkeypatch, None)
