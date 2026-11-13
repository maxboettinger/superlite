"""#745: a task's Also-touches files are named as editable in `sl task` and in the fleet task message, never under `Do not touch`."""
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io  # noqa: E402
import plan_tools  # noqa: E402
import task  # noqa: E402

LINE = task.also_line(["src/b.py"])


def block(tid, owns, also=""):
    extra = f"**Also-touches:** {also}\n" if also else ""
    return f"### {tid} · task {tid} · Complexity 2 · Est. context 20k\n\n**Owns:** {owns}\n{extra}**Tests:** fast\n\n"


def write(tmp_path, t3_also="", body_extra=""):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan\n\n" + block("T1", "`src/a.py`, `tests/test_a.py`", "`src/b.py`") + block("T2", "`src/b.py`, `tests/test_b.py`")
        + block("T3", "`src/c.py`", t3_also) + body_extra,
        encoding="utf-8",
    )
    return str(plan)


def test_message_lists_also_touches(tmp_path):
    plan = write(tmp_path)
    lines = fleet_io.task_message(plan, ["T1"], "/sl/sl", "/sl").splitlines()
    i = lines.index("Owns: src/a.py, tests/test_a.py")
    assert lines[i + 1] == LINE
    assert lines[i + 2] == "Do not touch: tests/test_b.py, src/c.py"


def test_haiku_message_and_sl_task(tmp_path, capsys):
    plan = write(tmp_path)
    msg = fleet_io.task_message(plan, ["T1"], "/sl/sl", "/sl", tier="haiku")
    assert msg.splitlines().count(LINE) == 2
    out = task.render(plan_tools.Plan.load(plan), "T1").splitlines()
    assert out[out.index(LINE) - 1] == ""
    assert out[out.index(LINE) - 2] == "**Tests:** fast"
    task.main(["T1", "--plan", plan])
    assert LINE in capsys.readouterr().out.splitlines()


def test_plain_task_unchanged(tmp_path):
    plan = write(tmp_path)
    msg = fleet_io.task_message(plan, ["T2"], "/sl/sl", "/sl")
    assert not [ln for ln in msg.splitlines() if ln.startswith("Also edit:")]
    assert "Do not touch: src/a.py, tests/test_a.py, src/c.py" in msg.splitlines()
    assert not [ln for ln in task.render(plan_tools.Plan.load(plan), "T2").splitlines() if ln.startswith("Also edit:")]


def test_batch_unions_also_touches(tmp_path):
    plan = write(tmp_path, t3_also="src/b.py, src/a.py")
    lines = fleet_io.task_message(plan, ["T1", "T3"], "/sl/sl", "/sl").splitlines()
    assert "Owns: src/a.py, tests/test_a.py, src/c.py" in lines
    assert lines.count(LINE) == 1
    assert "Do not touch: tests/test_b.py" in lines


def test_also_touches_parse(tmp_path):
    plan = write(tmp_path, t3_also="src/{b,d}.py")
    pl = plan_tools.Plan.load(plan)
    assert task.also_touches(pl.by_id["T3"]) == ["src/b.py", "src/d.py"]
    plan2 = write(tmp_path, t3_also="src/b.py, src/c.py, src/b.py")
    assert task.also_touches(plan_tools.Plan.load(plan2).by_id["T3"]) == ["src/b.py"]
    fenced = write(tmp_path, body_extra="```\n**Also-touches:** src/x.py\n```\n")
    t = plan_tools.Plan.load(fenced).by_id["T3"]
    assert task.also_touches(t) == []


def test_module_docstring_names_also_touches():
    assert "also_touches" in task.__doc__ and "Also edit:" in task.__doc__
