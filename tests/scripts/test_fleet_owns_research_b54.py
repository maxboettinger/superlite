"""Fleet task message: own files never under Do not touch (#364); research workers default to sonnet (#374)."""
import sys
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402


def test_own_files_never_in_do_not_touch(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/guard.py, tests/test_t1.py"}, {"id": "T2", "owns": "src/guard.py, tests/test_t2.py"},
                                {"id": "T3", "owns": "src/c.py, tests/test_t1.py"}], edges=[("T1", "T2")])
    lines = io.task_message(plan, ["T2"], "/sl/sl", "/sl").splitlines()
    assert "Owns: src/guard.py, tests/test_t2.py" in lines
    assert "Do not touch: tests/test_t1.py, src/c.py" in lines


def test_batch_owns_cover_every_member(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py, src/a.py"}, {"id": "T3", "owns": "src/a.py, src/b.py"}])
    assert "Do not touch: (nothing else is owned)" in io.task_message(plan, ["T1", "T2"], "/sl/sl", "/sl").splitlines()


def test_research_defaults_to_sonnet_and_takes_a_haiku_pin():
    r = fr.launch("research", None, routing.load_cfg())
    assert r["model"] == "sonnet" and r["argv"][:4] == ["--agent", "superlite:researcher", "--model", "sonnet"]
    h = fr.launch("research", "haiku", routing.load_cfg())
    assert h["model"] == "haiku" and h["argv"][:4] == ["--agent", "superlite:researcher", "--model", "haiku"]
