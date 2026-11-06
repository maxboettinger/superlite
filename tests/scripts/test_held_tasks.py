import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import next_tasks  # noqa: E402


def ledger(tmp_path, text):
    p = tmp_path / "progress.md"
    p.write_text(text)
    return p


def test_hold_line_holds(tmp_path):
    assert next_tasks.held_tasks(ledger(tmp_path, "- Hold T5: ssh sign-in on the build host\n")) == {"T5": "ssh sign-in on the build host"}


def test_release_line_releases(tmp_path):
    assert next_tasks.held_tasks(ledger(tmp_path, "- Hold T5: ssh sign-in\n- Release T5\n")) == {}


def test_last_hold_wins(tmp_path):
    assert next_tasks.held_tasks(ledger(tmp_path, "- Hold T5: first\n- Hold T5: second\n")) == {"T5": "second"}


def test_missing_ledger_holds_nothing(tmp_path):
    assert next_tasks.held_tasks(tmp_path / "nope.md") == {}


def test_hold_line_forms(tmp_path):
    text = "* Hold T5a: x\nHold UI3: y\n+ Hold T6:   z  \n- Hold t7: no\n- Holding T8: no\n"
    assert next_tasks.held_tasks(ledger(tmp_path, text)) == {"T5a": "x", "UI3": "y", "T6": "z"}
    assert next_tasks.held_tasks(ledger(tmp_path, "- Hold T5: a\n- Release T50\n")) == {"T5": "a"}


def test_ready_tasks_skips_held(tmp_path):
    g = {"T1": [], "T2": ["T1"], "T3": []}
    t = {"T1": 1, "T2": 1, "T3": 1}
    assert next_tasks.ready_tasks(g, t, [], [], 10, held={"T1": "x"}) == ["T3"]
    assert next_tasks.ready_tasks(g, t, [], [], 10, held=None) == ["T1", "T3"]


def test_short_release_keeps_longer_id_held(tmp_path):
    assert next_tasks.held_tasks(ledger(tmp_path, "- Hold T50: a\n- Hold T5a: b\n- Release T5\n")) == {"T50": "a", "T5a": "b"}
