"""#848: the unit suite's dependencies and pytest settings live in the tracked pyproject.toml and uv.lock."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # Python 3.11+

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402


def _toml(name: str) -> dict:
    return tomllib.loads((REPO / name).read_text(encoding="utf-8"))


def _names(reqs) -> set:
    return {re.split(r"[<>=!~\[; ]", r, maxsplit=1)[0].lower() for r in reqs if isinstance(r, str)}


def test_dev_group_holds_pytest_and_xdist():
    assert {"pytest", "pytest-xdist"} <= _names(_toml("pyproject.toml")["dependency-groups"]["dev"])


def test_project_table_is_virtual_with_a_fixed_version():
    data = _toml("pyproject.toml")
    project = data["project"]
    assert project["name"] == "superlite"
    assert project["requires-python"] == ">=3.10"
    assert project["version"] == "0.0.0"
    assert "dynamic" not in project
    assert "build-system" not in data


def test_pytest_settings_keep_tests_and_register_markers():
    ini = _toml("pyproject.toml")["tool"]["pytest"]["ini_options"]
    assert ini["testpaths"] == ["tests"]
    assert "addopts" not in ini
    assert {"slow", "live"} <= {m.split(":", 1)[0].strip() for m in ini["markers"]}


def test_lock_matches_pyproject():
    lock = _toml("uv.lock")
    assert lock["requires-python"] == ">=3.10"
    pkgs = {p["name"]: p for p in lock["package"]}
    assert {"pytest", "pytest-xdist"} <= set(pkgs)
    root = pkgs["superlite"]
    assert root["source"] == {"virtual": "."}
    assert root["version"] == "0.0.0"
    assert {"pytest", "pytest-xdist"} <= {d["name"] for d in root["dev-dependencies"]["dev"]}


def test_full_run_passes_no_path():
    assert testcmd.python_full_args(REPO) == []


def test_testing_doc_names_the_fresh_clone_command():
    text = (REPO / "docs" / "testing.md").read_text(encoding="utf-8")
    assert "## Fresh clone" in text
    assert "uv run --group dev pytest tests/scripts -q -x --co" in text
    assert "uv.lock" in text
    assert text.index("## Fresh clone") < text.index("## Stamps")
