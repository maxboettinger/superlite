"""machine_load (#560, #643): agents admitted by measured memory; an optional count cap."""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import machine_load as ml  # noqa: E402

G, M = 1 << 30, 1 << 20


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("SUPERLITE_MACHINE_LIMIT", raising=False)
    monkeypatch.delenv("SUPERLITE_MACHINE_FLOOR", raising=False)


def test_agent_trees_sum_process_trees():
    procs = [(10, 1, 1000, "/usr/local/bin/claude"), (11, 10, 500, "/bin/zsh"), (12, 11, 2000, "xcodebuild"),
             (20, 1, 300, "claude"), (21, 20, 100, "claude"), (30, 1, 999, "zsh")]
    assert ml.agent_trees(procs) == [3500, 400]


def test_agent_trees_survive_cycles_and_unknown_parents():
    assert sorted(ml.agent_trees([(5, 6, 10, "claude"), (6, 5, 20, "zsh"), (7, 99, 30, "codex"), (0, 0, 5, "kernel_task")])) == [30, 30]


def test_darwin_memory_parse():
    assert ml._darwin(f"{64 * G}\n81\n1\n") == {"total": 64 * G, "free": 64 * G * 81 // 100, "pressure": "normal"}
    assert ml._darwin(f"{64 * G}\n9\n2\n")["pressure"] == "warn"
    assert ml._darwin(f"{64 * G}\n9\n4\n")["pressure"] == "critical"
    assert ml._darwin("garbage") is None


def test_linux_memory_parse():
    meminfo = "MemTotal:       16384000 kB\nMemFree:  100 kB\nMemAvailable:    8192000 kB\n"
    psi = "some avg10=0.50 avg60=0.10 avg300=0.00 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    assert ml._linux(meminfo, psi) == {"total": 16384000 * 1024, "free": 8192000 * 1024, "pressure": "normal"}
    assert ml._linux(meminfo, psi.replace("some avg10=0.50", "some avg10=12.00"))["pressure"] == "warn"
    assert ml._linux(meminfo, psi.replace("full avg10=0.00", "full avg10=10.00"))["pressure"] == "critical"
    assert ml._linux(meminfo, "")["pressure"] == "normal"
    assert ml._linux("MemTotal: 1 kB\n", "") is None


def test_other_agent_clis_are_agents():
    procs = [(10, 1, 100, "/opt/bin/gemini"), (20, 1, 200, "opencode"), (30, 1, 300, "cursor-agent"), (40, 1, 400, "node")]
    assert ml.agent_trees(procs) == [100, 200, 300]


def test_linux_full_below_ten_is_not_critical():
    meminfo = "MemTotal:       16384000 kB\nMemFree:  100 kB\nMemAvailable:    8192000 kB\n"
    psi = "some avg10=0.00 avg60=0 avg300=0 total=0\nfull avg10=7.50 avg60=0 avg300=0 total=0\n"
    assert ml._linux(meminfo, psi)["pressure"] == "normal"


def test_floor_and_limit_sources(monkeypatch):
    assert ml.floor() == (15.0, "default") and ml.limit() == (0, "default")
    f = ml.home() / "machine.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"limit": 16, "floor": 20}))
    assert ml.limit() == (16, str(f)) and ml.floor() == (20.0, str(f))
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "4")
    monkeypatch.setenv("SUPERLITE_MACHINE_FLOOR", "10")
    assert ml.limit() == (4, "SUPERLITE_MACHINE_LIMIT") and ml.floor() == (10.0, "SUPERLITE_MACHINE_FLOOR")


def test_measure_mean_and_default():
    mem = {"total": 64 * G, "free": 52 * G, "pressure": "normal"}
    m = ml.measure(procs=[(10, 1, 600 * M, "claude"), (20, 1, 800 * M, "claude")], mem=mem)
    assert m == {"agents": 2, "each": 700 * M, "total": 64 * G, "free": 52 * G, "pressure": "normal"}
    m0 = ml.measure(procs=[], mem=mem)
    assert m0["agents"] == 0 and m0["each"] == G


def test_xcodebuild_not_counted():
    procs = [(10, 1, 600 * M, "claude")] + [(100 + i, 1, 2 * G, "/usr/bin/xcodebuild") for i in range(5)]
    m = ml.measure(procs=procs, mem={"total": 64 * G, "free": 40 * G, "pressure": "normal"})
    assert m["agents"] == 1 and m["each"] == 600 * M


def test_describe():
    m = {"agents": 23, "each": 750 * M, "total": 64 * G, "free": 7 * G, "pressure": "normal"}
    assert ml.describe(m, 15) == "memory 10% free, floor 15% (23 agents, about 0.7 GB each)"
    assert ml.describe({**m, "pressure": "warn"}, 15) == "memory pressure warn, 10% free, floor 15% (23 agents, about 0.7 GB each)"
    assert ml.describe({**m, "agents": 1}, 15) == "memory 10% free, floor 15% (1 agent, about 0.7 GB each)"
    assert ml.describe({**m, "agents": 0, "each": G}, 15) == "memory 10% free, floor 15% (no agents, 1.0 GB assumed)"
    assert ml.describe({**m, "total": None, "free": None, "pressure": None}, 15) == "memory unknown (23 agents, about 0.7 GB each)"


def test_room():
    m = {"agents": 15, "each": 600 * M, "total": 64 * G, "free": 52 * G, "pressure": "normal"}
    assert ml.room(m, 15, 0) is True
    assert ml.room({**m, "free": 10 * G}, 15, 0) is False
    assert ml.room({**m, "free": 11 * G}, 15, 0) is True
    assert ml.room({**m, "pressure": "warn"}, 15, 0) is False
    assert ml.room(m, 15, 16) is True
    assert ml.room({**m, "agents": 16}, 15, 16) is False
    assert ml.room({**m, "free": 1 * G, "pressure": "critical"}, 0, 0) is True
    assert ml.room({**m, "total": None, "free": None, "pressure": None}, 15, 0) is True


def _measures(monkeypatch, frees):
    it = iter(frees)
    monkeypatch.setattr(ml, "measure", lambda *a, **k: {"agents": 23, "each": 750 * M, "total": 64 * G, "free": next(it), "pressure": "normal"})


def test_gate_busy_line(monkeypatch):
    _measures(monkeypatch, [7 * G])
    assert ml.gate("backlog start B7", 0) == "machine busy after 0 s: memory 10% free, floor 15% (23 agents, about 0.7 GB each)"


def test_gate_waits_then_starts(monkeypatch, capsys):
    _measures(monkeypatch, [7 * G, 7 * G, 40 * G])
    assert ml.gate("fleet spawn (fixer)", 30, poll_s=0) is None
    err = capsys.readouterr().err
    assert [x for x in err.splitlines() if x.startswith("machine busy:")] == [
        "machine busy: memory 10% free, floor 15% (23 agents, about 0.7 GB each); waiting up to 30 s for fleet spawn (fixer)"]
    assert err.count("machine has room after") == 1 and "starting fleet spawn (fixer)" in err


def test_gate_count_cap_names_source(monkeypatch):
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "16")
    monkeypatch.setattr(ml, "measure", lambda *a, **k: {"agents": 16, "each": 600 * M, "total": 64 * G, "free": 52 * G, "pressure": "normal"})
    assert ml.gate("x", 0) == "machine busy after 0 s: memory 81% free, floor 15% (16 agents, about 0.6 GB each); 16 agents of limit 16 from SUPERLITE_MACHINE_LIMIT"


def test_gate_over_limit(monkeypatch, capsys):
    _measures(monkeypatch, [1 * G])
    assert ml.gate("x", 0, over=True) is None
    assert "machine limit overridden (--over-limit): memory 1% free" in capsys.readouterr().err


def test_gate_off_measures_nothing(monkeypatch):
    monkeypatch.setenv("SUPERLITE_MACHINE_FLOOR", "0")
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "0")
    monkeypatch.setattr(ml, "measure", lambda *a, **k: pytest.fail("no measurement when both checks are off"))
    assert ml.gate("x", 0) is None and ml.enabled() is False


def test_snapshot_text(monkeypatch):
    monkeypatch.setattr(ml, "measure", lambda *a, **k: {"agents": 15, "each": 600 * M, "total": 64 * G, "free": 52 * G, "pressure": "normal"})
    assert ml.snapshot_text() == "machine: memory 81% free, floor 15% (15 agents, about 0.6 GB each); no count cap"
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "16")
    assert ml.snapshot_text() == "machine: memory 81% free, floor 15% (15 agents, about 0.6 GB each); 15 agents of limit 16 from SUPERLITE_MACHINE_LIMIT"


def test_ps_survives_non_utf8_names(monkeypatch):
    out = b"10 1 2048 /bin/\xff\xfeclaude\n11 1 1024 codex\n"
    real = ml.subprocess.run

    def fake(cmd, **kw):
        return real([sys.executable, "-c", "import sys; sys.stdout.buffer.write(%r)" % out], **kw)

    monkeypatch.setattr(ml.subprocess, "run", fake)
    procs = ml._ps()
    assert [p[0] for p in procs] == [10, 11]


def test_negative_limit_is_no_cap():
    f = ml.home() / "machine.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"limit": -1}))
    assert ml.limit()[0] == 0


def test_node_script_agent_is_named():
    procs = [(10, 1, 500, "node"), (11, 10, 100, "/bin/zsh"), (20, 1, 300, "node")]
    got = ml._named(procs, {10: "node /opt/homebrew/bin/gemini --yolo", 20: "node /srv/app/server.js"})
    assert got == [(10, 1, 500, "gemini"), (11, 10, 100, "/bin/zsh"), (20, 1, 300, "node")]
    assert ml.agent_trees(got) == [600]


def test_bun_script_with_extension():
    got = ml._named([(5, 1, 100, "/usr/local/bin/bun")], {5: "bun /usr/local/lib/pi.js"})
    assert got == [(5, 1, 100, "pi")]


def test_process_title_agent_is_named():
    assert ml._named([(5, 1, 100, "node")], {5: "claude"}) == [(5, 1, 100, "claude")]
