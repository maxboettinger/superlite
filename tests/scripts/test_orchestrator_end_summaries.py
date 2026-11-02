"""orchestrator end: per-run test summaries (test-summary-*.json, test-summary-*.log, test-summary.latest) are archived."""
from __future__ import annotations

import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import orchestrator  # noqa: E402


def touch(sd: Path, *names: str) -> None:
    sd.mkdir(parents=True, exist_ok=True)
    for n in names:
        (sd / n).write_text("{}", encoding="utf-8")


def run_dirs(sd: Path) -> list[Path]:
    return sorted(p for p in (sd / "runs").iterdir() if p.is_dir())


def test_end_moves_run_summaries(tmp_path):
    sd = tmp_path / ".superlite"
    touch(sd, "pool.json", "test-summary.json", "test-summary-a.json", "test-summary-a.log", "test-summary.latest")
    touch(sd, "test-cmd.json", "checkpoints.json")
    (sd / "probes").mkdir()

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: run ended; 5 files moved to ")
    (dest,) = run_dirs(sd)
    assert line.endswith(str(dest))
    for n in ("pool.json", "test-summary.json", "test-summary-a.json", "test-summary-a.log", "test-summary.latest"):
        assert (dest / n).is_file(), n
        assert not (sd / n).exists(), n


def test_end_only_summaries(tmp_path):
    sd = tmp_path / ".superlite"
    touch(sd, "test-summary-a.json")

    line = orchestrator.end(sd)

    assert line.startswith("orchestrator: run ended; 1 files moved to ")
    (dest,) = run_dirs(sd)
    assert (dest / "test-summary-a.json").is_file()
    assert not (sd / "test-summary-a.json").exists()


def test_end_keeps_config_and_probes(tmp_path):
    sd = tmp_path / ".superlite"
    touch(sd, "pool.json", "test-summary-a.json", "test-cmd.json", "checkpoints.json")
    (sd / "probes").mkdir()

    orchestrator.end(sd)

    assert (sd / "test-cmd.json").is_file()
    assert (sd / "checkpoints.json").is_file()
    assert (sd / "probes").is_dir()


def test_end_nothing_to_end(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()

    line = orchestrator.end(sd)

    assert line == f"orchestrator: nothing to end in {sd}"
    assert not (sd / "runs").exists()
