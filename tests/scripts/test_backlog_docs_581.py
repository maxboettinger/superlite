from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "backlog.md").read_text()


def test_lead_end_states_and_acceptance_are_documented():
    for s in ("Status: DONE no-change: <reason>", "Ship without <step>?", "`Refs #N`", "`Unverified: <step> (#N)`", "`Kind: design`",
              "design: awaits plan approval", "UNVERIFIED", "backlog ship B notes", "evidence", "an evals layer red on a case your batch's files do not touch"):
        assert s in DOC, s
    assert "full text in B.notes.md" not in DOC


def test_summary_lines_and_ship_changes_are_documented():
    for s in ("`Decisions:`", "`Attribution:`", "queue place", "first come first served", "`origin/<branch>`", "healthy wait", "cleanup owed", "never runs maxapp ship"):
        assert s in DOC, s
