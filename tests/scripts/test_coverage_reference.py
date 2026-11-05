from pathlib import Path

REF = Path(__file__).resolve().parents[2] / "skills" / "brainstorming" / "coverage.md"


def _rows():
    lines = REF.read_text(encoding="utf-8").split("\n")
    start = lines.index("## Categories")
    rows = []
    fenced = False
    for line in lines[start + 1:]:
        if line.startswith("```"):
            fenced = not fenced
        if fenced or not line.startswith("|"):
            continue
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows[2:]


def test_categories_table():
    rows = _rows()
    assert len(rows) == 14
    assert rows[0][0] == "Scope and success criteria"
    assert rows[2][0] == "Persistence and migration"
    assert rows[6][0] == "Error handling and recovery"
    assert rows[13][0] == "Research unknowns"
    for r in rows:
        assert len(r) == 2 and all(r)


def test_procedure_names_states_and_rules():
    text = REF.read_text(encoding="utf-8")
    for s in ["`settled`", "`ruled`", "`n/a`", "`spike`", "`open`", "## Coverage",
              "AskUserQuestion", "**Coverage:** off", ".superlite/coverage.md",
              "sl coverage check", "COVERAGE:", "Unattended"]:
        assert s in text, s


def test_present_user_is_attended():
    text = REF.read_text(encoding="utf-8")
    assert "A user who says they are present is attended" in text
    assert "rule only when the call fails" in text
