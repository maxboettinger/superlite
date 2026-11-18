#!/usr/bin/env python3
"""Reviewer eval core: pure functions to load cases, pool findings, score variants and summarize.

    load_cases(set_dir) -> list of case dicts (id, repo, base, merge, title, body); CaseError on a bad file
    parse_variant("name=model:effort") -> {"name", "model", "effort"}; ValueError on a bad spec
    pool(found) -> the findings of all variants merged by fingerprint, sorted, without variant names
    score(found, grades, stats) -> per variant counts, recall, precision, unverified, cost_usd
    run_case(case, variants, review_fn, grade_fn, work) -> {"case", "pool", "pool_real", "variants"}
    summarize(rows) -> per variant totals over rows; table(summary) -> text table

No subprocess and no model call: the live adapters pass review_fn and grade_fn.
"""
import json
import re
from pathlib import Path

KEYS = ("id", "repo", "base", "merge", "title", "body")
ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
GRADES = ("real", "nit", "wrong")
POOL_KEYS = ("fp", "file", "line", "problem", "quote")


class CaseError(ValueError):
    """A case file that is missing or malformed."""


def load_cases(set_dir: Path) -> list:
    path = Path(set_dir) / "cases.json"
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaseError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(cases, list):
        raise CaseError("cases.json must hold a list")
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise CaseError(f"case {i} is not an object")
        for key in KEYS:
            if key not in case:
                raise CaseError(f"case {i} lacks the key {key}")
        cid = case["id"]
        if not isinstance(cid, str) or not ID.match(cid) or cid in (".", ".."):
            raise CaseError(f"case {i} has a bad id {cid!r}")
    return cases


def parse_variant(text: str) -> dict:
    name, sep, rest = text.partition("=")
    model, sep2, effort = rest.partition(":")
    if not sep or not sep2 or not name.strip() or not model.strip() or not effort.strip():
        raise ValueError(f"variant must be name=model:effort, got {text!r}")
    return {"name": name.strip(), "model": model.strip(), "effort": effort.strip()}


def pool(found: dict) -> list:
    merged = {}
    for name in sorted(found):
        for f in found[name]:
            merged.setdefault(f["fp"], {k: f.get(k) for k in POOL_KEYS})
    return [merged[fp] for fp in sorted(merged)]


def _ratio(num: int, den: int):
    return num / den if den else None


def _entry(grades: dict, fp) -> dict:
    g = grades.get(fp)
    return g if isinstance(g, dict) else {}


def _grade(grades: dict, fp) -> str:
    word = _entry(grades, fp).get("grade")
    return word if word in GRADES else "ungraded"


def score(found: dict, grades: dict, stats: dict) -> dict:
    pooled = {e["fp"] for e in pool(found)}

    def grade_of(fp):
        return _grade(grades, fp)

    pool_real = sum(1 for fp in pooled if grade_of(fp) == "real")
    out = {}
    for name, findings in found.items():
        counts = {"real": 0, "serious": 0, "nit": 0, "wrong": 0, "ungraded": 0}
        for fp in {f["fp"] for f in findings}:
            g = grade_of(fp)
            counts[g] += 1
            if g == "real" and _entry(grades, fp).get("serious") is True:
                counts["serious"] += 1
        st = stats.get(name) or {}
        out[name] = {**counts, "unverified": st.get("unverified", 0),
                     "recall": _ratio(counts["real"], pool_real),
                     "precision": _ratio(counts["real"], counts["real"] + counts["wrong"]),
                     "cost_usd": st.get("cost_usd", 0.0)}
    return out


def run_case(case: dict, variants: list, review_fn, grade_fn, work: Path) -> dict:
    found, stats, kept = {}, {}, {}
    for variant in variants:
        res = review_fn(case, variant, work)
        found[variant["name"]] = res["findings"]
        kept[variant["name"]] = res.get("unverified_items", [])
        stats[variant["name"]] = {"unverified": res.get("unverified", 0), "cost_usd": res.get("cost_usd", 0.0)}
    pooled = pool(found)
    grades = grade_fn(case, pooled)
    scored = score(found, grades, stats)
    pool_real = sum(1 for e in pooled if _grade(grades, e["fp"]) == "real")
    return {"case": case["id"], "pool": len(pooled), "pool_real": pool_real, "variants": scored,
            "unverified_items": kept}


def summarize(rows: list) -> dict:
    total_real = sum(r.get("pool_real", 0) for r in rows)
    sums = {}
    for row in rows:
        for name, v in row["variants"].items():
            s = sums.setdefault(name, {"real": 0, "serious": 0, "nit": 0, "wrong": 0, "ungraded": 0, "unverified": 0, "cost": 0.0, "n": 0})
            for k in ("real", "serious", "nit", "wrong", "ungraded", "unverified"):
                s[k] += v.get(k, 0)
            s["cost"] += v.get("cost_usd", 0.0)
            s["n"] += 1
    out = {}
    for name, s in sums.items():
        out[name] = {k: s[k] for k in ("real", "serious", "nit", "wrong", "ungraded", "unverified")}
        out[name].update(recall=_ratio(s["real"], total_real), precision=_ratio(s["real"], s["real"] + s["wrong"]),
                         cost_usd=s["cost"] / s["n"])
    return out


def table(summary: dict) -> str:
    def fmt(x):
        return "-" if x is None else f"{x:.2f}"

    lines = [f"{'variant':<16}{'real':>6}{'serious':>9}{'nit':>5}{'wrong':>7}{'ungr':>6}{'unver':>7}{'recall':>8}{'prec':>7}{'cost':>8}"]
    for name in sorted(summary):
        s = summary[name]
        lines.append(f"{name:<16}{s['real']:>6}{s['serious']:>9}{s['nit']:>5}{s['wrong']:>7}{s['ungraded']:>6}{s['unverified']:>7}"
                     f"{fmt(s['recall']):>8}{fmt(s['precision']):>7}{fmt(s['cost_usd']):>8}")
    return "\n".join(lines)
