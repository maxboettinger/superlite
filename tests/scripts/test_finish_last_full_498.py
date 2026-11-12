"""finish and the build report take the run's last full run as its test result and name a newer run beside it (#498);
finish's checkpoint note names `sl autocommit apply --trailer` (B96 follow-up)."""
import json
import sys

from test_plan_tools import SCRIPTS, run
from test_report import fixture, go

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import report  # noqa: E402

FULL = "- tests full passed=5777 failed=4 skipped=2 seconds=812.3"
FAST = "- tests fast passed=12 failed=0 skipped=0 seconds=1.2"
FAST2 = "- tests fast passed=3 failed=1 skipped=0 seconds=0.8"
REC = "- tests full passed=1333 failed=0 skipped=0 seconds=900 recorded"


def ledger(tmp_path, *lines):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    p = sl / "progress.md"
    p.write_text("# Progress ledger\n- start abc1234\n" + "".join(x + "\n" for x in lines), encoding="utf-8")
    return p


def finish_out(tmp_path, p):
    cp = run(SCRIPTS / "finish.py", "--ledger", p, "--log", p.with_name("incidents.jsonl"), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return cp.out


def test_test_result_last_full_wins_and_names_newer_fast(tmp_path):
    res, newer, n = finish.test_result(ledger(tmp_path, FAST2, FULL, FAST))
    assert res == {"mode": "full", "passed": 5777, "failed": 4, "skipped": 2, "seconds": 812.3, "recorded": False}
    assert newer == {"mode": "fast", "passed": 12, "failed": 0, "skipped": 0, "seconds": 1.2, "recorded": False} and n == 1


def test_test_result_counts_every_newer_run_and_keeps_the_newest(tmp_path):
    res, newer, n = finish.test_result(ledger(tmp_path, FULL, FAST2, FAST))
    assert res["passed"] == 5777 and newer["passed"] == 12 and n == 2


def test_test_result_full_newest_has_no_newer(tmp_path):
    res, newer, n = finish.test_result(ledger(tmp_path, FAST, FULL))
    assert res["mode"] == "full" and res["passed"] == 5777 and newer is None and n == 0


def test_test_result_recorded_full_never_counts_as_full(tmp_path):
    res, newer, n = finish.test_result(ledger(tmp_path, FULL, REC, FAST))
    assert res == {"mode": "full", "passed": 5777, "failed": 4, "skipped": 2, "seconds": 812.3, "recorded": False}
    assert newer["passed"] == 12 and n == 2


def test_test_result_without_full_run_is_the_newest_line(tmp_path):
    res, newer, n = finish.test_result(ledger(tmp_path, FAST, FAST2))
    assert res["mode"] == "fast" and res["passed"] == 3 and newer is None and n == 0


def test_test_result_none_and_missing(tmp_path):
    assert finish.test_result(ledger(tmp_path)) == (None, None, 0)
    assert finish.test_result(tmp_path / "nope" / "progress.md") == (None, None, 0)


def test_finish_prints_the_full_run_and_the_newer_fast_run(tmp_path):
    lines = finish_out(tmp_path, ledger(tmp_path, FULL, FAST)).splitlines()
    i = lines.index("tests (full): 5777 passed, 4 failed, 2 skipped in 812.3s")
    assert lines[i + 1] == "- newer fast run (not the run's result): 12 passed, 0 failed, 0 skipped in 1.2s"
    assert not any(x.startswith("tests (fast)") for x in lines)


def test_finish_counts_several_newer_runs(tmp_path):
    out = finish_out(tmp_path, ledger(tmp_path, FULL, FAST2, FAST))
    assert "- 2 newer fast runs (not the run's result), newest: 12 passed, 0 failed, 0 skipped in 1.2s" in out.splitlines()


def test_finish_full_newest_prints_one_line(tmp_path):
    out = finish_out(tmp_path, ledger(tmp_path, FAST, FULL))
    assert "tests (full): 5777 passed, 4 failed, 2 skipped in 812.3s" in out.splitlines() and "newer fast run" not in out


def test_finish_recorded_and_fast_only_keep_their_labels(tmp_path):
    assert "tests (full, recorded): 1333 passed, 0 failed, 0 skipped in 900.0s" in finish_out(tmp_path, ledger(tmp_path, REC)).splitlines()
    assert "tests (fast): 3 passed, 1 failed, 0 skipped in 0.8s" in finish_out(tmp_path, ledger(tmp_path, FAST, FAST2)).splitlines()
    assert "tests: none recorded" in finish_out(tmp_path, ledger(tmp_path)).splitlines()


def test_checkpoint_note_names_the_trailer_flag(tmp_path, monkeypatch):
    import autocommit
    p = ledger(tmp_path)
    (p.parent / "checkpoints.json").write_text(json.dumps({"run": "r1", "entries": [{"title": "T1 x", "files": ["a.py"]}]}), encoding="utf-8")
    monkeypatch.setattr(autocommit, "is_on", lambda *a, **k: False)
    text = "\n".join(finish.checkpoint_note(p))
    assert "no trailer" not in text
    assert ('`sl autocommit apply` (one commit per task, same titles; add `--trailer "Key: value"`, repeatable, '
            "for each attribution line your harness requires)") in text


def test_report_takes_the_last_full_run_and_names_the_newer_fast_run(tmp_path):
    p = fixture(tmp_path)
    sl = tmp_path / ".superlite"
    ledger(tmp_path, FULL, FAST)
    (sl / "test-summary.json").write_text(json.dumps({"passed": 12, "failed": 0, "skipped": 0, "mode": "fast"}), encoding="utf-8")
    c = json.loads(go(tmp_path, p, "--json"))
    assert c["quality"]["tests"]["passed"] == 5777 and c["quality"]["tests"]["failed"] == 4
    assert c["quality"]["tests_newer"]["passed"] == 12 and c["quality"]["tests_from"] == "progress.md"
    want = "tests 5777 passed, 4 failed (last full run; newer fast run: 12 passed, 0 failed)"
    assert want + "; first-time pass" in go(tmp_path, p)
    assert "quality: " + want + "; first-time pass" in go(tmp_path, p, "--full")


def test_report_fast_only_says_so_and_falls_back_without_ledger_lines(tmp_path):
    p = fixture(tmp_path)
    sl = tmp_path / ".superlite"
    ledger(tmp_path, FAST)
    assert "tests 12 passed, 0 failed (fast run; no full run); first-time pass" in go(tmp_path, p)
    ledger(tmp_path)
    (sl / "test-summary.json").write_text(json.dumps({"passed": 9, "failed": 1, "skipped": 0, "mode": "fast"}), encoding="utf-8")
    c = json.loads(go(tmp_path, p, "--json"))
    assert c["quality"]["tests"]["failed"] == 1 and c["quality"]["tests_newer"] is None and c["quality"]["tests_from"] == "test-summary.json"
    assert "tests 9 passed, 1 failed; first-time pass" in go(tmp_path, p)


def test_report_renders_an_old_saved_report_without_tests_newer(tmp_path):
    p = fixture(tmp_path)
    c = json.loads(go(tmp_path, p, "--json"))
    for k in ("tests_newer", "tests_from"):
        c["quality"].pop(k, None)
    c["quality"]["tests"] = {"passed": 9, "failed": 1}
    assert "tests 9 passed, 1 failed;" in report.render(c) and "tests 9 passed, 1 failed;" in report.summary(c, "x.md")
