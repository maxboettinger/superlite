"""Claude Code re-attaches only the first 5,000 tokens of a skill after a compaction, so a longer SKILL.md loses its end."""

import fnmatch
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def oversize(root: Path, limit: int = 20000) -> list[str]:
    out = []
    for p in (root / "skills").glob("*/SKILL.md"):
        size = p.stat().st_size
        if size >= limit:
            out.append(f"{p.relative_to(root).as_posix()} {size}")
    return sorted(out)


def dev_files(root: Path) -> list[str]:
    out = []
    for p in (root / "skills").rglob("*"):
        if p.is_file() and (
            p.name == "CREATION-LOG.md" or fnmatch.fnmatch(p.name, "test-*.md") or fnmatch.fnmatch(p.name, "*.log")
        ):
            out.append(p.relative_to(root).as_posix())
    return sorted(out)


def test_oversize_reports_file_at_limit(tmp_path):
    for name, n in (("a", 20000), ("b", 19999)):
        d = tmp_path / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_bytes(b"x" * n)
    assert oversize(tmp_path) == ["skills/a/SKILL.md 20000"]


def test_dev_files_reports_logs_and_scenarios(tmp_path):
    d = tmp_path / "skills" / "a"
    (d / "scripts").mkdir(parents=True)
    for n in ("CREATION-LOG.md", "test-pressure.md", "run.log", "scripts/run_tests.py"):
        (d / n).write_text("x")
    assert dev_files(tmp_path) == [
        "skills/a/CREATION-LOG.md",
        "skills/a/run.log",
        "skills/a/test-pressure.md",
    ]


def test_repo_skills_under_compaction_cut():
    assert oversize(REPO) == []


def test_repo_skills_hold_no_dev_files():
    assert dev_files(REPO) == []
