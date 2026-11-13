import stat
import sys

import pytest

from test_backlog_cli import bk, cli  # noqa: F401
from backlog_fixtures import batch
import backlog_cap
import backlog_run
import backlog_state as bs

LINE = "cap: 5 (room 10 cores, 2 per lead; accounts ok)"


@pytest.fixture
def fake(bk, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    calls = {"run": [], "cap": []}
    monkeypatch.setattr(backlog_run, "main", lambda argv: calls["run"].append(list(argv)) or 0)

    def lead_cap(data, root, held=0, tier=None, env=None):
        calls["cap"].append({"held": held, "tier": tier})
        return 5, LINE
    monkeypatch.setattr(backlog_cap, "lead_cap", lead_cap)
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [batch("B1", ["a.py"])]}))
    return calls


def test_start_appends_cap(fake, capsys):
    rc, out = cli(capsys, "start", "--timeout", "9")
    assert rc == 0 and fake["run"] == [["start", "--timeout", "9", "--cap", "5"]]
    assert out.startswith(LINE + "\n")


@pytest.mark.parametrize("args", [["--cap", "3"], ["--cap=3"]])
def test_start_explicit_cap_no_line(fake, capsys, args):
    rc, out = cli(capsys, "start", *args)
    assert fake["run"] == [["start", *args]] and fake["cap"] == [] and "cap:" not in out


def test_start_help_no_cap(fake, capsys):
    cli(capsys, "start", "--help")
    assert fake["run"] == [["start", "--help"]] and fake["cap"] == []


def test_start_in_fleet_worker_no_cap(fake, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "1")
    rc, out = cli(capsys, "start")
    assert fake["run"] == [["start"]] and fake["cap"] == [] and "cap:" not in out


def test_run_appends_cap(fake, capsys):
    rc, out = cli(capsys, "run", "--timeout", "9")
    assert fake["run"] == [["run", "--timeout", "9"]] and "cap:" not in out  # #761: cmd_run reads the cap per round


def test_tier_from_model_flag(fake, capsys):
    cli(capsys, "start", "--model", "sonnet")
    assert fake["cap"][0]["tier"] == "sonnet"


def test_held_passed(fake, bk, capsys):
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [batch("B1", ["a.py"]), batch("B2", ["a.py"])]}))
    cli(capsys, "start")
    assert fake["cap"][0]["held"] == 1


def test_status_ends_with_cap_line(fake, capsys):
    rc, out = cli(capsys, "status")
    assert out.rstrip("\n").splitlines()[-1] == LINE


def test_status_no_planned_no_cap(fake, bk, capsys):
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [batch("B1", ["a.py"], "shipped")]}))
    rc, out = cli(capsys, "status")
    assert "cap:" not in out and out.rstrip("\n").splitlines()[-1] == "next: sl backlog plan"


def test_status_fleet_worker_no_cap(fake, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "1")
    rc, out = cli(capsys, "status")
    assert "cap:" not in out and fake["cap"] == []


def test_start_real_cap_integration(bk, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "1")
    home = tmp_path / "home"
    home.mkdir()
    room = home / "room.py"
    room.write_text("#!/usr/bin/env python3\nprint('{\"room\": 6, \"unit\": \"cores\"}')\n")
    room.chmod(room.stat().st_mode | stat.S_IEXEC)
    (home / "machine.json").write_text('{"room": ["%s"]}' % room)
    cp = home / "cp.py"
    cp.write_text("#!/usr/bin/env python3\nimport json, sys\nif sys.argv[1] == 'usage':\n    print(json.dumps({'accounts': [{'name': 'a1', 'n': 1, 'error': None, 'limits': []}]}))\nelse:\n    print('{}')\n")
    cp.chmod(cp.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("SUPERLITE_CLAUDE_PROFILE_BIN", str(cp))
    monkeypatch.setattr(backlog_cap, "live_leads", lambda: 0)
    runs = []
    monkeypatch.setattr(backlog_run, "main", lambda argv: runs.append(list(argv)) or 0)
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [batch("B1", ["a.py"])]}))
    rc, out = cli(capsys, "start")
    assert runs == [["start", "--cap", "3"]]
    assert out.startswith("cap: 3 (room 6 cores, 2 per lead; accounts ok)\n")


def test_status_passes_run_config_lead_model_as_tier(fake, monkeypatch, capsys):
    import run_config
    monkeypatch.setattr(run_config, "resolve", lambda cfg, root: {"lead": {"model": "opus"}})
    cli(capsys, "status")
    assert fake["cap"][0]["tier"] == "opus"
