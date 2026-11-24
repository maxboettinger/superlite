"""findings route --send starts one fixer worker per brief itself (#1069)."""
import json
import subprocess
import sys

from test_plan_tools import SCRIPTS, make_plan

sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402
import fleet_state as fs  # noqa: E402

LINE = "fixer tier=sonnet brief=/r/.superlite/briefs/fix-F-T1-1.md files=a.py task=T1"


def fake(rcs):
    calls = []

    def run(argv, **kw):
        calls.append(list(argv))
        rc = rcs[len(calls) - 1] if len(calls) <= len(rcs) else 0
        return subprocess.CompletedProcess(argv, rc, "W1 F-T1-1 sent\n", "")
    return run, calls


def test_send_lines_argv(capsys):
    run, calls = fake([0])
    assert findings.send_lines([LINE], "/s/sl", "/r/.superlite", run=run) == 0
    assert calls == [["/s/sl", "fleet", "spawn", "--role", "fixer", "--tier", "sonnet", "--brief", "/r/.superlite/briefs/fix-F-T1-1.md", "--label", "F-T1-1", "--plan", "/r/.superlite"]]
    assert "W1 F-T1-1 sent" in capsys.readouterr().out


def test_send_lines_empty():
    run, calls = fake([])
    assert findings.send_lines([], "/s/sl", "P", run=run) == 0
    assert calls == []


def test_send_failure_exit_code():
    run, calls = fake([3, 0])
    other = LINE.replace("fix-F-T1-1", "fix-F-T2-1").replace("task=T1", "task=T2")
    assert findings.send_lines([LINE, other], "/s/sl", "P", run=run) == 3
    assert len(calls) == 2


def test_send_coordinator_line():
    run, calls = fake([0])
    line = LINE.replace("task=T1", "task=coordinator")
    assert findings.send_lines([line], "/s/sl", "P", run=run) == 0
    assert calls[0][:4] == ["/s/sl", "fleet", "spawn", "--role"]


def test_route_send_flag_parses(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    sd = root / ".superlite"
    sd.mkdir(parents=True)
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}])
    fs.path(sd).write_text(json.dumps({"on": True}), encoding="utf-8")
    sent = []
    monkeypatch.setattr(findings, "route", lambda *a, **k: [LINE])
    monkeypatch.setattr(findings, "send_lines", lambda lines, sl, p, **k: sent.append((lines, sl, p)) or 0)
    assert findings.main(["route", "--plan", str(plan), "--send", "r.json"]) == 0
    assert sent and sent[0][0] == [LINE] and sent[0][2] == str(plan)
    assert sent[0][1].startswith("/") and sent[0][1].endswith("/sl")
    assert capsys.readouterr().out.startswith("fixer tier=")


def test_send_refuses_when_fleet_off(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    sd = root / ".superlite"
    sd.mkdir(parents=True)
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}])
    called = []
    monkeypatch.setattr(findings, "route", lambda *a, **k: called.append(1) or [LINE])
    assert findings.main(["route", "--plan", str(plan), "--send", "r.json"]) == 2
    err = capsys.readouterr().err
    assert "sl fleet on" in err and "--send needs the fleet on" in err
    assert not called and not (sd / "briefs").exists()
