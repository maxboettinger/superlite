from pathlib import Path

DOC = ((Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "backlog-main.md").read_text(encoding="utf-8") + "\n" + (Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8"))


def test_release_and_unit_layer_are_explained():
    assert "lock not held" in DOC
    assert "run_tests --full" in DOC and "--layer unit" in DOC


def test_plan_and_undo_lines_are_documented():
    for s in ("fast path", "already shipped:", "check:", "not found:", "offer:", "unskip", "reset B [--discard]", "--help", "reopened", "latest comments", "low memory"):
        assert s in DOC, s
