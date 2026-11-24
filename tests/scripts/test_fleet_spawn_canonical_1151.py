"""#1151: a start Herdr refuses because the pane's terminal is still in canonical mode (a start line over its line limit
before the shell prompt) is a pane that is not a shell yet: one pause, one more start, then one start in a fresh pane."""
import json
import os
from pathlib import Path

import pytest
from test_fleet import world  # noqa: F401  (world is a fixture)
from test_fleet_for_dispatch import dwld, FRESH, _go  # noqa: F401
from test_fleet_spawn_shell_retry import MSG, script, starts
from test_fleet_lead_shell_551 import lead
from test_fleet_restore_577 import w, idle_agent, fr  # noqa: F401  (w is a fixture)
import fleet
import fleet_lead as fl

REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted start failures need the in-process fake")
ROOT = Path(__file__).resolve().parents[2]
CANON = ("input contains a 1190-byte line but the terminal is in canonical mode with a 1024-byte limit; "
         "wait for the shell prompt and retry")
REFUSED = ("agent_start_failed", CANON)


@pytest.fixture
def pauses(monkeypatch):
    p = []
    monkeypatch.setattr(fleet, "_pause", p.append)
    return p


def test_no_shell_matches_both_refusals():
    assert fleet.CANON_MSG == "terminal is in canonical mode" and fleet.SHELL_MSGS == (fleet.SHELL_MSG, fleet.CANON_MSG)
    assert fleet.no_shell(MSG) and fleet.no_shell(CANON)
    assert not fleet.no_shell("blocked during startup") and not fleet.no_shell("") and not fleet.no_shell(None)


def test_start_on_shell_retries_the_canonical_refusal(world, pauses):
    script(world, {1: REFUSED})
    assert fleet.start_on_shell("a", "w6:p1", ["x"]) == "; retried once"
    assert len(starts(world)) == 2 and pauses == [fleet.SHELL_PAUSE_S]


def test_spawn_retries_the_canonical_refusal_on_the_same_pane(world, pauses):
    fleet.main(["on"]); script(world, {1: REFUSED})
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"
    assert len(starts(world)) == 2 and pauses == [fleet.SHELL_PAUSE_S]


def test_spawn_starts_a_fresh_pane_after_two_canonical_refusals(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr(); script(world, {1: REFUSED, 2: REFUSED})
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W2"
    err = capsys.readouterr().err
    assert f"W1 startup: {CANON}; retried once; retrying in a fresh pane" in err
    assert len(starts(world)) == 3 and pauses == [fleet.SHELL_PAUSE_S]
    assert any(c[0] == "close_pane" for c in world.fh.calls)


def test_spawn_blocks_after_the_fresh_pane_is_refused_too(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(world, {n: REFUSED for n in (1, 2, 3, 4)})
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    line = capsys.readouterr().out.splitlines()[0]
    assert e.value.code == 3 and line.startswith("BLOCKED: W2 account ")
    assert line.endswith(f"startup: {CANON}; retried once; retried in a fresh pane after W1")
    assert len(starts(world)) == 4 and len(pauses) == 2


def test_other_startup_errors_still_get_no_retry(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(world, {1: ("agent_start_failed", "the terminal refused the line")})
    with pytest.raises(SystemExit):
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    out = capsys.readouterr().out
    assert out.startswith("BLOCKED: ") and "retried" not in out
    assert len(starts(world)) == 1 and pauses == []


def test_for_dispatch_names_the_rerun_on_a_canonical_refusal(dwld, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(dwld, {n: REFUSED for n in (1, 2, 3, 4)})
    dwld.lines = [("T2", FRESH), ("T3", FRESH)]
    assert _go(dwld) == 3
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("BLOCKED: T2 not sent (")
    assert out[0].endswith(f"{CANON}; retried once; retried in a fresh pane after W1; rerun sl fleet spawn --for-dispatch)")
    assert out[1:] == ["W3 T3 sent"]


def test_lead_starts_in_a_fresh_pane_after_two_canonical_refusals(world, tmp_path, monkeypatch, pauses, capsys):
    wt = lead(world, tmp_path, monkeypatch); capsys.readouterr(); script(world, {1: REFUSED, 2: REFUSED})
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    out, err = capsys.readouterr()
    workers = json.loads((world.sd / "fleet.json").read_text())["workers"]
    assert r["id"] == "W2" and (workers["W1"]["state"], workers["W2"]["state"]) == ("blocked", "ready")
    assert len(starts(world)) == 3 and pauses == [fleet.SHELL_PAUSE_S] and "BLOCKED" not in out
    assert f"W1 startup: {CANON}; retried once; retrying in a fresh pane" in err


def test_restore_retries_the_canonical_refusal(w):
    w.fake.agents = [idle_agent()]
    w.fake.start_errors = [REFUSED]
    lines, blocked = w.run()
    assert not blocked and lines[0].startswith("W1 restored") and w.pauses == [fr.fleet.SHELL_PAUSE_S]
    assert sum(1 for c in w.fake.calls if c[0] == "start_agent") == 2


def test_docs_name_the_canonical_refusal():
    fleet_md = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    bullet = next(x for x in fleet_md.splitlines() if "terminal is in canonical mode" in x)
    assert bullet.startswith("- ") and "(#1151)" in bullet and "fleet restore" in bullet
    row = next(x for x in (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines() if x.startswith("| `fleet` |"))
    assert "`not an available shell` or Herdr's canonical-mode refusal (`terminal is in canonical mode`, #1151)" in row
    assert "only when the reason holds `not an available shell` or `terminal is in canonical mode`" in row
