"""reviewer_eval.py: pure case loading, pooling, scoring and summary."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))
import reviewer_eval as re_  # noqa: E402


def F(fp, line=1):
    return {"fp": fp, "file": "x.py", "line": line, "problem": "p" + fp, "quote": "q" + fp}


FOUND = {"a": [F("f1"), F("f2")], "b": [F("f2"), F("f3")]}
GRADES = {"f1": {"grade": "real", "serious": True}, "f2": {"grade": "real", "serious": False}, "f3": {"grade": "wrong", "serious": False}}
STATS = {"a": {"unverified": 0, "cost_usd": 1.0}, "b": {"unverified": 2, "cost_usd": 0.5}}


def test_score_example():
    assert re_.score(FOUND, GRADES, STATS) == {
        "a": {"real": 2, "serious": 1, "nit": 0, "wrong": 0, "ungraded": 0, "unverified": 0, "recall": 1.0, "precision": 1.0, "cost_usd": 1.0},
        "b": {"real": 1, "serious": 0, "nit": 0, "wrong": 1, "ungraded": 0, "unverified": 2, "recall": 0.5, "precision": 0.5, "cost_usd": 0.5},
    }


def test_score_without_real_findings():
    out = re_.score({"a": [F("f1")], "b": []}, {"f1": {"grade": "nit", "serious": False}}, {})
    assert out["a"]["recall"] is None and out["a"]["precision"] is None and out["a"]["nit"] == 1
    assert out["b"]["recall"] is None and out["b"]["precision"] is None
    assert out["b"]["cost_usd"] == 0.0 and out["b"]["unverified"] == 0


def test_ungraded_and_unknown_grades():
    found = {"a": [F("f1"), F("f2"), F("f3")]}
    grades = {"f1": {"grade": "real", "serious": False}, "f3": {"grade": "maybe", "serious": True}, "zz": {"grade": "real", "serious": True}}
    a = re_.score(found, grades, {})["a"]
    assert (a["real"], a["ungraded"], a["serious"]) == (1, 2, 0)
    assert a["recall"] == 1.0 and a["precision"] == 1.0


def test_pool_hides_variants_and_is_stable():
    out = re_.pool(FOUND)
    assert [e["fp"] for e in out] == ["f1", "f2", "f3"]
    assert all(set(e) == {"fp", "file", "line", "problem", "quote"} for e in out)
    assert re_.pool({"b": FOUND["b"], "a": FOUND["a"]}) == out


def test_parse_variant():
    assert re_.parse_variant("fast=sonnet:medium") == {"name": "fast", "model": "sonnet", "effort": "medium"}
    for bad in ("sonnet", "=sonnet:high", "n=:high", "n=sonnet:", "n=sonnet", ""):
        with pytest.raises(ValueError):
            re_.parse_variant(bad)


def _case(**kw):
    c = {"id": "c1", "repo": "/r", "base": "b", "merge": "m", "title": "t", "body": "x"}
    c.update(kw)
    return c


def _write(d, cases):
    d.mkdir(exist_ok=True)
    (d / "cases.json").write_text(json.dumps(cases))
    return d


def test_load_cases_checks_keys_and_ids(tmp_path):
    assert re_.load_cases(_write(tmp_path / "ok", [_case()])) == [_case()]
    c = _case()
    del c["merge"]
    with pytest.raises(re_.CaseError, match="merge"):
        re_.load_cases(_write(tmp_path / "k", [c]))
    for bad in ("a/b", "..", ".", "", "x" * 65):
        with pytest.raises(re_.CaseError):
            re_.load_cases(_write(tmp_path / "i", [_case(id=bad)]))
    with pytest.raises(re_.CaseError):
        re_.load_cases(tmp_path / "missing")


def test_run_case_calls_review_per_variant_and_grade_once(tmp_path):
    variants = [re_.parse_variant("a=sonnet:low"), re_.parse_variant("b=opus:high")]
    calls = []

    def review(case, variant, work):
        calls.append(variant["name"])
        return {"findings": FOUND[variant["name"]], "unverified": 1, "cost_usd": 1.0, "seconds": 2.0}

    graded = []

    def grade(case, pooled):
        graded.append(pooled)
        return GRADES

    row = re_.run_case(_case(), variants, review, grade, tmp_path)
    assert calls == ["a", "b"] and len(graded) == 1 and [e["fp"] for e in graded[0]] == ["f1", "f2", "f3"]
    assert row["case"] == "c1" and row["pool"] == 3 and row["variants"]["a"]["real"] == 2
    assert row["pool_real"] == 2


def test_summarize_and_table():
    def v(real, wrong, serious, cost, unv=0, nit=0, ung=0):
        return {"real": real, "serious": serious, "nit": nit, "wrong": wrong, "ungraded": ung, "unverified": unv, "cost_usd": cost}

    rows = [
        {"case": "1", "pool": 3, "pool_real": 2, "variants": {"b": v(1, 1, 0, 1.0), "a": v(2, 0, 1, 2.0)}},
        {"case": "2", "pool": 2, "pool_real": 2, "variants": {"b": v(1, 0, 1, 3.0, unv=1), "a": v(0, 1, 0, 4.0)}},
    ]
    s = re_.summarize(rows)
    assert s["b"]["real"] == 2 and s["b"]["wrong"] == 1 and s["b"]["unverified"] == 1
    assert s["b"]["recall"] == 0.5 and s["b"]["precision"] == pytest.approx(2 / 3) and s["b"]["cost_usd"] == 2.0
    assert s["a"]["recall"] == 0.5 and s["a"]["cost_usd"] == 3.0
    lines = re_.table(s).splitlines()
    assert len(lines) == 3 and lines[1].split()[0] == "a" and lines[2].split()[0] == "b"


def test_malformed_grade_entries_count_as_ungraded():
    found = {"a": [F("f1"), F("f2")]}
    out = re_.score(found, {"f1": "real", "f2": None}, {})["a"]
    assert out["ungraded"] == 2 and out["real"] == 0
    row = re_.run_case(_case(), [re_.parse_variant("a=m:e")], lambda c, v, w: {"findings": found["a"]}, lambda c, p: {"f1": "real"}, Path("."))
    assert row["pool_real"] == 0
