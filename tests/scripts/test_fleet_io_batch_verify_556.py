"""#556: a batched task message gives each member its own Verify line with its own --task, and says one run per task."""
import sys

from test_plan_tools import SCRIPTS, make_plan

sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402

TAIL = ", then run the printed `wait:` line in the foreground."
BATCH = ("Batch: run each task's Verify command on its own (the red run too), never one run_tests for several tasks; "
         "a `--task Tn` run may use Tn's own tree, which holds Tn's files but not another member's unfinished ones, "
         "so each task's change must work without the other's.")


def verify_lines(msg):
    return [ln for ln in msg.splitlines() if ln.startswith("Verify")]


def test_batch_without_cmd_gets_a_line_per_member(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/test_a.py"}, {"id": "T2", "owns": "src/b.py, tests/test_b.py"}])
    msg = io.task_message(plan, ["T2", "T1"], "/sl/sl", "/sl")
    assert verify_lines(msg) == [
        "Verify T2: `/sl/sl run_tests --fast tests/test_b.py --task T2 --background`" + TAIL,
        "Verify T1: `/sl/sl run_tests --fast tests/test_a.py --task T1 --background`" + TAIL,
    ]
    lines = msg.splitlines()
    assert BATCH in lines and lines.index(BATCH) == lines.index(verify_lines(msg)[-1]) + 1


def test_build_member_and_code_member(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T2", "owns": "Sources/App/AppShell.swift", "tests": "build"}, {"id": "T4", "owns": "src/d.py, tests/test_d.py"}])
    msg = io.task_message(plan, ["T2", "T4"], "/sl/sl", "/sl")
    assert verify_lines(msg) == [
        "Verify T2: `/sl/sl run_tests --full --task T2 --background` (Tests: build, a build check)" + TAIL,
        "Verify T4: `/sl/sl run_tests --fast tests/test_d.py --task T4 --background`" + TAIL,
    ]


def test_docs_only_member_gets_its_own_no_test_line(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "docs/a.md"}, {"id": "T2", "owns": "src/b.py, tests/test_b.py"}])
    msg = io.task_message(plan, ["T1", "T2"], "/sl/sl", "/sl")
    assert verify_lines(msg) == [
        "Verify T1: no test command (no code file in Owns); check that each owned file exists and says what the task asks.",
        "Verify T2: `/sl/sl run_tests --fast tests/test_b.py --task T2 --background`" + TAIL,
    ]


def test_single_task_message_unchanged(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/test_a.py"}, {"id": "T2", "owns": "docs/b.md"}])
    msg = io.task_message(plan, ["T1"], "/sl/sl", "/sl")
    assert verify_lines(msg) == ["Verify: `/sl/sl run_tests --fast tests/test_a.py --task T1 --background`" + TAIL]
    assert "Batch:" not in msg
    assert verify_lines(io.task_message(plan, ["T2"], "/sl/sl", "/sl")) == ["Verify: no test command (no code file in Owns); check that each owned file exists and says what the task asks."]


def test_haiku_batch_gets_the_same_lines(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/test_a.py"}, {"id": "T2", "owns": "src/b.py, tests/test_b.py"}])
    msg = io.task_message(plan, ["T1", "T2"], "/sl/sl", "/sl", tier="haiku")
    assert [ln.split(":", 1)[0] for ln in verify_lines(msg)] == ["Verify T1", "Verify T2"] and BATCH in msg.splitlines()
