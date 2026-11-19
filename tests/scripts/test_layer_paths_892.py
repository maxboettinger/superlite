# tests/scripts/test_layer_paths_892.py
"""#892: pyproject.toml and uv.lock move the unit layer; AGENTS.md's unit row lists the MATRIX globs."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_test_layers import tl  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def test_pytest_config_and_lock_map_to_unit_892():
    assert tl.layers_for(["pyproject.toml"]) == ["unit"]
    assert tl.layers_for(["uv.lock"]) == ["unit"]
    assert tl.layers_for(["bench/pyproject.toml", "docs/uv.lock"]) == []


def test_agents_md_unit_row_lists_the_matrix_globs_892():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    row = next(ln for ln in text.splitlines() if ln.startswith("| unit |"))
    assert re.findall(r"`([^`]+)`", row.split("|")[3]) == tl.MATRIX["unit"][0]
    assert tl.MATRIX["unit"][0][-2:] == ["pyproject.toml", "uv.lock"]
