# tests/scripts/test_backlog_run_disk_sims_672.py: start disk floor and simulator cleanup (#672)
import json, sys, types
from pathlib import Path
import pytest
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import trees  # noqa: E402
import backlog_state as bs  # noqa: E402

UDID = "4F1A2B3C-0000-4000-8000-00000000000A"
STAND_IN = """import json, sys
from pathlib import Path
d = Path(__file__).parent
args = sys.argv[1:]
with open(d / "simctl.log", "a") as f:
    f.write(" ".join(args) + "\\n")
devs = json.loads((d / "devices.json").read_text())
if args[:3] == ["list", "devices", "-j"]:
    print(json.dumps({"devices": {"rt": [{"udid": u, "name": n} for u, n in devs.items()]}}))
elif args[:1] == ["delete"]:
    devs.pop(args[1], None)
    (d / "devices.json").write_text(json.dumps(devs))
"""

@pytest.fixture
def simctl(tmp_path, monkeypatch):
    s = tmp_path / "simctl_standin"; s.mkdir()
    (s / "stand.py").write_text(STAND_IN); (s / "devices.json").write_text(json.dumps({UDID: "sl-check"}))
    monkeypatch.setenv("SUPERLITE_SIMCTL", f"{sys.executable} {s / 'stand.py'}")
    if not hasattr(trees, "remove_simulators"):
        def fake(wt):
            if not (Path(wt) / ".superlite" / "simulators.txt").is_file():
                return [], [], []
            with open(s / "simctl.log", "a") as f:
                f.write(f"shutdown {UDID}\ndelete {UDID}\n")
            return [UDID], [], []
        monkeypatch.setattr(trees, "remove_simulators", fake, raising=False)
    return s

def log_of(s):
    f = s / "simctl.log"
    return f.read_text().splitlines() if f.is_file() else []

def lowdisk(monkeypatch, gb):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "20"); monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "50")
    monkeypatch.setattr(trees, "free_gb", lambda path: gb[0])

def gate_spy(monkeypatch, calls):
    import machine_load
    monkeypatch.setattr(machine_load, "gate", lambda *a, **k: calls.append(a) or "")

def test_start_below_floor_starts_nothing(bk, capsys, monkeypatch):
    gb = [12.0]; lowdisk(monkeypatch, gb); calls = []; gate_spy(monkeypatch, calls)
    put(bk, b("B7", ["a.py"]), b("B8", ["b.py"]))
    rc, out = run(capsys, "start", "B7", "B8", "--cap", "2")
    lines = out.splitlines()
    assert rc == 2 and len(lines) == 2
    for bid, line in zip(("B7", "B8"), lines):
        assert line.startswith(f"BLOCKED: waiting for disk: {bid} not started: 12.0 GB free on ")
        assert f"below the 20 GB floor; run sl trees clean (trees, orphaned Xcode DerivedData) and free space, then rerun sl backlog start {bid} ({bid} keeps its state)" in line
        assert "disk: " not in line.split("not started: ")[1]
    assert not any(c[0] in ("spawn", "fleet", "send") for c in bk.calls) and calls == []
    for bid in ("B7", "B8"):
        assert get(bk, bid)["state"] == "planned" and not get(bk, bid).get("worktree")

def test_start_after_space_frees(bk, capsys, monkeypatch):
    gb = [12.0]; lowdisk(monkeypatch, gb); gate_spy(monkeypatch, [])
    put(bk, b("B7", ["a.py"]))
    assert run(capsys, "start", "B7")[0] == 2
    gb[0] = 100.0
    rc, out = run(capsys, "start", "B7", "--cap", "2")
    assert rc == 0 and out.startswith("B7 running lead=W1") and get(bk, "B7")["state"] == "running"

def test_warn_line_prints_and_batch_starts(bk, capsys, monkeypatch):
    gb = [30.0]; lowdisk(monkeypatch, gb); gate_spy(monkeypatch, [])
    put(bk, b("B7", ["a.py"]))
    rc, out = run(capsys, "start", "B7")
    assert rc == 0 and "WARNING: 30.0 GB free" in out and "B7 running" in out

def test_parked_batch_keeps_its_reason(bk, capsys, monkeypatch):
    gb = [12.0]; lowdisk(monkeypatch, gb); gate_spy(monkeypatch, [])
    put(bk, b("B7", ["a.py"], "parked", reason="tui red", worktree=str(bk.root / ".claude" / "worktrees" / "superlite-b7-t")))
    rc, out = run(capsys, "start", "B7")
    assert rc == 2 and "waiting for disk: B7 not started" in out
    x = get(bk, "B7")
    assert x["state"] == "parked" and x["reason"] == "tui red"

def test_cleanup_removes_listed_simulator(bk, capsys, simctl):
    wt = bk.root / "wt"; (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "simulators.txt").write_text(UDID + "\n")
    put(bk, b("B1", ["a.py"], "shipped", worktree=str(wt)))
    assert br.project_cleanup(bk.root, wt, "superlite/b1-t", "B1") is None
    assert capsys.readouterr().out == f"B1 simulators: removed 1: {UDID}\n"
    log = log_of(simctl)
    assert any(x.startswith("shutdown") for x in log) and any(x.startswith("delete") for x in log)

def test_owed_recorded_and_returned(bk, capsys, simctl, monkeypatch):
    wt = bk.root / "wt"; (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "simulators.txt").write_text(UDID + "\n")
    put(bk, b("B1", ["a.py"], "shipped", worktree=str(wt)))
    owed = [{"sim": UDID, "why": "delete failed: Unable to delete"}]
    monkeypatch.setattr(trees, "remove_simulators", lambda w: ([], [], owed), raising=False)
    ret = br.project_cleanup(bk.root, wt, "superlite/b1-t", "B1")
    line = br.simulators_owed_line("B1", owed)
    assert ret is None and line == f"B1 simulators owed: {UDID} (delete failed: Unable to delete); delete each with xcrun simctl delete <udid>, then sl backlog status"
    assert json.loads(bs_path(bk).read_text())["batches"][0]["simulators_owed"] == owed
    assert br.stored_owed_line(bk.root, "B1") == line
    # once nothing is owed any more, the key goes away
    monkeypatch.setattr(trees, "remove_simulators", lambda w: ([UDID], [], []), raising=False)
    assert br.project_cleanup(bk.root, wt, "superlite/b1-t", "B1") is None
    assert "simulators_owed" not in get(bk, "B1")

def bs_path(bk):
    return bk.root / ".superlite" / "backlog.json"

def test_owed_line_examples():
    assert br.simulators_owed_line("B2", [{"sim": "a", "why": "x"}, {"sim": "b", "why": "y"}]) == "B2 simulators owed: a (x), b (y); delete each with xcrun simctl delete <udid>, then sl backlog status"

def test_owed_line_joins_cleanup_failure(bk, capsys, monkeypatch):
    wt = bk.root / "wt"; wt.mkdir()
    put(bk, b("B1", ["a.py"], "shipped", worktree=str(wt)))
    (bk.root / ".superlite" / "cleanup-cmd.json").write_text(json.dumps({"cleanup": "exit 3"}))
    owed = [{"sim": "a", "why": "x"}]
    monkeypatch.setattr(trees, "remove_simulators", lambda w: ([], [], owed), raising=False)
    ret = br.project_cleanup(bk.root, wt, "br", "B1")
    assert ret == "B1 project cleanup: exit 3" and br.stored_owed_line(bk.root, "B1") == br.simulators_owed_line("B1", owed)

def test_no_file_no_simctl_call(bk, capsys, simctl):
    wt = bk.root / "wt"; (wt / ".superlite").mkdir(parents=True)
    put(bk, b("B1", ["a.py"], "shipped", worktree=str(wt)))
    assert br.project_cleanup(bk.root, wt, "br", "B1") is None
    assert capsys.readouterr().out == "" and log_of(simctl) == []

def test_shipped_names_owed_after_open(bk, capsys, monkeypatch):
    wt = bk.root / "wt"; wt.mkdir()
    owed = [{"sim": "a", "why": "x"}]
    put(bk, b("B1", ["a.py"], "running", worktree=str(wt), cleaned=True, open_issues=[5], simulators_owed=owed))
    out = br._shipped(bs_path(bk), bk.sd, bk.root, get(bk, "B1"), None)
    i = next(i for i, x in enumerate(out) if x.startswith("B1 OPEN"))
    assert out[i + 1] == br.simulators_owed_line("B1", owed)


def test_shipped_prints_owed_once(bk, capsys, monkeypatch):
    wt = bk.root / "wt"; wt.mkdir()
    owed = [{"sim": "a", "why": "x"}]
    monkeypatch.setattr(trees, "remove_simulators", lambda w: ([], [], owed), raising=False)
    for cleaned in (True, False):
        put(bk, b("B1", ["a.py"], "running", worktree=str(wt), cleaned=cleaned, simulators_owed=owed))
        out = br._shipped(bs_path(bk), bk.sd, bk.root, get(bk, "B1"), None)
        assert out.count(br.simulators_owed_line("B1", owed)) == 1

def test_drop_worktree_owed_once(bk, capsys, monkeypatch):
    wt = bk.root / "wt"; wt.mkdir()
    owed = [{"sim": "a", "why": "x"}]
    put(bk, b("B1", ["a.py"], "shipped", worktree=str(wt)))
    monkeypatch.setattr(trees, "remove_simulators", lambda w: ([], [], owed), raising=False)
    monkeypatch.setattr(br, "remove_worktree", lambda *a, **k: ["B1 worktree removed"])
    out = br.drop_worktree(bk.root, get(bk, "B1"))
    assert out.count(br.simulators_owed_line("B1", owed)) == 1 and len(out) == 2
