"""guard_tools.capture_hint: the no-capture hint for a variable captured from sl output (#1069)."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import guard_tools as gt  # noqa: E402

SL = "SL=/u/skills/subagent-driven-development/scripts/sl; "


def test_eval_of_captured_wait_line():
    cmd = SL + "w=$(\"$SL\" run_tests --full --background 2>&1 | sed -n 's/^wait: //p'); eval \"$w\""
    assert gt.capture_hint(cmd, "eval $w: text the guard cannot resolve") == gt.RUN_TESTS_CAPTURE_HINT


def test_route_brief_through_a_second_variable():
    cmd = SL + "OUT=$($SL findings route --plan P r.json); B=$(echo \"$OUT\" | sed -n 's/.*brief=\\([^ ]*\\).*/\\1/p'); echo x >> \"$B\""
    assert gt.capture_hint(cmd, "$B") == gt.ROUTE_CAPTURE_HINT


def test_absolute_sl_path_and_braces():
    cmd = "R=$(/u/skills/subagent-driven-development/scripts/sl findings route --plan P r.json | tail -1); cat >> \"${R}\""
    assert gt.capture_hint(cmd, "${R}") == gt.ROUTE_CAPTURE_HINT


def test_backtick_capture():
    cmd = "w=`sl run_tests --full --background | grep wait:`; eval \"$w\""
    assert gt.capture_hint(cmd, "eval $w: text the guard cannot resolve") == gt.RUN_TESTS_CAPTURE_HINT


def test_for_loop_over_route_output():
    cmd = SL + "for id in $($SL findings route --plan P r.json | grep -o 'F-[^ ]*'); do echo x > .superlite/briefs/fix-$id.md; done"
    assert gt.capture_hint(cmd, ".superlite/briefs/fix-$id.md") == gt.ROUTE_CAPTURE_HINT


def test_other_sl_tool():
    cmd = "T=$(sl plan_tools packet --plan P); cat \"$T\" > x"
    assert gt.capture_hint(cmd, "$T") == gt.SL_CAPTURE_HINT.format(tool="plan_tools")


def test_not_from_sl():
    assert gt.capture_hint("B=$(awk '{print $1}' f); echo x > \"$B\"", "$B") == ""
    assert gt.capture_hint("echo x > \"$B\"", "$B") == ""
    assert gt.capture_hint("B=$(slow run_tests); echo > $B", "$B") == ""


def test_chain_depth_cap():
    cmd = "A=$(sl run_tests --full); B=$(echo $A); C=$(echo $B); D=$(echo $C); E=$(echo $D); F=$(echo $E); eval \"$F\""
    assert gt.capture_hint(cmd, "eval $F: text the guard cannot resolve") == ""
    assert gt.capture_hint(cmd, "eval $D: text the guard cannot resolve") == gt.RUN_TESTS_CAPTURE_HINT


def test_quoted_paren_in_substitution():
    cmd = "B=$(sl findings route --plan \"P (1)\" r.json | tail -1); echo x >> \"$B\""
    assert gt.capture_hint(cmd, "$B") == gt.ROUTE_CAPTURE_HINT


def test_garbage_never_raises():
    for cmd, word in (("B=$(", "$B"), ("", ""), ("B=`sl run_tests", "$B"), ("$(((", "$(")):
        assert isinstance(gt.capture_hint(cmd, word), str)
