"""Prune keeps an edge whose producer gets no Wave 0 stub (#796)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS, run
from test_shape import EG, issues, plan, task

sys.path.insert(0, str(SCRIPTS))
import plan_tools as pt  # noqa: E402
import wave0  # noqa: E402

PROD = "lang.parse(src: string) -> Ast"


def make(tmp_path, wave0_none=False):
    p = plan(tmp_path, [task("T1", PROD, eg=[EG]), task("T2", None, PROD)], [("T1", "T2")])
    if wave0_none:
        p.write_text(p.read_text(encoding="utf-8").replace("**Tech stack:**", "**Wave0:** none\n**Tech stack:**", 1), encoding="utf-8")
    return p


def prune(p, tmp_path):
    return run(SCRIPTS / "plan_tools.py", "prune", "--plan", p, cwd=tmp_path).out.strip()


def test_wave0_none_keeps_example_edge(tmp_path):
    p = make(tmp_path, wave0_none=True)
    assert prune(p, tmp_path) == "pruned: no removable edges"
    assert "EDGE:" not in issues(p)
    assert wave0.stubbed_ids(pt.Plan.load(str(p))) == set()


def test_existing_owns_get_no_stub_and_keep_edge(tmp_path):
    p = make(tmp_path)
    root = pt.stable_root(str(p))
    f = root / "src" / "pkg" / "t1.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("", encoding="utf-8")
    try:
        assert wave0.stubbed_ids(pt.Plan.load(str(p)), root) == set()
        assert prune(p, tmp_path) == "pruned: no removable edges"
    finally:
        f.unlink()


def test_stubbed_producer_edge_still_pruned(tmp_path):
    p = make(tmp_path)
    root = pt.stable_root(str(p))
    assert wave0.stubbed_ids(pt.Plan.load(str(p)), root) == {"T1"}
    assert prune(p, tmp_path) == "pruned: T1->T2"
