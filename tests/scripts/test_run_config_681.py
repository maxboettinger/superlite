"""run_config: layered named run configs (#681)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_config as rc  # noqa: E402


def _txt(cfg):
    return json.dumps({"configs": {"x": cfg}})


def _project(tmp_path, data):
    p = tmp_path / "proj"
    (p / ".superlite").mkdir(parents=True)
    (p / ".superlite" / "run-configs.json").write_text(json.dumps(data))
    return p


def _machine(tmp_path, monkeypatch, text):
    h = tmp_path / "home"
    h.mkdir()
    (h / "run-configs.json").write_text(text)
    monkeypatch.setenv("SUPERLITE_HOME", str(h))


def test_unknown_key_is_an_error():
    with pytest.raises(rc.ConfigError, match="unknown key efort"):
        rc.load_text(_txt({"lead": {"efort": "high"}}))


def test_bool_is_not_a_window():
    with pytest.raises(rc.ConfigError):
        rc.load_text(_txt({"lead": {"autocompact": True}}))
    for bad in (99999, 1000001):
        with pytest.raises(rc.ConfigError):
            rc.load_text(_txt({"lead": {"autocompact": bad}}))
    rc.load_text(_txt({"lead": {"autocompact": 400000}}))


def test_ttl_enum():
    with pytest.raises(rc.ConfigError):
        rc.load_text(_txt({"cache_ttl": {"lead": "2h"}}))
    rc.load_text(_txt({"cache_ttl": {"lead": "5m"}}))


def test_workers_role_names():
    with pytest.raises(rc.ConfigError):
        rc.load_text(_txt({"workers": {"reviewer": "sonnet"}}))
    rc.load_text(_txt({"workers": {"final-reviewer": "sonnet"}}))


def test_load_text_examples():
    assert rc.load_text('{"configs": {"low": {"lead": {"effort": "high"}}}}') == {
        "default": None, "configs": {"low": {"lead": {"effort": "high"}}}}
    with pytest.raises(rc.ConfigError) as e:
        rc.load_text('{"configs": {"x": {"lead": {"effort": "huge"}}}}', "p.json")
    assert str(e.value) == "p.json: x: lead.effort: huge is not one of low, medium, high, xhigh, max"
    with pytest.raises(rc.ConfigError) as e:
        rc.load_text("[1]")
    assert str(e.value) == "<text>: not a JSON object"


def test_resolve_default():
    c = rc.resolve()
    assert c["name"] == "default" and c["sources"] == ["builtin"]
    assert c["id"].startswith("default-") and len(c["id"]) == len("default-") + 8
    assert c["lead"]["model"] == "opus" and c["lead"]["effort"] == "xhigh" and c["lead"]["mcp"] == "project"
    assert c["lead"]["text"] == "default" and c["lead"]["autocompact"] is None
    assert "AskUserQuestion" in c["lead"]["deny"] and "Workflow" in c["lead"]["deny"]
    assert c["cache_ttl"] == {"lead": "1h", "workers": "1h"}
    assert c["workers"] == {"implementer": None, "fixer": None, "package-reviewer": None, "final-reviewer": None}


def test_project_beats_machine(tmp_path, monkeypatch):
    _machine(tmp_path, monkeypatch, json.dumps({"configs": {"low": {"lead": {"effort": "medium"}}}}))
    p = _project(tmp_path, {"configs": {"low": {"lead": {"effort": "high"}}}})
    c = rc.resolve("low", p)
    assert c["lead"]["effort"] == "high" and c["lead"]["model"] == "opus"
    assert c["sources"] == ["machine", "project"]


def test_default_name_from_project_file(tmp_path):
    p = _project(tmp_path, {"default": "low", "configs": {"low": {"lead": {"effort": "high"}}}})
    assert rc.resolve(None, p)["name"] == "low"


def test_unknown_name():
    with pytest.raises(rc.ConfigError) as e:
        rc.resolve("nope")
    assert str(e.value) == "run config nope: not defined; known: default"


def test_overrides_change_id():
    a = rc.resolve()
    b = rc.resolve(overrides={"lead": {"model": "sonnet"}})
    assert b["lead"]["model"] == "sonnet" and b["id"] != a["id"]


def test_id_stable_and_value_sensitive(tmp_path):
    p = _project(tmp_path, {"configs": {"default": {"lead": {"effort": "high"}}}})
    assert rc.resolve()["id"] == rc.resolve()["id"]
    assert rc.resolve(None, p)["id"] != rc.resolve()["id"]


def test_write_and_active(tmp_path):
    cfg = rc.resolve()
    assert rc.write_active(tmp_path, cfg) == tmp_path / "run-config.json"
    assert rc.active(tmp_path) == cfg


def test_active_without_snapshot(tmp_path):
    assert rc.active(tmp_path) == rc.resolve(None, None)


def test_broken_snapshot_falls_back(tmp_path, capsys):
    (tmp_path / "run-config.json").write_text("{")
    assert rc.active(tmp_path) == rc.resolve()
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1 and err[0].startswith("run config:")


def test_bad_machine_file_active_falls_back(tmp_path, monkeypatch, capsys):
    _machine(tmp_path, monkeypatch, "[1]")
    sd = tmp_path / "sd"
    sd.mkdir()
    c = rc.active(sd)
    assert c["name"] == "default" and c["sources"] == ["builtin"]
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_cli_show_and_error():
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "run_config.py"), *a], capture_output=True, text=True)
    r = run("show", "--config", "nope")
    assert r.returncode == 2 and r.stderr.strip() == "error: run config nope: not defined; known: default"
    r = run("show")
    assert r.returncode == 0 and json.loads(r.stdout)["name"] == "default"
    r = run("list")
    assert r.returncode == 0 and r.stdout.splitlines() == ["default builtin", "default: default"]
