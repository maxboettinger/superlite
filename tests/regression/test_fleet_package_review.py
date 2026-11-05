"""Package review batch 6 (fleet capacity and dispatch): regressions."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import fleet_state as fs  # noqa: E402
import herdr_client as hc  # noqa: E402


def test_pane_layout_with_a_null_size_is_a_herdr_error_not_a_type_error(monkeypatch):
    bad = {"layout": {"panes": [{"pane_id": "p1", "rect": {"height": None, "width": 10}}]}}
    monkeypatch.setattr(hc, "call", lambda argv: bad)
    with pytest.raises(hc.HerdrError):
        hc.pane_layout("p1")


def test_agent_names_stay_unique_and_valid(tmp_path):
    names = set()
    for parent in ("a", "b"):
        sd = tmp_path / parent / "proj" / ".superlite"
        sd.mkdir(parents=True)
        for wid in ("W1", "W12"):
            n = fs.agent_name(sd, wid)
            assert re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", n) and n.endswith("-" + wid.lower())
            names.add(n)
    assert len(names) == 4
    long = tmp_path / ("x" * 60) / ".superlite"
    long.mkdir(parents=True)
    assert len(fs.agent_name(long, "W99")) <= 32


def test_place_never_splits_a_short_pane_and_opens_a_tab_at_four():
    p = lambda n, r: {"pane_id": n, "rows": r}
    assert fs.place([p("a", 39), p("b", 39)]) == ("tab", None)
    assert fs.place([p("a", 40), p("b", 20)]) == ("down", "a")
    assert fs.place([p(i, 60) for i in "abcd"]) == ("tab", None)
