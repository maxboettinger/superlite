# tests/scripts/test_fleet_brief_constraints_635.py: every brief `sl fleet` sends carries the plan's Global constraints once (#635)
import json, sys
import pytest
from test_fleet import world  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import fleet_state as fs  # noqa: E402

HEAD = "# Plan\n**Goal:** test.\n\nGlobal constraints:\n- Every check runs on the build machine.\n\n"
TASKS = "### T1 first · Complexity 3 (O-1) · Est. context 40k\n**Owns:** src/a.py\n"
SECTION = "\n## Global constraints\n\nGlobal constraints:\n- Every check runs on the build machine.\n"


@pytest.fixture
def plan(tmp_path):
    p = tmp_path / "cplan.md"; p.write_text(HEAD + TASKS)
    return p


def test_with_constraints_appends_the_section(plan):
    assert fleet.with_constraints("# Brief\n", plan) == "# Brief\n" + SECTION


def test_with_constraints_keeps_a_brief_that_has_them(plan):
    text = "# Brief\n\n## Global constraints\n\nown\n"
    assert fleet.with_constraints(text, plan) == text


def test_with_constraints_no_plan_or_none_stated(tmp_path):
    assert fleet.with_constraints("x\n", None) == "x\n"
    bare = tmp_path / "bare.md"; bare.write_text("# Plan\n**Goal:** t.\n\n" + TASKS)
    assert fleet.with_constraints("x\n", bare) == "x\n"


def test_plan_file_order(tmp_path, plan):
    sd = tmp_path / "proj" / ".superlite"; sd.mkdir(parents=True)
    assert fleet.plan_file(sd, None) is None
    (sd / "pool.json").write_text("not json")
    assert fleet.plan_file(sd, str(tmp_path / "missing.md")) is None
    (sd.parent / "docs").mkdir(); (sd.parent / "docs" / "p.md").write_text(HEAD)
    (sd / "pool.json").write_text(json.dumps({"plan": "docs/p.md"}))
    assert fleet.plan_file(sd, None) == sd.parent / "docs" / "p.md"
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan)}))
    assert fleet.plan_file(sd, None) == plan
    other = tmp_path / "other.md"; other.write_text(HEAD)
    assert fleet.plan_file(sd, str(other)) == other


def test_add_constraints_reports_change_and_survives_errors(plan, tmp_path):
    b = tmp_path / "b.md"; b.write_text("hi\n")
    assert fleet.add_constraints(str(b), plan) is True
    assert fleet.add_constraints(str(b), plan) is False
    assert fleet.add_constraints(str(tmp_path / "nope.md"), plan) is False


def test_send_brief_gains_constraints_once(world, plan, monkeypatch):
    got = []
    monkeypatch.setattr(fleet_io, "main", lambda argv: got.append(list(argv)) or 0)
    brief = world.proj / "b.md"; brief.write_text("# Brief\n")
    argv = ["send", "W1", "--brief", str(brief), "--plan", str(plan)]
    assert fleet.main(list(argv)) == 0
    assert brief.read_text() == "# Brief\n" + SECTION
    assert fleet.main(list(argv)) == 0
    assert brief.read_text() == "# Brief\n" + SECTION
    assert got == [argv, argv]


def test_send_survives_a_failing_plan_lookup(world, plan, monkeypatch):
    got = []
    monkeypatch.setattr(fleet_io, "main", lambda argv: got.append(list(argv)) or 0)
    monkeypatch.setattr(fleet, "_sd", lambda a: (_ for _ in ()).throw(RuntimeError("boom")))
    brief = world.proj / "b.md"; brief.write_text("# Brief\n")
    argv = ["send", "W1", "--brief", str(brief), "--plan", str(plan)]
    assert fleet.main(list(argv)) == 0
    assert got == [argv] and brief.read_text() == "# Brief\n"


def test_spawn_brief_gains_constraints(world, plan, monkeypatch):
    plan = world.plan  # inside the run's project, so --plan resolves its state folder
    plan.write_text(HEAD + TASKS)
    fleet.main(["on"])
    sent = []
    monkeypatch.setattr(fleet_io, "send_brief", lambda sd, wid, brief, label="", full=False: sent.append(open(brief).read()) or label)
    brief = world.proj / "b.md"; brief.write_text("do it\n")
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "2", "--brief", str(brief), "--plan", str(plan)]) == 0
    assert sent == ["do it\n" + SECTION]


@pytest.mark.parametrize("note", [False, True])
def test_for_review_brief_has_constraints(world, plan, monkeypatch, note):
    plan = world.plan
    plan.write_text(HEAD + TASKS)
    fleet.main(["on"])
    (world.sd / "progress.md").write_text("- commit T1 abc1234 first\n")
    def spawn(sd_, plan_, tier, project, cfg=None, env=None, role="implementer", over=False, machine_wait=100.0):
        with fs.locked(sd_):
            d = fs.load(sd_); d["workers"]["W4"] = {"id": "W4", "role": role, "state": "ready"}; fs.save(sd_, d)
        return {"id": "W4"}
    monkeypatch.setattr(fleet, "spawn", spawn)
    monkeypatch.setattr(fleet_io, "send_brief", lambda sd, wid, brief, label="", full=False: label)
    monkeypatch.setattr(fleet_io, "review_brief", lambda *a, **k: "REVIEW\n")
    args = ["spawn", "--for-review", "T1", "--plan", str(plan)]
    if note:
        n = world.proj / "n.md"; n.write_text("look here\n"); args += ["--note", str(n)]
    assert fleet.main(args) == 0
    text = (world.sd / "briefs" / "review-T1.md").read_text()
    assert text.startswith("REVIEW\n") and "## Global constraints" in text
    if note:
        assert text.index("## Global constraints") < text.index("## Coordinator notes")
