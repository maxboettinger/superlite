"""#302: stable_partition names every unstable dep; #306: gantt labels hold no brackets and pass lint."""
from __future__ import annotations

import json
import re

from test_plan_tools import make_plan, pt  # puts the scripts folder on sys.path

import next_tasks  # noqa: E402
import plan_tools  # noqa: E402

IDS = ("T1", "T2", "T3", "T4", "T5")
LATER_ROUND = [("T1", "T3"), ("T5", "T3"), ("T4", "T5")]  # T3 is visited before T5 turns unstable


def _plan(tmp_path, edges):
    return plan_tools.Plan.load(str(make_plan(tmp_path, [{"id": i, "time": 2} for i in IDS], edges)))


def _issue(tid):
    return plan_tools.Issue(f"LINT: {tid} is broken", tasks=(tid,))


def _reasons(fix):
    return {f["task"]: f["reasons"] for f in fix}


def test_reason_names_dep_that_turns_unstable_in_a_later_round(tmp_path):
    stable, fix, _ = plan_tools.stable_partition(_plan(tmp_path, LATER_ROUND), [_issue("T1"), _issue("T4")], [])
    reasons = _reasons(fix)
    assert reasons["T3"] == ["depends on unstable T1, T5"]
    assert reasons["T5"] == ["depends on unstable T4"]
    assert stable == ["T2"]


def test_own_reasons_first_then_one_depends_line(tmp_path):
    issues = [_issue("T1"), _issue("T3"), _issue("T4")]
    _, fix, _ = plan_tools.stable_partition(_plan(tmp_path, LATER_ROUND), issues, [])
    reasons = _reasons(fix)
    assert reasons["T3"] == ["LINT: T3 is broken", "depends on unstable T1, T5"]
    assert sum(r.startswith("depends on unstable") for rs in reasons.values() for r in rs) == 2


def test_stable_deps_are_not_named(tmp_path):
    stable, fix, _ = plan_tools.stable_partition(_plan(tmp_path, [("T1", "T3"), ("T2", "T3")]), [_issue("T1")], [])
    assert _reasons(fix)["T3"] == ["depends on unstable T1"]
    assert stable == ["T2", "T4", "T5"]


def test_lapse_waits_for_every_named_dep(tmp_path):
    _, fix, _ = plan_tools.stable_partition(_plan(tmp_path, LATER_ROUND), [_issue("T1"), _issue("T4")], [])
    assert "T3" not in next_tasks.lapsed_fix(fix, ["T1"])
    assert "T3" in next_tasks.lapsed_fix(fix, ["T1", "T5"])


def test_lint_stable_json_names_later_round_dep(tmp_path):
    ghost = "ghost(x: int) -> int"
    tasks = [{"id": "T1", "time": 5, "consumes": ghost}, {"id": "T2", "time": 2}, {"id": "T3", "time": 2},
             {"id": "T4", "time": 2, "consumes": ghost}, {"id": "T5", "time": 2}]
    cp = pt("lint", "--stable", "--plan", make_plan(tmp_path, tasks, LATER_ROUND))
    data = json.loads((tmp_path / ".superlite" / "stable.json").read_text(encoding="utf-8"))
    reasons = _reasons(data["fix"])
    assert "depends on unstable T1, T5" in reasons["T3"], cp.both
    assert "depends on unstable T4" in reasons["T5"], cp.both


def _gantt_lines(text):
    return [ln for ln in text.splitlines() if re.search(r" :t\d+, \d+, \d+s$", ln)]


def _schedule(tmp_path, title):
    p = make_plan(tmp_path, [{"id": "T1", "time": 2, "title": title}])
    cp = pt("schedule", "--plan", p, "--insert")
    assert cp.returncode == 0, cp.both
    lines = _gantt_lines(p.read_text(encoding="utf-8"))
    assert len(lines) == 1, lines
    return p, lines[0]


def test_gantt_label_cut_inside_braces_stays_balanced(tmp_path):
    p, line = _schedule(tmp_path, "Fix the stable reason list {name every dep}")
    assert line.startswith("  T1 Fix the stable reason list name every :t1, 0, "), line
    assert "unbalanced" not in pt("lint", "--plan", p).both


def test_gantt_label_strips_lone_brackets_and_collapses_spaces(tmp_path):
    p, line = _schedule(tmp_path, "Add [x] flag: {y} mode; #3, done ] {")
    assert line.startswith("  T1 Add x flag y mode 3 done :t1, 0, "), line
    assert "unbalanced" not in pt("lint", "--plan", p).both


def test_gantt_label_never_ends_in_a_space(tmp_path):
    _, line = _schedule(tmp_path, "a" * 36 + " tail")
    assert line.startswith("  T1 " + "a" * 36 + " :t1, 0, "), line


def test_gantt_label_keeps_parentheses(tmp_path):
    p, line = _schedule(tmp_path, "Parse (a) values")
    assert line.startswith("  T1 Parse (a) values :t1, 0, "), line
    assert "unbalanced" not in pt("lint", "--plan", p).both
