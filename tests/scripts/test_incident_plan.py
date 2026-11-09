import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[2] / "skills"
              / "subagent-driven-development" / "scripts")
sys.path.insert(0, SCRIPTS)
import incident  # noqa: E402

SL = str(Path(SCRIPTS) / "sl")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for v in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    L = tmp_path / "i.jsonl"
    assert incident.main(["add", "--file", "a.py", "--line", "3", "--context", "c", "--log", str(L)]) == 0
    assert incident.main(["add", "--file", "b.py", "--line", "5", "--context", "c", "--log", str(L)]) == 0
    other = tmp_path / "other" / ".superlite"
    return L, other


def test_hotspots_accepts_plan_anywhere(env, capsys):
    L, other = env
    capsys.readouterr()
    assert incident.main(["hotspots", "--log", str(L)]) == 0
    base = capsys.readouterr().out
    assert len(base.splitlines()) == 2
    for argv in (["hotspots", "--log", str(L), "--plan", str(other)],
                 ["--plan", str(other), "hotspots", "--log", str(L)],
                 ["hotspots", "--plan=" + str(other), "--log", str(L)],
                 ["hotspots", "--log", str(L), "--plan", "x", "--plan=y"]):
        assert incident.main(argv) == 0
        assert capsys.readouterr().out == base


def test_add_with_plan_writes_only_the_log(env):
    L, other = env
    assert incident.main(["add", "--file", "c.py", "--line", "1", "--context", "x",
                          "--log", str(L), "--plan", str(other)]) == 0
    assert len(L.read_text().splitlines()) == 3
    assert not other.exists()


def test_resolve_and_summary_accept_plan(env, capsys):
    L, other = env
    assert incident.main(["resolve", "--file", "a.py", "--line", "3", "--ruling", "r",
                          "--log", str(L), "--plan", str(other)]) == 0
    capsys.readouterr()
    assert incident.main(["summary", "--log", str(L), "--plan=" + str(other)]) == 0
    assert capsys.readouterr().out.startswith("total: 3")


@pytest.mark.parametrize("tail", [["--log", "{L}", "--plan"], ["--plan", "--log", "{L}"]])
def test_valueless_plan_is_usage_error(env, capsys, tail):
    L, _ = env
    capsys.readouterr()
    assert incident.main(["hotspots"] + [t.replace("{L}", str(L)) for t in tail]) == 2
    cap = capsys.readouterr()
    assert cap.err == "usage: incident.py add|resolve|hotspots|summary ... [--plan P]\n"
    assert cap.out == ""


def test_help_names_plan(capsys):
    with pytest.raises(SystemExit) as e:
        incident.main(["--help"])
    assert e.value.code == 0
    assert "--plan P (anywhere): accepted and ignored" in capsys.readouterr().out


def test_sl_incident_hotspots_with_plan(env, tmp_path):
    L, _ = env
    r = subprocess.run([SL, "incident", "hotspots", "--files", "a.py", "--log", str(L),
                        "--plan", ".superlite"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "unrecognized arguments" not in r.stderr
    out = r.stdout.splitlines()
    assert len(out) == 1 and json.loads(out[0])["file"] == "a.py"
