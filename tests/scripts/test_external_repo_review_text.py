"""Review regressions for the external worker text (B48 T4, plan_tools docstring)."""
from __future__ import annotations

import sys


SCRIPTS = __import__("pathlib").Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plan_tools as pt  # noqa: E402


def test_docstring_names_external():
    assert "external" in pt.__doc__.split("Subcommands implemented here:")[1].splitlines()[0]
