"""`fleet send Wn --brief F` refuses a brief its worker cannot read in full before any prompt, as spawn does (#1015, #1024)."""
import json
import pytest
from test_fleet_io import io, world  # noqa: F401  (world is a fixture)
from test_plan_tools import SCRIPTS, make_plan
import fleet  # noqa: E402

TAIL = "a worker cannot read them: copy each file into"


def setw(world, wid, **kw):
    p = world.sd / "fleet.json"; data = json.loads(p.read_text()); data["workers"][wid].update(kw); p.write_text(json.dumps(data))


def prompts(world):
    return [c for c in world.fh.calls if c[0] == "prompt"]


def _other(tmp_path):
    other = tmp_path / "other"; other.mkdir(); (other / "spec.md").write_text("s")
    return other


def _brief(world, text, name="R1.md"):
    b = world.sd / "briefs" / name; b.parent.mkdir(exist_ok=True); b.write_text(text)
    return b


def test_send_refuses_brief_naming_outside_path(world, capsys, tmp_path):
    other = _other(tmp_path)
    b = _brief(world, f"Read {other}/spec.md.\n")
    assert io.main(["send", "W1", "--brief", str(b)]) == 2
    err = capsys.readouterr().err
    assert (f"error: brief {b.resolve()} names paths outside the project, the run folder and the plugin skills folder: {other}/spec.md; "
            f"a worker cannot read them: copy each file into {world.sd.resolve()}/briefs/ and name the copy, or drop the path (#1015)") in err
    assert prompts(world) == []
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert (w["state"], w["task"]) == ("ready", None)


def test_send_refuses_brief_file_outside(world, capsys, tmp_path):
    b = tmp_path / "b.md"; b.write_text("Answer the question.\n")
    assert io.main(["send", "W1", "--brief", str(b)]) == 2
    assert (f"error: brief {b.resolve()} is outside the project, the run folder and the plugin skills folder; a worker cannot read it: "
            f"move it into {world.sd.resolve()}/briefs/ (#1015)") in capsys.readouterr().err
    assert prompts(world) == []


@pytest.mark.parametrize("role", ["implementer", "fixer", "research", "writer", "checker", "package-reviewer", "final-reviewer"])
def test_every_worker_role_but_lead_is_checked(world, capsys, tmp_path, role):
    other = _other(tmp_path)
    setw(world, "W1", role=role)
    b = _brief(world, f"Read {other}/spec.md.\nOutput: out.md\n")
    assert io.main(["send", "W1", "--brief", str(b)]) == 2
    assert f"{other}/spec.md; {TAIL}" in capsys.readouterr().err
    assert prompts(world) == []


def test_send_with_inside_paths_still_sends(world):
    b = _brief(world, f"Read {world.proj}/src/c.py and {world.sd}/briefs/x.md.\n")
    assert io.main(["send", "W1", "--brief", str(b)]) == 0
    assert str(b.resolve()) in prompts(world)[-1][2]


def test_lead_worker_is_not_checked(world, monkeypatch, tmp_path):
    other = _other(tmp_path)
    setw(world, "W1", role="lead")
    b = _brief(world, f"Read {other}/spec.md.\n", "lead.md")
    seen = []
    monkeypatch.setattr(io, "send_brief", lambda sd, wid, brief, *a, **k: seen.append((wid, brief)))
    assert io.main(["send", "W1", "--brief", str(b)]) == 0
    assert seen == [("W1", str(b))]
    out = tmp_path / "lead-outside.md"; out.write_text("x\n")
    assert io.brief_refusal(world.sd, out, "lead") is None


def test_global_constraints_in_the_sent_brief_are_checked(world, capsys, tmp_path):
    other = _other(tmp_path)
    plan = make_plan(world.proj, [{"id": "T1", "owns": "src/a.py"}], header=f"\nGlobal constraints:\n- The spec is {other}/spec.md.\n", name="cplan.md")
    b = _brief(world, "Answer the question.\n")
    assert fleet.add_constraints(str(b), plan) is True  # what fleet.main does before it hands send to fleet_io (#635)
    assert io.main(["send", "W1", "--brief", str(b)]) == 2
    assert f"{other}/spec.md; {TAIL}" in capsys.readouterr().err
    assert prompts(world) == []


def test_unknown_worker_still_names_the_worker(world, capsys):
    b = _brief(world, "x\n")
    assert io.main(["send", "W9", "--brief", str(b)]) == 2
    assert "error: unknown worker or task 'W9'" in capsys.readouterr().err


def test_docs_name_the_send_check():
    doc = (SCRIPTS.parents[2] / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert "`fleet send Wn --brief F` runs the same check before any prompt" in doc and "#1024" in doc
    assert "(#1024)" in io.__doc__
