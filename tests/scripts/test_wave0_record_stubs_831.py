"""Prune keeps the edge to a consumer the run's Wave 0 record never stubbed (#831)."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run
from test_shape import EG, plan, task

sys.path.insert(0, str(SCRIPTS))
import plan_tools as pt  # noqa: E402
import wave0  # noqa: E402

PROD = "lang.parse(src: string) -> Ast"


def make(tmp_path):
    return plan(tmp_path, [task("T1", PROD, eg=[EG]), task("T2", None, PROD)], [("T1", "T2")])


def record(p, body):
    f = wave0.sl_dir(str(p)) / "briefs" / "wave0.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")


def meta(stubs):
    return {"id": "T0", "synthetic": True, "title": "Wave 0 skeleton", "owns": [], "stubs": stubs, "wait": []}


def stubbed(p):
    return wave0.stubbed_ids(pt.Plan.load(str(p)), pt.stable_root(str(p)))


def prune(p, tmp_path):
    return run(SCRIPTS / "plan_tools.py", "prune", "--plan", p, cwd=tmp_path).out.strip()


def test_record_without_the_stub_keeps_the_edge(tmp_path):
    p = make(tmp_path)
    record(p, meta([]))
    assert stubbed(p) == set()
    assert prune(p, tmp_path) == "pruned: no removable edges"


def test_record_with_the_stub_still_prunes(tmp_path):
    p = make(tmp_path)
    record(p, meta(["src/pkg/t1.py"]))
    assert stubbed(p) == {"T1"}
    assert prune(p, tmp_path) == "pruned: T1->T2"


def test_no_record_keeps_todays_answer(tmp_path):
    assert stubbed(make(tmp_path)) == {"T1"}


def test_malformed_record_keeps_todays_answer(tmp_path):
    p = make(tmp_path)
    record(p, {"id": "T0"})
    assert stubbed(p) == {"T1"}
    record(p, "{not json")
    assert stubbed(p) == {"T1"}
