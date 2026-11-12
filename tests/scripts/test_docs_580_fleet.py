# tests/scripts/test_docs_580_fleet.py: the docs name the one-fleet-per-session rule and the post-run fixer (#580)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"


def test_fleet_md_names_follow():
    t = (SDD / "fleet.md").read_text()
    assert "follows the session" in t
    assert "before a plan, $PLAN is the worktree's .superlite" in t
    assert "fleet: this session's fleet moved from" in (SDD / "scripts" / "fleet.py").read_text()


def test_fixing_md_names_post_run_fixer():
    t = (SDD / "fixing.md").read_text()
    assert "fleet spawn --role fixer --tier T --brief" in t
    assert "plain git commit" in t
