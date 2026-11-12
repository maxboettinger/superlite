"""trees: disk levels and simulator cleanup helpers (#672). simctl is always a stand-in script."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import trees  # noqa: E402

A = "4F1A2B3C-0000-4000-8000-00000000000A"
B = "5B2C3D4E-0000-4000-8000-00000000000B"

STAND_IN = '''
import json, sys
from pathlib import Path
here = Path(__file__).parent
args = sys.argv[1:]
with open(here / "log.txt", "a") as f:
    f.write(" ".join(args) + "\\n")
dev = here / "devices.json"
if args[:2] == ["list", "devices"]:
    if (here / "list_fail").exists():
        print("boom"); sys.exit(1)
    print(dev.read_text()); sys.exit(0)
if args[0] == "delete":
    if (here / "delete_fail").exists():
        sys.stderr.write("Unable to delete\\n"); sys.exit(1)
    d = json.loads(dev.read_text())
    for rt in d["devices"].values():
        rt[:] = [x for x in rt if x["udid"] != args[1]]
    dev.write_text(json.dumps(d))
sys.exit(0)
'''


@pytest.fixture
def sim(tmp_path, monkeypatch):
    script = tmp_path / "simctl.py"
    script.write_text(STAND_IN)
    monkeypatch.setenv("SUPERLITE_SIMCTL", f"{sys.executable} {script}")
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True)

    class Env:
        path = tmp_path
        worktree = wt

        def devices(self, mapping):
            rows = [{"udid": u, "name": n} for u, n in mapping]
            (tmp_path / "devices.json").write_text(json.dumps({"devices": {"rt": rows}}))

        def list(self, text):
            (wt / ".superlite" / "simulators.txt").write_text(text)

        def log(self):
            p = tmp_path / "log.txt"
            return p.read_text().splitlines() if p.exists() else []
    return Env()


def test_disk_levels_defaults(monkeypatch):
    monkeypatch.delenv("SUPERLITE_DISK_FLOOR_GB", raising=False)
    monkeypatch.delenv("SUPERLITE_DISK_WARN_GB", raising=False)
    assert trees.disk_levels() == (20.0, 50.0)


def test_disk_levels_env(monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "0")
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "x")
    assert trees.disk_levels() == (0.0, 50.0)


def test_disk_gate_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "20")
    monkeypatch.setattr(trees, "free_gb", lambda p: 12.0)
    kind, line = trees.disk_gate(tmp_path)
    assert kind == "refuse"
    assert line.startswith("disk: 12.0 GB free on ") and "below the 20 GB floor; " in line


def test_simctl_argv_override(monkeypatch):
    monkeypatch.setenv("SUPERLITE_SIMCTL", "py 'a b' c")
    assert trees.simctl_argv() == ["py", "a b", "c"]
    monkeypatch.setenv("SUPERLITE_SIMCTL", "")
    assert trees.simctl_argv() == ["xcrun", "simctl"]
    monkeypatch.delenv("SUPERLITE_SIMCTL")
    assert trees.simctl_argv() == ["xcrun", "simctl"]


def test_listed_simulators_parses(tmp_path):
    wt = tmp_path / "w"
    (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "simulators.txt").write_text(
        f"{A} booted by T3\n\n# note\niPhone 16 clone\n-rf\n{A.lower()}\n")
    assert trees.listed_simulators(wt) == [A, "iPhone 16 clone"]


def test_listed_simulators_missing(tmp_path):
    assert trees.listed_simulators(tmp_path) == []


def test_remove_by_udid_and_name(sim):
    sim.devices([(A, "sl-check-wt"), (B, "iPhone 16 clone")])
    sim.list(f"{A}\niPhone 16 clone\nold-sim\n")
    assert trees.remove_simulators(sim.worktree) == ([A, "iPhone 16 clone"], ["old-sim"], [])


def test_simctl_missing_program(sim, monkeypatch):
    sim.list(f"{A}\n")
    monkeypatch.setenv("SUPERLITE_SIMCTL", str(sim.path / "no-such-program"))
    removed, gone, owed = trees.remove_simulators(sim.worktree)
    assert removed == [] and gone == []
    assert len(owed) == 1 and owed[0]["sim"] == A and owed[0]["why"].startswith("simctl not runnable: ")


def test_no_file_no_simctl_call(sim):
    assert trees.remove_simulators(sim.worktree) == ([], [], [])
    assert sim.log() == []


def test_ambiguous_name_is_never_deleted(sim):
    sim.devices([(A, "iPhone 16 clone"), (B, "iPhone 16 clone")])
    sim.list("iPhone 16 clone\n")
    removed, gone, owed = trees.remove_simulators(sim.worktree)
    assert removed == [] and gone == []
    assert owed == [{"sim": "iPhone 16 clone", "why": "2 simulators share this name; list its UDID"}]
    assert not any(l.startswith("delete") for l in sim.log())


def test_failed_delete_is_owed(sim):
    sim.devices([(A, "x")])
    sim.list(f"{A}\n")
    (sim.path / "delete_fail").write_text("1")
    removed, gone, owed = trees.remove_simulators(sim.worktree)
    assert removed == [] and owed == [{"sim": A, "why": "delete failed: Unable to delete"}]


def test_shutdown_runs_before_delete(sim):
    sim.devices([(A, "x")])
    sim.list(f"{A}\n")
    trees.remove_simulators(sim.worktree)
    log = sim.log()
    assert log.index(f"shutdown {A}") < log.index(f"delete {A}")


def test_entry_never_reaches_a_shell(sim):
    sim.devices([(A, "x")])
    sim.list("a; touch pwned\n")
    cwd = Path.cwd()
    trees.remove_simulators(sim.worktree)
    assert not (cwd / "pwned").exists() and not (sim.path / "pwned").exists()
    assert not (sim.worktree / "pwned").exists()


def test_list_error_owes_every_entry(sim):
    sim.list(f"{A}\nfoo\n")
    sim.devices([])
    (sim.path / "list_fail").write_text("1")
    removed, gone, owed = trees.remove_simulators(sim.worktree)
    assert removed == [] and gone == []
    assert [o["sim"] for o in owed] == [A, "foo"]
    assert owed[0]["why"] == "simctl list exit 1: boom"


def test_present_simulators(sim):
    sim.devices([(A, "x")])
    assert trees.present_simulators([A, "old-sim"]) == [A]
    assert trees.present_simulators(["x"]) == ["x"]


def test_present_simulators_list_error(sim):
    (sim.path / "list_fail").write_text("1")
    assert trees.present_simulators(["a"]) is None
