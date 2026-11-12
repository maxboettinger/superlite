"""#627: the lead brief names the verdict command, the build folders and the ship tree rule."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}}
B = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}


def test_build_sentence_names_verdict_and_folders():
    t = bb.lead_brief(B, CTX)
    for s in ("maxapp test", "build pool", "<tree>/.build/DerivedData", ".build/` of the worktree".replace("`", ""),
              "running-app check", "copy this sentence into every worker brief"):
        assert s in t, s
    assert "Build inside your worktree" not in t


def test_ship_sentence_names_tree_rule():
    t = bb.lead_brief(B, CTX)
    assert "TREE: changed" in t and "LAYERS:" in t


def test_not_approved_brief_has_no_tree_rule():
    t = bb.lead_brief(B, {**CTX, "approved": None})
    assert "TREE: changed" not in t and "LAYERS:" not in t
