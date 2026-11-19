"""#902: the refusal names the figures that drive it; a gate that gives up says why and what would change it."""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import machine_load as ml  # noqa: E402

G, M = 1 << 30, 1 << 20
MX = {"agents": 9, "each": 400 * M, "total": 64 * G, "free": 9 * G, "pressure": "warn", "swap_total": 2 * G,
      "swap_used": 3 * G // 2, "compressed": G, "other": ("bigd", 20 * G)}
TAIL = "swap 1.5 of 2.0 GB used (0.5 GB free), compressor 1.0 GB (9 agents, about 0.4 GB each); largest non-agent process bigd 20.0 GB"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("SUPERLITE_MACHINE_LIMIT", raising=False)
    monkeypatch.delenv("SUPERLITE_MACHINE_FLOOR", raising=False)


def test_darwin_parses_swap_and_compressor():
    sysctl = "68719476736\n52\n2\ntotal = 2048.00M  used = 1536.00M  free = 512.00M  (encrypted)\n"
    vm = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100.\nPages occupied by compressor: 65536.\n"
    assert ml._darwin(sysctl, vm) == {"total": 68719476736, "free": 35734127902, "pressure": "warn", "swap_total": 2147483648,
                                      "swap_used": 1610612736, "compressed": 1073741824}
    got = ml._darwin(sysctl.replace("2048.00M", "2.00G").replace("1536.00M", "1.50G"), vm)
    assert got["swap_total"] == 2147483648 and got["swap_used"] == 1610612736


def test_darwin_without_swap_line():
    assert ml._darwin("68719476736 52 2") == {"total": 68719476736, "free": 35734127902, "pressure": "warn",
                                              "swap_total": None, "swap_used": None, "compressed": None}


def test_linux_swap():
    meminfo = "MemTotal: 16384000 kB\nMemAvailable: 8192000 kB\nSwapTotal: 2097152 kB\nSwapFree: 524288 kB\n"
    got = ml._linux(meminfo, "")
    assert (got["swap_total"], got["swap_used"], got["compressed"]) == (2147483648, 1610612736, None)
    got = ml._linux("MemTotal: 16384000 kB\nMemAvailable: 8192000 kB\n", "")
    assert (got["swap_total"], got["swap_used"]) == (None, None)


def test_measure_passes_swap_figures(monkeypatch):
    mem = {"total": 64 * G, "free": 32 * G, "pressure": "warn", "swap_total": 2 * G, "swap_used": G, "compressed": 5}
    m = ml.measure(procs=[], mem=mem)
    assert (m["swap_total"], m["swap_used"], m["compressed"]) == (2 * G, G, 5)
    monkeypatch.setattr(ml, "memory", lambda: None)
    m = ml.measure(procs=[], mem=None)
    assert (m["swap_total"], m["swap_used"], m["compressed"]) == (None, None, None)


def test_figures_examples():
    assert ml.figures({"pressure": "warn", "swap_total": 2147483648, "swap_used": 1610612736, "compressed": 1073741824}) == \
        "pressure warn, swap 1.5 of 2.0 GB used (0.5 GB free), compressor 1.0 GB"
    assert ml.figures({"pressure": "normal", "swap_total": 0, "swap_used": 0, "compressed": None}) == "pressure normal, no swap in use"
    assert ml.figures({"pressure": None}) == "pressure unknown"


def test_cause_examples():
    assert ml.cause(MX, 15, 0) == "floor"
    assert ml.cause({**MX, "free": 32 * G, "pressure": "critical"}, 15, 0) == "critical"
    assert ml.cause({**MX, "free": 32 * G}, 15, 8) == "count"
    assert ml.cause({**MX, "free": 32 * G}, 15, 0) is None


def test_refusal_examples():
    assert ml.refusal(MX, 15, 0, "default", "floor") == f"memory 14% free, floor 15%, pressure warn, {TAIL}"
    assert ml.refusal({**MX, "free": 32 * G, "pressure": "critical"}, 15, 0, "default", "critical") == f"memory pressure critical, {TAIL}"
    assert ml.refusal({**MX, "free": 32 * G}, 15, 8, "SUPERLITE_MACHINE_LIMIT", "count") == \
        "memory pressure warn, swap 1.5 of 2.0 GB used (0.5 GB free), compressor 1.0 GB (9 agents, about 0.4 GB each); " \
        "9 agents of limit 8 from SUPERLITE_MACHINE_LIMIT; largest non-agent process bigd 20.0 GB"


def test_refusal_has_no_percent_unless_floor():
    assert "% free" not in ml.refusal({**MX, "free": 32 * G, "pressure": "critical"}, 15, 0, "default", "critical")
    assert "% free" not in ml.refusal({**MX, "free": 32 * G}, 15, 8, "x", "count")
    assert "% free" in ml.refusal(MX, 15, 0, "default", "floor")


def test_gave_up_examples():
    assert ml.gave_up(["critical"] * 3, 240, MX) == \
        "gave up after 3 checks in 240 s: pressure critical at every check; room comes when agents end (9 running) or when bigd (20.0 GB) ends"
    assert ml.gave_up(["floor", "critical"], 10, {**MX, "other": None, "agents": 2}) == \
        "gave up after 2 checks in 10 s: free memory under the floor at 1, pressure critical at 1; room comes when agents end (2 running)"
    assert ml.gave_up(["floor"], 0, {**MX, "agents": 0}) == \
        "gave up after 1 check in 0 s: free memory under the floor; room comes when bigd (20.0 GB) ends"
    assert ml.gave_up(["count"], 0, {**MX, "agents": 0, "other": None}).endswith("agent count at the limit; room comes when memory frees up")


def test_gate_final_line_says_why(monkeypatch):
    m = {**MX, "free": 32 * G, "pressure": "critical"}
    monkeypatch.setattr(ml, "measure", lambda *a, **k: dict(m))
    assert ml.gate("x", 0) == "machine busy after 0 s: " + ml.refusal(m, 15, 0, "default", "critical") + "; " + ml.gave_up(["critical"], 0, m)


def test_describe_adds_swap_and_compressor_only_when_known():
    assert ml.describe(MX, 15) == "memory pressure warn, 14% free, floor 15%, swap 1.5 of 2.0 GB used (0.5 GB free), compressor 1.0 GB (9 agents, about 0.4 GB each)"
