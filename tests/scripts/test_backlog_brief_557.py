"""#557: main's answers reach a lead as orchestrator rulings; shipped summaries say who answered each decision."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

B = {"id": "B4", "topic": "t", "issues": [7], "files": ["a.py"], "version": "1.0", "pr": 9}
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "o/r", "approved": {"by": "AskUserQuestion", "time": "T0"}}
Q = "How should reviewers and fixers avoid sharing a build folder and test target on a compiled stack?"
A = "Isolated tree per worker as --task does, with the base checkpoint and every change (Recommended)"


def test_main_head_names_orchestrator_rulings():
    assert bb.MAIN_HEAD.startswith("Main's rulings (orchestrator rulings: main decided these as AI orchestrator, not Max;")
    t = bb.lead_brief({**B, "answers": {"Q?": "x"}, "answered_by": {"Q?": "main"}}, CTX)
    assert "Max's decisions: none\n" + bb.MAIN_HEAD + "\n- Q?: x\n" + bb.ATTRIBUTION + "\n" in t


def test_attribution_rule_in_every_brief():
    mine = {**B, "answers": {"Q?": "x"}, "answered_by": {"Q?": "user"}}
    for b, ctx in ((B, CTX), (mine, CTX), (B, {**CTX, "approved": None})):
        assert bb.ATTRIBUTION in bb.lead_brief(b, ctx)
    t = bb.lead_brief(mine, CTX)
    assert t.index("Max's decisions:\n- Q?: x") < t.index(bb.ATTRIBUTION) < t.index("Rulings from shipped batches")
    for s in ("notes.md", "pr-body.md", "commit messages", "Max's decisions", "by", "`Decisions:`", "(Max)", "never as Max's"):
        assert s in bb.ATTRIBUTION, s


def test_decisions_line_names_who_answered():
    b = {**B, "answers": {"Keep the v1 API?": "Drop (Recommended)", "Lock path?": "Per tree"},
         "answered_by": {"Keep the v1 API?": "user", "Lock path?": "main"}}
    assert bb.decisions_line(b) == "Decisions: Keep the v1 API?: Drop (Max); Lock path?: Per tree (main's ruling)"
    assert bb.decisions_line(B) is None
    assert bb.decisions_line({**B, "answers": {"Q?": "x"}}) is None
    assert bb.decisions_line({**B, "answers": {"Q?": "x"}, "answered_by": {"Q?": "bot"}}) is None


def test_decisions_line_cuts_at_words_drops_control_characters_and_caps_entries():
    b = {**B, "answers": {Q: A}, "answered_by": {Q: "main"}}
    assert bb.decisions_line(b) == ("Decisions: How should reviewers and fixers avoid sharing a build folder: "
                                    "Isolated tree per worker as --task does, with the (main's ruling)")
    odd = {"Q\x1b[2J?": "a\nb"}
    assert bb.decisions_line({**B, "answers": odd, "answered_by": {"Q\x1b[2J?": "user"}}) == "Decisions: Q[2J?: a b (Max)"
    six = {f"Q{i}?": "x" for i in range(6)}
    line = bb.decisions_line({**B, "answers": six, "answered_by": {k: "user" for k in six}})
    assert line == "Decisions: " + "; ".join(f"Q{i}?: x (Max)" for i in range(4)) + "; +2 more"


def test_summary_carries_the_decisions_line_after_the_head():
    b = {**B, "answers": {"Lock path?": "Per tree"}, "answered_by": {"Lock path?": "main"}}
    assert bb.summary(b, "Ruling: ok\n").splitlines() == [
        "B4 shipped: #7", "PR: #9", "Version: 1.0", "Decisions: Lock path?: Per tree (main's ruling)", "Ruling: ok"]


def test_summary_with_decisions_stays_at_ten_lines():
    b = {**B, "answers": {"Lock path?": "Per tree"}, "answered_by": {"Lock path?": "user"}}
    six = bb.summary(b, "\n".join(f"n{i}" for i in range(6))).splitlines()
    assert len(six) == 10 and six[3] == "Decisions: Lock path?: Per tree (Max)" and six[9] == "n5"
    nine = bb.summary(b, "\n".join(f"n{i}" for i in range(9))).splitlines()
    assert len(nine) == 10 and nine[8] == "n4" and nine[9] == "+4 more note lines: sl backlog ship B4 notes prints them"
    plain = bb.summary(B, "\n".join(f"n{i}" for i in range(7))).splitlines()
    assert len(plain) == 10 and plain[9] == "n6"
