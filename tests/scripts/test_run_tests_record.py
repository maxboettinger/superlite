"""run_tests --record: write a full-run summary for a result the agent ran outside run_tests."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pt_review  # noqa: E402


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def summary(cwd, name="test-summary.json"):
    return json.loads((Path(cwd) / ".superlite" / name).read_text(encoding="utf-8"))


def record(tmp_path):
    return rt(tmp_path, "--record", "--passed", "1333", "--command", "Scripts/test.sh")


def test_record_writes_full_summary(tmp_path):
    r = record(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    s = summary(tmp_path)
    assert {k: s[k] for k in ("mode", "passed", "failed", "skipped", "recorded")} == {
        "mode": "full", "passed": 1333, "failed": 0, "skipped": 0, "recorded": "Scripts/test.sh"}
    assert "started" in s
    assert "- tests full passed=1333 failed=0 skipped=0 seconds=0 recorded" in (tmp_path / ".superlite" / "progress.md").read_text(encoding="utf-8")


def test_record_without_command_exits_2(tmp_path):
    r = rt(tmp_path, "--record", "--passed", "3")
    assert r.returncode == 2 and "--command" in r.stderr
    r = rt(tmp_path, "--record", "--command", "x.sh")
    assert r.returncode == 2 and "--passed" in r.stderr


def test_finish_labels_recorded(tmp_path):
    record(tmp_path)
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(SCRIPTS / "finish.py"), "--ledger", str(sl / "progress.md"), "--log", str(sl / "incidents.jsonl")],
                        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert "tests (full, recorded): 1333 passed" in cp.stdout, cp.stdout + cp.stderr


def test_record_shadows_older_background_summary(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    old = sl / "test-summary-old.json"
    old.write_text(json.dumps({"passed": 0, "failed": 1, "skipped": 0, "mode": "full"}), encoding="utf-8")
    (sl / "test-summary.latest").write_text(json.dumps({"id": "old", "summary": str(old), "mode": "full"}), encoding="utf-8")
    assert pt_review.newest_summary_path(sl / "test-summary.json") == old
    assert record(tmp_path).returncode == 0
    assert pt_review.newest_summary_path(sl / "test-summary.json") == sl / "test-summary.json"


def test_record_negative_passed_exits_2(tmp_path):
    r = rt(tmp_path, "--record", "--passed", "-1", "--command", "x.sh")
    assert r.returncode == 2 and "--passed" in r.stderr
    assert not (tmp_path / ".superlite" / "test-summary.json").exists()


def test_record_with_failures_and_seconds(tmp_path):
    r = rt(tmp_path, "--record", "--passed", "10", "--failed", "2", "--skipped", "1", "--seconds", "4.5", "--command", "x.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    s = summary(tmp_path)
    assert (s["passed"], s["failed"], s["skipped"], s["seconds"]) == (10, 2, 1, 4.5)
    assert "- tests full passed=10 failed=2 skipped=1 seconds=4.5 recorded" in (tmp_path / ".superlite" / "progress.md").read_text(encoding="utf-8")
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(SCRIPTS / "finish.py"), "--ledger", str(sl / "progress.md"), "--log", str(sl / "incidents.jsonl")],
                        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert "2 failed" in cp.stdout, cp.stdout + cp.stderr


def test_record_negative_failed_exits_2(tmp_path):
    for flag in ("--failed", "--skipped", "--seconds"):
        r = rt(tmp_path, "--record", "--passed", "3", flag, "-1", "--command", "x.sh")
        assert r.returncode == 2 and flag in r.stderr, flag
