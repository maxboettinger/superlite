# tests/scripts/test_docs_b102.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"


def read(p):
    return p.read_text(encoding="utf-8")


def test_sdd_names_in_process_agents():
    t = read(SDD / "SKILL.md")
    line = next(x for x in t.splitlines() if "fleet name" in x)
    assert "`description`" in line and "sl:<repo>-<worktree>-<id>" in line
    assert len(t) <= 11700


def test_fleet_docs_name_the_new_format():
    for p in (SDD / "fleet.md", ROOT / "docs" / "fleet.md"):
        t = read(p)
        assert "sl-<repo>-<worktree>-w" in t and "sl-<run folder>-<hash>" not in t, p
    d = read(ROOT / "docs" / "fleet.md")
    assert "sl:<repo>-<worktree>-<task> Wn" in d and "sl fleet name [ID]" in d


def test_tools_row_names_fleet_name():
    row = next(x for x in read(ROOT / "docs" / "tools.md").splitlines() if x.startswith("| `fleet` |"))
    assert "`name [ID]`" in row
