# tests/scripts/test_backlog_steps_checks_674.py
import copy
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

CMD = "command: 1 to 300 characters, one line"


def prop(steps=None, **kw):
    b = {"id": "B1", "topic": "t", "issues": [12], "files": ["a.py"], "depends": []}
    if steps is not None:
        b["main_steps"] = steps
    b.update(kw)
    return {"batches": [b]}


def test_check_step_ok():
    s = {"runs": "main", "command": "git lfs install", "why": "LFS hooks"}
    assert bc.check_step(s, "B1 main_steps 1") == (s, [])


def test_check_step_errors():
    assert bc.check_step({"runs": "lead", "command": ""}, "x") == (None, ["x runs: main or user", "x " + CMD])


def test_check_step_drops_unknown():
    got = bc.check_step({"issues": [12], "runs": "user", "command": "gh auth login", "sudo": True}, "B1 main_steps 1", [12, 13])
    assert got == ({"issues": [12], "runs": "user", "command": "gh auth login"}, [])


def test_check_step_issues_subset():
    err = ["w issues: a non-empty list of this batch's issues"]
    assert bc.check_step({"issues": [99], "runs": "main", "command": "c"}, "w", [12]) == (None, err)
    assert bc.check_step({"issues": [12], "runs": "main", "command": "c"}, "w", []) == (None, err)


def test_command_one_line():
    assert bc.check_step({"runs": "main", "command": "a\nb"}, "w") == (None, ["w " + CMD])
    assert bc.check_step({"runs": "main", "command": "c" * 301}, "w") == (None, ["w " + CMD])
    assert bc.check_step({"runs": "main", "command": "c" * 300}, "w")[1] == []


def test_why_limits():
    e = ["w why: 0 to 200 characters, one line"]
    assert bc.check_step({"runs": "main", "command": "c", "why": "x" * 201}, "w") == (None, e)
    assert bc.check_step({"runs": "main", "command": "c", "why": "a\x07"}, "w") == (None, e)


def test_not_an_object():
    assert bc.check_step("x", "w") == (None, ["w: not an object"])


def q(opt):
    return {"questions": [{"question": "Q", "header": "H", "options": [opt, {"label": "B"}]}]}


def test_option_runs_needs_command():
    errs = bc.check_question(q({"label": "A", "runs": "main"}))
    assert "q1 option 1 command: 1 to 300 characters, one line" in errs


def test_clean_question_keeps_option_step():
    c = bc.clean_question(q({"label": "A", "runs": "main", "command": "x", "junk": 1}))
    assert c["questions"][0]["options"][0] == {"label": "A", "runs": "main", "command": "x"}


def test_proposal_main_steps_stored():
    st = [{"issues": [12], "runs": "main", "command": "git lfs install", "why": "LFS"}]
    out, errs = bc.check_proposal(prop(st), {12})
    assert errs == [] and out[0]["main_steps"] == st
    for p in (prop([]), prop()):
        out, errs = bc.check_proposal(p, {12})
        assert errs == [] and "main_steps" not in out[0]


def test_proposal_main_steps_errors():
    assert bc.check_proposal(prop("x"), {12})[1] == ["B1: main_steps must be a list"]
    nine = [{"issues": [12], "runs": "main", "command": "c"}] * 9
    assert "B1: main_steps: at most 8 entries" in bc.check_proposal(prop(nine), {12})[1]
    bad = [{"issues": [12], "runs": "lead", "command": "c"}]
    assert "B1 main_steps 1 runs: main or user" in bc.check_proposal(prop(bad), {12})[1]


def test_step_line():
    assert bc.step_line({"runs": "main", "command": "git lfs install"}) == "main runs this: git lfs install"
    assert bc.step_line({"runs": "user", "command": "gh auth login"}) == "Max runs this: gh auth login"


def test_ask_shape():
    inp = {"questions": [{"question": "Store assets?", "header": "Assets", "options": [
        {"label": "Git LFS (Recommended)", "description": "main installs git-lfs", "runs": "main", "command": "git lfs install"},
        {"label": "Plain git", "description": "no tool"}]}]}
    keep = copy.deepcopy(inp)
    out, lines = bc.ask_shape(inp)
    assert inp == keep
    assert out["questions"][0]["options"] == [{"label": "Git LFS (Recommended)", "description": "main installs git-lfs"},
                                              {"label": "Plain git", "description": "no tool"}]
    assert lines == ['step: "Store assets?" / "Git LFS (Recommended)": main runs this: git lfs install']
    plain = {"questions": [{"question": "Q", "header": "H", "multiSelect": False, "options": [{"label": "A"}, {"label": "B"}]}]}
    assert bc.ask_shape(plain) == (plain, [])


def test_runs_unhashable_is_an_error():
    assert bc.check_step({"runs": ["main"], "command": "c"}, "w") == (None, ["w runs: main or user"])
    assert bc.check_step({"runs": {"a": 1}, "command": "c"}, "w") == (None, ["w runs: main or user"])
    out, lines = bc.ask_shape(q({"label": "A", "runs": ["main"], "command": "x"}))
    assert lines == [] and "runs" not in out["questions"][0]["options"][0]


def test_option_step_error_names_its_own_position():
    twin = {"label": "A", "runs": "lead", "command": "x"}
    errs = bc.check_question({"questions": [{"question": "Q", "header": "H", "options": [{"label": "B", "runs": "lead", "command": "x"}, dict(twin)]}]})
    assert "q1 option 1 runs: main or user" in errs and "q1 option 2 runs: main or user" in errs
    same = {"label": "A", "runs": "lead", "command": "x"}
    errs = bc.check_question({"questions": [{"question": "Q", "header": "H", "options": [same, dict(same)]}]})
    assert "q1 option 2 runs: main or user" in errs
