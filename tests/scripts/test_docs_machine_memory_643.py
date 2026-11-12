"""Docs name the memory-based machine gate (#643)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # O(1)


def _row(prefix):
    for line in (ROOT / "docs" / "tools.md").read_text().splitlines():  # O(n)
        if line.startswith(prefix):  # O(1)
            return line  # O(1)
    raise AssertionError(prefix)  # O(1)


def test_fleet_row_names_memory_gate():
    row = _row("| `fleet` |")  # O(n)
    for s in ["SUPERLITE_MACHINE_FLOOR", "default 15", "1 GB", "SUPERLITE_MACHINE_LIMIT",
              "unset or 0 = no cap", "`xcodebuild` processes are not counted",
              "`--over-limit` skips both checks", "--machine-wait S",
              "machine busy after N s: memory"]:  # O(k)
        assert s in row, s  # O(1)
    assert "leads, fixers and xcodebuild" not in row  # O(1)


def test_backlog_run_row_names_same_gate():
    row = _row("| `backlog_run` |")  # O(n)
    assert "same machine gate as `fleet spawn`" in row  # O(1)
    assert "machine busy" in row and "machine: ... parks" in row  # O(1)


def test_fleet_md_capacity_bullet():
    text = (ROOT / "docs" / "fleet.md").read_text()  # O(n)
    sec = text.split("## Capacity", 1)[1].split("\n## ", 1)[0]  # O(n)
    bullets = [b for b in sec.splitlines() if b.startswith("- Machine gate (#560, #643):")]  # O(n)
    assert bullets  # O(1)
    for s in ["kern.memorystatus_vm_pressure_level", "MemAvailable", "/proc/pressure/memory",
              "15%", '{"floor": P}', '{"limit": N}', "sl fleet status"]:  # O(k)
        assert bullets[0].count(s) >= 1, s  # O(1)
