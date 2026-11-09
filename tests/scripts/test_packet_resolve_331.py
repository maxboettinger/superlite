"""#331: an `sl incident resolve` record closes its location in the review packet, also after repeated entries."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import incident  # noqa: E402
import pt_review  # noqa: E402


def add(log, **e):
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e) + "\n")


def items(log):
    return pt_review.incident_items(pt_review.read_incidents(log))


def resolve(log, file, line, *extra):
    assert incident.main(["resolve", "--file", file, "--line", str(line), "--ruling", "fixed by T3",
                          "--log", str(log), *extra]) == 0


def test_is_ruling():
    assert pt_review.is_ruling({"resolution": "resolved", "context": "resolved: fixed by T3"})
    assert pt_review.is_ruling({"resolution": "Accepted", "context": "Accepted: known gap"})
    assert not pt_review.is_ruling({"resolution": "fixed", "context": "off-by-one"})
    assert not pt_review.is_ruling({"resolution": "open", "context": "open: x"})
    assert not pt_review.is_ruling({"context": "resolved: x"})


def test_resolve_record_closes_its_location(tmp_path):
    log = tmp_path / "incidents.jsonl"
    add(log, file="skills/x/backlog_ship.py", line=249, context="AssertionError boom", kind="test-failure",
        resolution="open", agent="run_tests", epoch=1.0)
    assert len(items(log)) == 1
    resolve(log, "skills/x/backlog_ship.py", 249)
    assert items(log) == []


def test_resolve_closes_a_repeated_location(tmp_path):
    log = tmp_path / "incidents.jsonl"
    for ctx in ("first boom", "second boom"):
        add(log, file="a.py", line=3, context=ctx, kind="exception", resolution="open", agent="T1")
    resolve(log, "a.py", 3, "--resolution", "accepted")
    assert items(log) == []


def test_entry_after_the_resolve_reopens(tmp_path):
    log = tmp_path / "incidents.jsonl"
    add(log, file="a.py", line=3, context="first boom", kind="exception", resolution="open", agent="T1")
    resolve(log, "a.py", 3)
    add(log, file="a.py", line=3, context="third boom", kind="exception", resolution="open", agent="T2")
    it = items(log)
    assert len(it) == 1 and "unresolved" in it[0].title


def test_fixed_findings_without_a_ruling_stay_repeated():
    es = [{"file": "a.py", "line": 3, "context": "first", "kind": "exception", "resolution": "fixed"},
          {"file": "a.py", "line": 3, "context": "second", "kind": "exception", "resolution": "fixed"}]
    it = pt_review.incident_items(es)
    assert len(it) == 1 and "repeated" in it[0].title
