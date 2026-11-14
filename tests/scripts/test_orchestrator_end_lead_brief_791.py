"""#791: orchestrator end archives the run's briefs but leaves the lead's own briefs in briefs/."""
from __future__ import annotations

import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import findings  # noqa: E402
import orchestrator  # noqa: E402


def briefs(sd: Path, **files: str) -> Path:
    b = sd / "briefs"
    for name, text in files.items():
        p = b / name.replace("__", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return b


def run_dirs(sd: Path) -> list[Path]:
    return sorted(p for p in (sd / "runs").iterdir() if p.is_dir())


def test_kept_names():
    assert orchestrator.KEEP_BRIEFS == ("lead.md", "lead-build.md")


def test_end_keeps_lead_briefs_and_moves_the_rest(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "pool.json").write_text("{}", encoding="utf-8")
    b = briefs(sd, **{"lead.md": "lead\n", "lead-build.md": "build\n", "fix-F-T1-1.md": "fix\n",
                      "research__R1.md": "r\n"})

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: run ended; 2 files moved to ")
    (dest,) = run_dirs(sd)
    assert sorted(p.name for p in b.iterdir()) == ["lead-build.md", "lead.md"]
    assert (b / "lead.md").read_text(encoding="utf-8") == "lead\n"
    assert (b / "lead-build.md").read_text(encoding="utf-8") == "build\n"
    assert (dest / "briefs" / "fix-F-T1-1.md").read_text(encoding="utf-8") == "fix\n"
    assert (dest / "briefs" / "research" / "R1.md").is_file()
    assert not (dest / "briefs" / "lead.md").exists()


def test_end_with_only_the_lead_brief_ends_nothing(tmp_path):
    sd = tmp_path / ".superlite"
    briefs(sd, **{"lead.md": "lead\n"})

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: nothing to end in ")
    assert (sd / "briefs" / "lead.md").read_text(encoding="utf-8") == "lead\n"
    assert not (sd / "runs").exists()


def test_end_without_lead_brief_still_moves_briefs(tmp_path):
    sd = tmp_path / ".superlite"
    briefs(sd, **{"T1.md": "t\n"})

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: run ended; 1 files moved to ")
    (dest,) = run_dirs(sd)
    assert (dest / "briefs" / "T1.md").is_file()
    assert not any((sd / "briefs").iterdir()) if (sd / "briefs").exists() else True


def test_standing_note_survives_end(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "pool.json").write_text("{}", encoding="utf-8")
    briefs(sd, **{"lead.md": f"# Lead brief\n{bb.NOTE_HEAD}\n    keep this line\nEnd.\n", "T1.md": "t\n"})
    before = findings.standing_note(sd)

    orchestrator.end(sd)

    assert before == [bb.NOTE_HEAD, "    keep this line"]
    assert findings.standing_note(sd) == before
