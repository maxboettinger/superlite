"""#916: memory pressure `warn` alone does not refuse an agent while free memory minus one agent stays above the floor."""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import machine_load as ml  # noqa: E402

G, M = 1 << 30, 1 << 20
HALF_FREE = {"agents": 9, "each": 400 * M, "total": 64 * G, "free": 32 * G, "pressure": "warn"}  # the 15 Nov run


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("SUPERLITE_MACHINE_LIMIT", raising=False)
    monkeypatch.delenv("SUPERLITE_MACHINE_FLOOR", raising=False)


def test_warn_with_half_the_memory_free_has_room():
    assert ml.room(HALF_FREE, 15, 0) is True


def test_critical_still_refuses():
    assert ml.room({**HALF_FREE, "pressure": "critical"}, 15, 0) is False


def test_warn_below_the_floor_still_refuses():
    assert ml.room({**HALF_FREE, "free": 9 * G}, 15, 0) is False


def test_gate_goes_ahead_on_warn_with_half_free(monkeypatch):
    monkeypatch.setattr(ml, "measure", lambda *a, **k: dict(HALF_FREE))
    monkeypatch.setattr(ml.time, "sleep", lambda s: pytest.fail("gate waited on warn with half the memory free"))
    assert ml.gate("fleet spawn (implementer)", 100) is None


def test_measure_names_the_largest_process_outside_the_agent_trees():
    procs = [(10, 1, 400 * M, "claude"), (11, 10, 3 * G, "xcodebuild"), (20, 1, 20 * G, "/usr/libexec/bigd"), (30, 1, 2 * G, "zsh")]
    assert ml.measure(procs=procs, mem={"total": 64 * G, "free": 32 * G, "pressure": "warn"})["other"] == ("bigd", 20 * G)


def test_busy_line_names_the_largest_non_agent_process(monkeypatch):
    low = {**HALF_FREE, "free": 9 * G, "other": ("bigd", 20 * G)}
    monkeypatch.setattr(ml, "measure", lambda *a, **k: dict(low))
    busy = ml.gate("fleet spawn (implementer)", 0)
    assert busy == "machine busy after 0 s: memory pressure warn, 14% free, floor 15% (9 agents, about 0.4 GB each); largest non-agent process bigd 20.0 GB"
