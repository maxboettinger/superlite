"""#914: the task message counts other tasks' files for non-haiku tiers; the review brief lists its files once."""
import sys
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402

TASKS = [{"id": "T1", "owns": "a.py"}, {"id": "T2", "owns": "b.py, c.py"}, {"id": "T3", "owns": "d.py"}]


def test_task_message_counts_other_files(tmp_path):
    plan = make_plan(tmp_path, TASKS)
    lines = io.task_message(plan, ["T1"], "/sl/sl", "/sl").splitlines()
    assert "Do not touch: any other file (3 files belong to other tasks; the prime's task list names their owners)" in lines
    assert not any(f in "\n".join(lines) for f in ("b.py", "c.py", "d.py"))


def test_task_message_haiku_keeps_the_list(tmp_path):
    plan = make_plan(tmp_path, TASKS)
    assert "Do not touch: b.py, c.py, d.py" in io.task_message(plan, ["T1"], "/sl/sl", "/sl", tier="haiku").splitlines()


def test_task_message_alone_unchanged(tmp_path):
    plan = make_plan(tmp_path, TASKS[:1])
    assert "Do not touch: (nothing else is owned)" in io.task_message(plan, ["T1"], "/sl/sl", "/sl").splitlines()


def test_review_brief_lists_files_once(tmp_path):
    sd = tmp_path / ".superlite"; sd.mkdir()
    plan = make_plan(tmp_path, TASKS)
    out = io.review_brief(sd, plan, ["T2"], "/sl/sl", "/sl")
    assert "Files in scope: b.py, c.py" in out.splitlines()
    assert "Incident hotspots (`/sl/sl incident hotspots --files <the files in scope, comma-joined>`):" in out.splitlines()
    assert out.count("b.py") == 1
