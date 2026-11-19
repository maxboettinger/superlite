"""#825: task messages offer run_tests --affected and name extra runs from the Steps line."""
import sys

from test_plan_tools import SCRIPTS, make_plan

sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402

TAIL = ", then run the printed `wait:` line in the foreground."
ALSO = "; run each before you report DONE (the Verify line does not cover them)."


def plan_with(tmp_path, tasks, steps):
    p = make_plan(tmp_path, tasks)
    text = p.read_text(encoding="utf-8")
    for tid, st in steps.items():
        head = f"### {tid} "
        i = text.index(head)
        j = text.index("\n", text.index("**Owns:**", i))
        text = text[:j] + f"\n**Steps:** {st}" + text[j:]
    p.write_text(text, encoding="utf-8")
    return p


def lines(msg):
    return msg.splitlines()


def test_steps_runs_examples():
    assert io.steps_runs("1 failing test, 2 run: FAIL, 3 implement, 4 run: PASS, 5 run TestCompactDue") == ["TestCompactDue"]
    assert io.steps_runs("1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS") == []
    assert io.steps_runs("1 edit, 2 run `tests/scripts/test_x.py`, 3 run: pass") == ["tests/scripts/test_x.py"]


def test_steps_runs_empty_and_odd():
    assert io.steps_runs("") == []
    assert io.steps_runs("2 run: FAIL (red)") == []
    assert io.steps_runs("5 run X, 6 run X") == ["X"]


def test_fast_line_offers_affected(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/a_test.py"}])
    msg = io.task_message(plan, ["T1"], "/sl/sl", "/sl")
    assert ("Verify: `/sl/sl run_tests --fast tests/a_test.py --task T1 --background` "
            "(or `/sl/sl run_tests --affected --task T1 --background`, which picks the tests your change touches)" + TAIL) in lines(msg)


def test_steps_test_file_joins_fast_paths(tmp_path):
    plan = plan_with(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/a_test.py"}], {"T1": "1 edit, 5 run tests/b_test.py"})
    msg = io.task_message(plan, ["T1"], "/sl/sl", "/sl")
    assert "run_tests --fast tests/a_test.py tests/b_test.py --task T1 --background`" in msg
    assert "Steps also run" not in msg


def test_steps_class_gets_line(tmp_path):
    plan = plan_with(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/a_test.py"}], {"T1": "1 edit, 5 run TestCompactDue"})
    ls = lines(io.task_message(plan, ["T1"], "/sl/sl", "/sl"))
    i = next(k for k, x in enumerate(ls) if x.startswith("Verify: "))
    assert ls[i + 1] == "Steps also run: TestCompactDue" + ALSO


def test_batch_steps_line_per_member(tmp_path):
    plan = plan_with(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/a_test.py"}, {"id": "T2", "owns": "src/b.py, tests/b_test.py"}], {"T2": "5 run TestX"})
    ls = lines(io.task_message(plan, ["T1", "T2"], "/sl/sl", "/sl"))
    i = next(k for k, x in enumerate(ls) if x.startswith("Verify T2: "))
    assert ls[i + 1] == "Steps also run T2: TestX" + ALSO
    assert not any(x.startswith("Steps also run T1") for x in ls)


def test_cmd_and_build_forms_unchanged(tmp_path):
    plan = plan_with(tmp_path, [{"id": "T1", "owns": "src/a.py", "tests": "cmd=make check"}, {"id": "T2", "owns": "Sources/App/A.swift", "tests": "build"}],
                     {"T1": "5 run tests/b_test.py", "T2": "5 run tests/c_test.py"})
    ls = lines(io.task_message(plan, ["T1", "T2"], "/sl/sl", "/sl"))
    assert "Verify T1: `/sl/sl run_tests --task T1 --background` (runs its **Tests:** cmd=`make check`)" + TAIL in ls
    assert "Verify T2: `/sl/sl run_tests --full --task T2 --background` (Tests: build, a build check)" + TAIL in ls
    assert "Steps also run T1: tests/b_test.py" + ALSO in ls
    assert "Steps also run T2: tests/c_test.py" + ALSO in ls
