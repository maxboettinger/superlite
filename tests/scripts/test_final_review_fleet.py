# tests/scripts/test_final_review_fleet.py
import json, time
import pytest
from test_final_review_check import big, metrics, repo, run  # noqa: F401  (repo is a fixture)

def now_ms(offset_s=0):
    return int((time.time() + offset_s) * 1000)

def test_fleet_final_reviewer_stop_counts(repo):
    big(repo)
    metrics(repo, {"ev": "stop", "t": now_ms(5), "agent_id": "W4", "type": "fleet:superlite:final-reviewer", "last": "Verdict: APPROVED"})
    assert run(repo).stdout == ""

def test_fleet_record_as_capture_worker_stop_writes_it_counts(repo):
    big(repo)
    d = repo / ".superlite"; d.mkdir(exist_ok=True)
    (d / "metrics.jsonl").write_text('{"ev":"stop","t":%d,"agent_id":"W4","type":"fleet:superlite:final-reviewer","transcript":"/t.jsonl","last":"Verdict: APPROVED"}\n' % now_ms(5))
    assert run(repo).stdout == ""

def test_old_fleet_final_reviewer_stop_still_blocks(repo):
    big(repo)
    metrics(repo, {"ev": "stop", "t": now_ms(-3600), "agent_id": "W4", "type": "fleet:superlite:final-reviewer", "last": "Verdict: APPROVED"})
    assert json.loads(run(repo).stdout)["decision"] == "block"

@pytest.mark.parametrize("kind", ["fleet:superlite:implementer", "fleet:superlite:package-reviewer", "fleet:superlite:final-reviewer-x"])
def test_other_fleet_roles_do_not_count(repo, kind):
    big(repo)
    metrics(repo, {"ev": "stop", "t": now_ms(5), "agent_id": "W1", "type": kind})
    assert json.loads(run(repo).stdout)["decision"] == "block"
