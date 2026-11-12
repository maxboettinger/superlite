"""report.py --batches: latest row per batch, text and json, the CLI."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import report  # noqa: E402

REPORT = SCRIPTS / "report.py"

PARKED = {"row": "batch", "batch": "B1", "end": "parked", "lead": {"cost_usd": 1.0}}
SHIPPED = {"row": "batch", "batch": "B1", "end": "shipped",
           "lead": {"cost_usd": 3.0, "turns": 40, "wall_s": 600.0, "blocked_wait_s": 300.0,
                    "kinds": {"wait": {"turns": 20, "cost_usd": 2.0}}},
           "workers": {"implementer": {"n": 2, "cost_usd": 1.0}}, "workers_total": {"n": 2, "cost_usd": 1.0},
           "grade": {"points": 2, "letter": "B"}}
MAIN = {"row": "main", "round": ["B1"], "cost_usd": 0.5, "turns": 9, "kinds": {"wait": {"turns": 9, "cost_usd": 0.5}}}
ROWS = [PARKED, SHIPPED, MAIN]


def test_latest_row_per_batch():
    j = report.batches_json(ROWS)
    assert j["batches"] == [SHIPPED]
    assert j["main"] == [MAIN]
    assert j["total"] == {"batches": 1, "lead_usd": 3.0, "workers_usd": 1.0, "lead_share": 0.75,
                          "main_usd": 0.5, "rounds": 1}
    t = report.batches_text(ROWS)
    assert t.count("B1 ") == 1 and "B1 shipped" in t and "parked" not in t


def test_text_exact():
    assert report.batches_text(ROWS) == (
        "B1 shipped grade B (2) | lead $3.00 40 turns, wall 10.0 min, waits 5.0 min | workers $1.00 "
        "(implementer 2 $1.00) | lead by kind: wait $2.00\n"
        "total: 1 batches, lead $3.00 (75% of lead + workers), workers $1.00; main $0.50 over 1 rounds\n"
        "main B1: $0.50, 9 turns (wait $0.50)\n")
    assert report.batches_text([]) == "report: no batch rows\n"


def test_kinds_top_four_by_cost():
    kinds = {k: {"turns": 1, "cost_usd": c} for k, c in
             [("a", 1.0), ("b", 6.0), ("c", 3.0), ("d", 5.0), ("e", 2.0), ("f", 4.0)]}
    t = report.batches_text([{"row": "batch", "batch": "B2", "end": "shipped", "lead": {"kinds": kinds}}])
    assert "lead by kind: b $6.00, d $5.00, f $4.00, c $3.00" in t
    assert "a $1.00" not in t and "e $2.00" not in t


def test_missing_fields_print_zero():
    t = report.batches_text([{"row": "batch", "batch": "B3", "end": "parked"}])
    assert t.splitlines()[0].startswith("B3 parked grade ? (0) | lead $0.00 0 turns")
    assert "workers $0.00" in t
    j = report.batches_json([{"row": "batch", "batch": "B3"}])
    assert j["total"]["lead_share"] == 0.0


def test_cli_batches_json(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "batch-costs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8")
    cp = run(REPORT, "--batches", "--root", tmp_path, "--json", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert json.loads(cp.out) == report.batches_json(ROWS)
    cp = run(REPORT, "--batches", "--root", tmp_path, cwd=tmp_path)
    assert cp.returncode == 0 and cp.out == report.batches_text(ROWS)
