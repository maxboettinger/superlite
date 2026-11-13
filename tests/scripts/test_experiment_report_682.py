"""report.py experiment statistics: quality, bootstrap interval, verdict, text (#682)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import report  # noqa: E402

TOK = {"input": 10, "cache_read": 100, "cache_write": 20, "output": 30, "thinking": 5}


def row(batch, arm, cost, points=1, config=None, **kw):
    r = {"row": "batch", "batch": batch, "experiment": "e1", "arm": arm,
         "config": config or f"{arm}-0000aaaa",
         "lead": {"cost_usd": cost / 2, "wall_s": 600, "tokens": dict(TOK)},
         "workers_total": {"cost_usd": cost / 2, "tokens": dict(TOK)},
         "grade": {"points": points, "letter": "B"}, "end": "shipped"}
    r.update(kw)
    return r


def exp(min_per_arm=5, margin=10.0):
    return {"id": "e1", "arms": ["default", "cheap"], "configs": {}, "margin": margin, "min_per_arm": min_per_arm}


def arm_rows(arm, costs, points=1, start=1):
    return [row(f"{arm}{i + start}", arm, c, points) for i, c in enumerate(costs)]


DEFAULT = [10.0, 10.2, 9.8, 10.1, 9.9, 10.0]
CHEAP = [6.0, 6.2, 5.8, 6.1, 5.9, 6.0]


def test_quality_of_examples():
    assert report.quality_of({"grade": {"points": 2}}) == 80.0
    assert report.quality_of({"grade": {"points": 12}}) == 0.0
    assert report.quality_of({"quality": 70}) == 70.0
    assert report.quality_of({}) is None


def test_bootstrap_constant():
    assert report.bootstrap_diff([1.0, 1.0, 1.0], [3.0, 3.0, 3.0], seed=1) == (2.0, 2.0, 2.0)


def test_bootstrap_repeatable():
    a, b = [1.0, 2.0, 4.0, 3.0], [2.0, 5.0, 3.0, 6.0]
    r = report.bootstrap_diff(a, b, seed=7)
    assert r == report.bootstrap_diff(a, b, seed=7)
    d, lo, hi = r
    assert lo <= d <= hi


def test_not_enough_data():
    rows = arm_rows("default", DEFAULT[:3]) + arm_rows("cheap", CHEAP[:2])
    rep = report.experiment_report(rows, exp())
    assert rep["enough"] is False
    assert rep["verdict"] == "not enough data: default 3 of 5, cheap 2 of 5 batches; no winner yet"
    text = report.experiment_text(rep)
    assert "not enough data" in text and "verdict: cheap" not in text


def test_cheaper_and_noninferior():
    rows = arm_rows("default", DEFAULT) + arm_rows("cheap", CHEAP)
    rep = report.experiment_report(rows, exp())
    assert rep["enough"] is True
    assert rep["diffs"]["cheap"]["cost_usd"]["hi"] < 0
    assert rep["verdict"].startswith("cheap: cheaper by $4.00 per batch")


def test_quality_worse_keeps_baseline():
    rows = arm_rows("default", DEFAULT, points=0) + arm_rows("cheap", CHEAP, points=5)
    rep = report.experiment_report(rows, exp())
    assert rep["verdict"].startswith("keep default: cheap quality may be worse by more than 10 points")


def test_no_clear_cost_difference():
    same = [10.0, 10.2, 9.8, 10.1, 9.9, 10.0]
    other = [10.0, 9.8, 10.2, 9.9, 10.1, 10.0]
    rep = report.experiment_report(arm_rows("default", same) + arm_rows("cheap", other), exp())
    assert rep["verdict"].startswith("no winner: cheap")


def test_costs_more_keeps_baseline():
    rep = report.experiment_report(arm_rows("default", CHEAP) + arm_rows("cheap", DEFAULT), exp())
    assert rep["verdict"].startswith("keep default: cheap costs $4.00 more per batch")


def test_noise_note():
    rows = [row(f"d{i}", "default", 10.0, quality=92) for i in range(6)]
    rows += [row(f"c{i}", "cheap", 10.0, quality=90) for i in range(6)]
    for r in rows:
        r.pop("grade")
    assert "under 3 points: noise" in report.experiment_text(report.experiment_report(rows, exp()))


def test_excluded_config_mismatch():
    rows = arm_rows("default", DEFAULT) + arm_rows("cheap", CHEAP)
    rows.append(row("B7", "cheap", 99.0, config="default-0000aaaa"))
    rep = report.experiment_report(rows, exp())
    assert rep["excluded"] == [{"batch": "B7", "arm": "cheap", "config": "default-0000aaaa"}]
    assert rep["arms"]["cheap"]["n"] == 6


def test_latest_row_per_batch_and_skipped():
    rows = [row("B1", "default", 1.0), row("B1", "default", 3.0), row("B2", "default", 50.0, end="skipped")]
    rep = report.experiment_report(rows, exp(min_per_arm=1))
    assert rep["arms"]["default"]["n"] == 1
    assert rep["arms"]["default"]["cost_usd"] == 3.0


def test_tokens_by_kind_mean():
    a = row("B1", "default", 2.0)
    b = row("B2", "default", 2.0)
    b["lead"]["tokens"]["cache_read"] = 300
    b["workers_total"]["tokens"]["cache_read"] = 0
    rep = report.experiment_report([a, b], exp(min_per_arm=1))
    assert rep["arms"]["default"]["tokens"]["cache_read"] == (200 + 300) / 2


def test_single_batch_arm_interval():
    rows = [row("B1", "default", 10.0), row("B2", "cheap", 6.0)]
    rep = report.experiment_report(rows, exp(min_per_arm=1))
    c = rep["diffs"]["cheap"]["cost_usd"]
    assert c["diff"] == c["lo"] == c["hi"] == -4.0
    assert rep["verdict"].startswith("cheap: cheaper")


def test_missing_fields_rows():
    bare = {"row": "batch", "batch": "B1", "experiment": "e1", "arm": "default", "end": "shipped"}
    full = row("B2", "default", 4.0)
    rep = report.experiment_report([bare, full], exp(min_per_arm=1))
    a = rep["arms"]["default"]
    assert a["n"] == 2 and a["cost_usd"] == 2.0
    assert a["n_quality"] == 1
    report.experiment_text(rep)


def test_batches_text_config_and_arm():
    r = row("B1", "cheap", 2.0, config="cheap-1a2b3c4d")
    assert report.batches_text([r]).splitlines()[0].endswith("| config cheap-1a2b3c4d | experiment e1 arm cheap")
    plain = {"row": "batch", "batch": "B1", "end": "shipped", "lead": {"cost_usd": 1.0}}
    assert "config" not in report.batches_text([plain]).splitlines()[0]


def test_zero_min_per_arm_without_rows_never_crashes():
    import report
    rep = report.experiment_report([], {"id": "e1", "arms": ["default", "cheap"], "configs": {}, "margin": 10.0, "min_per_arm": 0})
    assert rep["enough"] is True
    assert rep["verdict"].startswith("no winner")


def test_replay_rows_counted_per_arm():
    rows = []
    for arm in ("default", "cheap"):
        for k in (1, 2, 3):
            rows.append({"row": "replay", "batch": f"c1#{k}", "experiment": "e1", "arm": arm,
                         "config": f"{arm}-0000aaaa", "quality": 80, "end": "shipped",
                         "lead": {"cost_usd": 1.0, "wall_s": 60}, "workers_total": {"cost_usd": 1.0}})
    rep = report.experiment_report(rows, exp(min_per_arm=3))
    assert [rep["arms"][a]["n"] for a in ("default", "cheap")] == [3, 3]


def test_bare_arm_config_counts():
    rows = [row("B1", "default", 10.0, config="default"), row("B2", "default", 10.0, config="default"),
            row("B3", "cheap", 6.0, config="cheap"), row("B4", "cheap", 6.0, config="cheap")]
    rep = report.experiment_report(rows, exp())
    assert rep["excluded"] == []
    assert rep["arms"]["default"]["n"] == 2
    assert rep["arms"]["cheap"]["n"] == 2


def test_no_quality_data_no_cheaper_claim():
    def rs(arm, costs):
        out = arm_rows(arm, costs)
        for r in out:
            r["grade"] = {"letter": "B"}
        return out

    rep = report.experiment_report(rs("default", DEFAULT) + rs("cheap", CHEAP), exp())
    assert rep["diffs"]["cheap"]["quality"] is None
    assert rep["verdict"] == "no winner: cheap or default has no quality data"
    assert "cheaper" not in rep["verdict"] and "no clear quality loss" not in rep["verdict"]
