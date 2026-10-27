"""Open incidents in the finish summary: identical incidents collapse, most frequent first, a limit with a more line."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402


def inc(file="a.swift", line=1, kind="exception", context="x"):
    return {"file": file, "line": line, "kind": kind, "context": context}


A = inc()
B = inc(file="b.swift", line=2, kind="flaky", context="y")


def test_groups_identical_incidents():
    out = finish.group_incidents([A, A, A, B])
    assert out == ["- 3x a.swift:1 [exception] x", "- b.swift:2 [flaky] y"]


def test_most_frequent_first():
    assert finish.group_incidents([B, A, A])[0] == "- 2x a.swift:1 [exception] x"


def test_ties_keep_log_order():
    assert finish.group_incidents([B, A]) == ["- b.swift:2 [flaky] y", "- a.swift:1 [exception] x"]


def test_missing_kind_is_unknown():
    out = finish.group_incidents([{"file": "a.swift", "line": 1, "context": "x"}])
    assert out == ["- a.swift:1 [unknown] x"]


def test_limit_adds_more_line():
    many = [inc(file=f"f{i}.swift", line=i, kind="flaky", context="c") for i in range(20)]
    out = finish.group_incidents(many, limit=15)
    assert len(out) == 16
    assert out[0] == "- f0.swift:0 [flaky] c"
    assert out[-1] == "- (+5 more)"


def test_default_limit_is_fifteen():
    many = [inc(file=f"f{i}.swift", line=i, kind="flaky", context="c") for i in range(20)]
    assert finish.group_incidents(many)[-1] == "- (+5 more)"


def test_no_more_line_at_the_limit():
    exact = [inc(file=f"f{i}.swift", line=i) for i in range(15)]
    assert len(finish.group_incidents(exact, limit=15)) == 15


def test_header_counts_total_and_distinct(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    log = [A, A, A, B]
    (sl / "i.jsonl").write_text("\n".join(json.dumps(e) for e in log) + "\n", encoding="utf-8")
    text = run(SCRIPTS / "finish.py", "--ledger", sl / "progress.md", "--log", sl / "i.jsonl", cwd=tmp_path).out
    assert "open incidents: 4 (2 distinct)" in text
    assert "- 3x a.swift:1 [exception] x" in text
