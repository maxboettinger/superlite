"""sl accounts prints each claude-profile account with its headroom, or a usage line (#387)."""
import json, os, subprocess, sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import accounts as ac  # noqa: E402

USAGE = {"accounts": [
    {"name": "claude1", "n": 1, "limits": [{"kind": "session", "percent": 12}, {"kind": "weekly_all", "percent": 40}]},
    {"name": "claude2", "n": 2, "limits": [{"kind": "session", "percent": 95}, {"kind": "weekly_all", "percent": 10}]},
    {"name": "claude3", "n": 3, "error": "token expired"},
    {"name": "claude4", "n": 4, "limits": [{"kind": "session", "percent": 5}, {"kind": "weekly_all", "percent": 20},
                                            {"kind": "weekly_scoped", "label": "Opus", "percent": 100}]}]}


def test_lines_per_account(monkeypatch, capsys):
    monkeypatch.setattr(ac, "read_usage", lambda env=None: USAGE)
    assert ac.main([]) == 0
    assert capsys.readouterr().out.splitlines() == ["claude1 ok 5h=12% weekly=40%", "claude2 skip 5-hour 95%",
                                                    "claude3 skip error token expired", "claude4 ok 5h=5% weekly=20%"]


def test_tier_adds_the_scoped_cap(monkeypatch, capsys):
    monkeypatch.setattr(ac, "read_usage", lambda env=None: USAGE)
    assert ac.main(["--tier", "opus"]) == 0
    assert capsys.readouterr().out.splitlines()[3] == "claude4 skip weekly_scoped Opus 100%"


def test_no_usage_data_prints_usage_and_exits_3(monkeypatch, capsys):
    monkeypatch.setattr(ac, "read_usage", lambda env=None: {})
    assert ac.main([]) == 3
    cap = capsys.readouterr()
    assert cap.out == ""
    assert "accounts: no usage data from claude-profile usage --json" in cap.err and "usage: sl accounts [--tier MODEL]" in cap.err


def test_sl_accounts_runs_main(tmp_path):
    fake = tmp_path / "claude-profile"
    fake.write_text("#!/bin/sh\nif [ \"$1\" = usage ]; then echo '" + json.dumps(USAGE) + "'; exit 0; fi\nexit 1\n")
    fake.chmod(0o755)
    r = subprocess.run([str(SCRIPTS / "sl"), "accounts"], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "SUPERLITE_CLAUDE_PROFILE_BIN": str(fake)})
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "claude1 ok 5h=12% weekly=40%"


def test_nameless_and_non_object_entries(monkeypatch, capsys):
    monkeypatch.setattr(ac, "read_usage", lambda env=None: {"accounts": ["junk", {"limits": []}, {"name": "c", "limits": []}]})
    assert ac.main([]) == 0
    assert capsys.readouterr().out.splitlines() == ["? ok 5h=0% weekly=0%", "c ok 5h=0% weekly=0%"]
