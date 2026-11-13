"""run_config build keys (#699)."""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import experiment  # noqa: E402
import run_config as rc  # noqa: E402


def _txt(lead):
    return json.dumps({"configs": {"x": {"lead": lead}}})


def test_build_keys_accepted():
    rc.load_text(_txt({"build_model": "sonnet", "build_effort": "high"}))
    rc.load_text(_txt({"build_model": None, "build_effort": None}))


def test_build_model_whitespace_refused():
    for bad in ("son net", 3):
        with pytest.raises(rc.ConfigError, match="lead.build_model: must be null or a model string without whitespace"):
            rc.load_text(_txt({"build_model": bad}))


def test_build_effort_refused():
    with pytest.raises(rc.ConfigError, match="huge is not one of low, medium, high, xhigh, max"):
        rc.load_text(_txt({"build_effort": "huge"}))


def test_build_lead_none():
    assert rc.build_lead(rc.resolve("default")) is None


def _cfg(**extra):
    return {"id": "b-1", "lead": {"model": "opus", "effort": "xhigh", "build_model": "sonnet", **extra}, "cache_ttl": {}, "workers": {}}


def test_build_lead_copy():
    arg = _cfg()
    out = rc.build_lead(arg)
    assert out == {"id": "b-1", "lead": {"model": "sonnet", "effort": "xhigh", "build_model": "sonnet"}, "cache_ttl": {}, "workers": {}}
    assert arg["lead"]["model"] == "opus"
    assert rc.build_lead(_cfg(build_effort="high"))["lead"]["effort"] == "high"


def test_default_id_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path))
    assert rc.resolve("default")["id"] == "default-801050ba"


def test_one_factor(tmp_path):
    p = tmp_path / "proj"
    (p / ".superlite").mkdir(parents=True)
    data = {"configs": {"a": {"lead": {"effort": "high"}}, "b": {"lead": {"effort": "high", "build_model": "sonnet"}}}}
    (p / ".superlite" / "run-configs.json").write_text(json.dumps(data))
    assert experiment.config_diff(rc.resolve("a", p), rc.resolve("b", p)) == ["lead.build_model"]
