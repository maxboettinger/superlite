"""#551: a lead pane that is not a shell yet gets one more start after a pause, then one start in a fresh pane."""
import json
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
from test_fleet_spawn_shell_retry import MSG, script, starts
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="scripted start failures need the in-process fake")
SHELL = ("agent_start_failed", MSG)


@pytest.fixture
def pauses(monkeypatch):
    p = []
    monkeypatch.setattr(fleet, "_pause", p.append)
    return p


def lead(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    fleet.main(["on", "--accounts", "claude1,claude3"])
    wt = tmp_path / "wt"; wt.mkdir(exist_ok=True)
    return wt


def panes_opened(world):
    return [c for c in world.fh.calls if c[0] in ("create_workspace", "split_pane", "create_tab")]


def test_start_on_shell_first_start_works(world, pauses):
    assert fleet.start_on_shell("a", "w6:p1", ["x"]) == "" and len(starts(world)) == 1 and pauses == []


def test_start_on_shell_retries_once_after_a_pause(world, pauses):
    script(world, {1: SHELL})
    assert fleet.start_on_shell("a", "w6:p1", ["x"]) == "; retried once"
    assert len(starts(world)) == 2 and pauses == [fleet.SHELL_PAUSE_S]


def test_start_on_shell_second_failure_carries_retried(world, pauses):
    script(world, {1: SHELL, 2: SHELL})
    with pytest.raises(world.fh.HerdrError) as e:
        fleet.start_on_shell("a", "w6:p1", ["x"])
    assert e.value.retried == "; retried once" and e.value.message == MSG and len(pauses) == 1


def test_start_on_shell_non_shell_error_is_not_retried(world, pauses):
    script(world, {1: ("agent_not_ready", "blocked during startup")})
    with pytest.raises(world.fh.HerdrError) as e:
        fleet.start_on_shell("a", "w6:p1", ["x"])
    assert getattr(e.value, "retried", "") == "" and pauses == [] and len(starts(world)) == 1


def test_lead_retries_the_same_pane_after_a_pause(world, tmp_path, monkeypatch, pauses):
    wt = lead(world, tmp_path, monkeypatch); script(world, {1: SHELL})
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    assert r["id"] == "W1" and len(starts(world)) == 2 and pauses == [fleet.SHELL_PAUSE_S] and len(panes_opened(world)) == 1
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"


def test_lead_starts_in_a_fresh_pane_after_two_shell_failures(world, tmp_path, monkeypatch, pauses, capsys):
    wt = lead(world, tmp_path, monkeypatch); capsys.readouterr(); script(world, {1: SHELL, 2: SHELL})
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    out, err = capsys.readouterr()
    workers = json.loads((world.sd / "fleet.json").read_text())["workers"]
    assert r["id"] == "W2" and (workers["W1"]["state"], workers["W2"]["state"]) == ("blocked", "ready")
    assert ("close_pane", "w6:p1") in world.fh.calls and len(panes_opened(world)) == 2 and len(starts(world)) == 3
    assert pauses == [fleet.SHELL_PAUSE_S] and "BLOCKED" not in out
    assert f"W1 startup: {MSG}; retried once; retrying in a fresh pane" in err


def test_lead_blocks_after_the_fresh_pane_fails_too(world, tmp_path, monkeypatch, pauses, capsys):
    wt = lead(world, tmp_path, monkeypatch); capsys.readouterr(); script(world, {1: SHELL, 2: SHELL, 3: SHELL, 4: SHELL})
    with pytest.raises(SystemExit) as e:
        fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    line = [x for x in capsys.readouterr().out.splitlines() if x.startswith("BLOCKED: ")][0]
    assert e.value.code == 3 and line.startswith("BLOCKED: W2 account ")
    assert line.endswith(f"startup: {MSG}; retried once; retried in a fresh pane after W1")
    assert len(starts(world)) == 4 and len(pauses) == 2


def test_other_lead_startup_errors_get_no_fresh_pane(world, tmp_path, monkeypatch, pauses, capsys):
    wt = lead(world, tmp_path, monkeypatch); capsys.readouterr()
    world.fh.start_error = "agent_not_ready"; world.fh.screen = "Select login method\n"
    with pytest.raises(SystemExit):
        fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    out, err = capsys.readouterr()
    assert out.startswith("BLOCKED: W1 ") and "fresh pane" not in out + err
    assert len(starts(world)) == 1 and pauses == [] and len(panes_opened(world)) == 1
