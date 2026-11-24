"""A research worker on this machine may name existing paths outside the project, read-only; the brief file stays checked (#1158)."""
import json
import pytest
from test_fleet_io import io, world  # noqa: F401  (world is a fixture)
from test_plan_tools import make_plan

TAIL = "a worker cannot read them: copy each file into"


def _ref(tmp_path):
    d = tmp_path / "x"; d.mkdir(); f = d / "ref.md"; f.write_text("r"); return f


def _brief(world, text):
    b = world.sd / "briefs" / "R.md"; b.parent.mkdir(exist_ok=True); b.write_text(text); return b


def test_local_research_may_name_outside_path(world, tmp_path):
    f = _ref(tmp_path); b = _brief(world, f"Read {f}.\n")
    assert io.brief_refusal(world.sd, b, "research", local=True) is None
    for why in (io.brief_refusal(world.sd, b, "research"), io.brief_refusal(world.sd, b, "implementer", local=True)):
        assert why is not None and f"{f}; {TAIL}" in why
    assert io.brief_reads(world.sd, b) == [str(f)]


def test_local_research_brief_file_outside_still_refused(world, tmp_path):
    b = tmp_path / "b.md"; b.write_text("Answer.\n")
    why = io.brief_refusal(world.sd, b, "research", local=True)
    assert why is not None and why.startswith(f"error: brief {b.resolve()} is outside the project")


def test_brief_reads_adds_constraint_paths(world, tmp_path):
    f = _ref(tmp_path); g = tmp_path / "x" / "spec.md"; g.write_text("s")
    plan = make_plan(world.proj, [{"id": "T1", "owns": "src/a.py"}], header=f"\nGlobal constraints:\n- The spec is {g}.\n", name="cplan.md")
    b = _brief(world, f"Read {f}.\n")
    assert io.brief_reads(world.sd, b, plan=plan) == [str(f), str(g)]


def _setw(world, **kw):
    p = world.sd / "fleet.json"; data = json.loads(p.read_text()); data["workers"]["W1"].update(kw); p.write_text(json.dumps(data))


def test_send_research_local_passes_remote_refused(world, capsys, tmp_path, monkeypatch):
    f = _ref(tmp_path); b = _brief(world, f"Read {f}.\n")
    seen = []
    monkeypatch.setattr(io, "send_brief", lambda sd, wid, brief, *a, **k: seen.append(wid))
    _setw(world, role="research")
    assert io.main(["send", "W1", "--brief", str(b)]) == 0 and seen == ["W1"]
    seen.clear(); _setw(world, machine="mxn")
    assert io.main(["send", "W1", "--brief", str(b)]) == 2
    assert f"{f}; {TAIL}" in capsys.readouterr().err and seen == []
