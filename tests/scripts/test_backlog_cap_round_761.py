# tests/scripts/test_backlog_cap_round_761.py: the lead cap is read per start round (#761)
import sys
import pytest
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run  # noqa: F401
from test_backlog_run_loop_673 import clock  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_cap  # noqa: E402


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "0")
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


def loop(bk, monkeypatch, caps, rounds=2):
    """cmd_run with cmd_start recording a.cap; _round is non-urgent until the last round."""
    got, calls = [], []
    monkeypatch.setattr(br, "cmd_start", lambda a: got.append(a.cap) or 0)
    seq = iter([["B9 shipped x"]] * (rounds - 1) + [["B9 parked: x"]])
    monkeypatch.setattr(br, "_round", lambda *a: next(seq))
    if caps is not None:
        it = iter(caps)
        monkeypatch.setattr(backlog_cap, "start_cap", lambda *a, **k: calls.append(a) or next(it))
    return got, calls


def test_start_cap_fixed(bk):
    assert backlog_cap.start_cap(bk.root) == (2, "cap: 2 (fixed cap 2: machine.json names no room command; accounts unknown (no usage data))")


def test_start_cap_tier(bk, monkeypatch):
    import run_config
    seen = []
    monkeypatch.setattr(backlog_cap, "lead_cap", lambda data, root, **k: seen.append(k) or (1, "x"))
    backlog_cap.start_cap(bk.root, model="sonnet")
    assert seen[-1]["tier"] == "sonnet"
    def boom(*a, **k):
        raise RuntimeError("no config")
    monkeypatch.setattr(run_config, "resolve", boom)
    backlog_cap.start_cap(bk.root)
    assert seen[-1]["tier"] is None


def test_run_rereads_cap_each_round(bk, capsys, clock, monkeypatch):
    put(bk, b("B1", ["a.py"]))
    got, _ = loop(bk, monkeypatch, [(1, "cap: 1 (a)"), (2, "cap: 2 (b)")])
    rc, out = run(capsys, "run", "--timeout", "60", "--poll", "0")
    assert got == [1, 2] and out.count("cap: 1 (a)") == 1 and out.count("cap: 2 (b)") == 1


def test_run_same_cap_prints_once(bk, capsys, clock, monkeypatch):
    put(bk, b("B1", ["a.py"]))
    got, _ = loop(bk, monkeypatch, [(2, "cap: 2 (a)"), (2, "cap: 2 (b)")])
    rc, out = run(capsys, "run", "--timeout", "60", "--poll", "0")
    assert got == [2, 2] and len([x for x in out.splitlines() if x.startswith("cap: 2")]) == 1


def test_run_explicit_cap_skips_reading(bk, capsys, clock, monkeypatch):
    put(bk, b("B1", ["a.py"]))
    got, calls = loop(bk, monkeypatch, [])
    run(capsys, "run", "--cap", "3", "--timeout", "60", "--poll", "0")
    assert got == [3, 3] and calls == []


def test_run_no_planned_skips_reading(bk, capsys, clock, monkeypatch):
    put(bk, b("B1", ["a.py"], "shipped"))
    got, calls = loop(bk, monkeypatch, [])
    run(capsys, "run", "--timeout", "60", "--poll", "0")
    assert calls == [] and got[0] == backlog_cap.FIXED_CAP


def test_run_route_passes_no_cap(bk, capsys, monkeypatch):
    import backlog
    seen = []
    monkeypatch.setattr(backlog, "_root", lambda: bk.root)
    monkeypatch.setattr(br, "main", lambda argv=None: seen.append(list(argv)) or 0)
    assert backlog.main(["run"]) == 0 and seen == [["run"]]
    assert "cap:" not in capsys.readouterr().out
    backlog.main(["start"])
    assert "--cap" in seen[-1]


def test_cap_default_none(monkeypatch):
    seen = []
    monkeypatch.setattr(br, "cmd_start", lambda a: seen.append(a) or 0)
    monkeypatch.setattr(br, "cmd_run", lambda a: seen.append(a) or 0)
    br.main(["start"]); br.main(["run"])
    assert [a.cap for a in seen] == [None, None]
    assert "[--cap N]" in br.__doc__ and "--cap 2" not in br.__doc__


def test_cmd_start_reads_cap_when_none(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"]))
    monkeypatch.setattr(backlog_cap, "start_cap", lambda *a, **k: (1, "cap: 1 (z)"))
    picked = []
    monkeypatch.setattr(br, "_pick", lambda data, bids, cap, live: picked.append(cap) or ([], []))
    run(capsys, "start")
    assert picked == [1]
    br.main(["start"])
    assert "cap: 1 (z)" in capsys.readouterr().out
