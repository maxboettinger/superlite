"""B95 (#451): SDD fleet.md, SKILL.md, fixing.md and the package reviewer name 1.5.82 to 1.5.100."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
FLEET = (SDD / "fleet.md").read_text(encoding="utf-8")
SKILL = (SDD / "SKILL.md").read_text(encoding="utf-8")
FIXING = (SDD / "fixing.md").read_text(encoding="utf-8")
PKG = (ROOT / "agents" / "package-reviewer.md").read_text(encoding="utf-8")


def has(text, *tokens):
    missing = [t for t in tokens if t not in text]
    assert not missing, missing


def test_fleet_md():
    has(FLEET, "--for-review", "--package", "review: Tn", "dropped", "another account", "ASKED", "concerns=N",
        "--full")


def test_skill_reviews_and_probes():
    has(SKILL, "--for-review", "review:", "--dismiss")


def test_skill_stays_under_cap():
    assert len(SKILL) <= 11700


def test_fixing_md():
    has(FIXING, "--dismiss", 'results["dismissed"]', "ADAPTER:", "RUN:", "probe files committed")


def test_package_reviewer():
    has(PKG, "probe_run --plan", "--dismiss")
