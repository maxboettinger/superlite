"""#605: predict_live reads a project's test-run minutes and the machine's contention."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import predict_live  # noqa: E402
import run_tests  # noqa: E402
import state  # noqa: E402

DEAD = 99_999_999
CFG = {"slots": 2, "active_window_min": 120, "full_wait_share": 0.5}


def project(tmp_path, name="proj", config=None, ledger=()):
    root = tmp_path / name
    (root / ".superlite").mkdir(parents=True)
    if config is not None:
        (root / ".superlite" / "test-cmd.json").write_text(json.dumps(config), encoding="utf-8")
    if ledger:
        (root / ".superlite" / "progress.md").write_text("# Progress ledger\n\n" + "\n".join(ledger) + "\n", encoding="utf-8")
    return root


def fast(seconds, passed=3, failed=0):
    return f"- tests fast passed={passed} failed={failed} skipped=0 seconds={seconds}"


def full(seconds, recorded=False):
    return f"- tests full passed=900 failed=0 skipped=2 seconds={seconds}" + (" recorded" if recorded else "")


def bind(sid, sd, pid):
    p = state.home() / "sessions" / sid
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{sd}\n{pid}\n{sd.parent}\n", encoding="utf-8")


def run_dir(tmp_path, name, marker="stable.json", age_s=0):
    sd = tmp_path / name / ".superlite"
    sd.mkdir(parents=True)
    f = sd / marker
    f.write_text("{}", encoding="utf-8")
    if age_s:
        old = time.time() - age_s
        os.utime(f, (old, old))
    return sd


def test_run_min_dict_in_test_cmd_json_wins(tmp_path):
    root = project(tmp_path, config={"test": "make test", "run_min": {"fast": 6, "full": 12}, "slots": 2},
                   ledger=[fast(1.0)] * 5)
    assert predict_live.project_tests(root, {}) == {"fast_min": 6.0, "full_min": 12.0, "fast_source": "test-cmd.json",
                                                    "full_source": "test-cmd.json", "fast_runs": 0, "full_runs": 0, "slots": 2}


def test_a_run_min_number_sets_both_modes(tmp_path):
    out = predict_live.project_tests(project(tmp_path, config={"test": "make test", "run_min": 4.5}), {})
    assert (out["fast_min"], out["full_min"], out["slots"]) == (4.5, 4.5, None)


def test_a_user_level_entry_supplies_the_minutes(tmp_path, monkeypatch):
    root = project(tmp_path)
    (root / "go.mod").write_text("module x\n", encoding="utf-8")
    user = tmp_path / "user-test-cmd.json"
    user.write_text(json.dumps({"go": {"test": "go test ./...", "run_min": {"fast": 3, "full": 9}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(user))
    out = predict_live.project_tests(root, {})
    assert (out["fast_min"], out["full_min"], out["fast_source"]) == (3.0, 9.0, "user test-cmd.json")


def test_measured_ledger_lines_fill_a_mode_the_config_leaves_out(tmp_path):
    root = project(tmp_path, config={"test": "make test", "run_min": {"fast": 6}},
                   ledger=[full(600.0), full(540.0), full(720.0, recorded=True)])
    out = predict_live.project_tests(root, {"history_min_runs": 3})
    assert (out["full_min"], out["full_source"], out["full_runs"]) == (10.0, "history", 3)
    assert (out["fast_min"], out["fast_source"]) == (6.0, "test-cmd.json")


def test_history_is_the_ledger_median(tmp_path):
    root = project(tmp_path, ledger=[fast(30.0), fast(30.0), fast(30.0)])
    assert predict_live.project_tests(root, {"history_min_runs": 3}) == {
        "fast_min": 0.5, "full_min": None, "fast_source": "history", "full_source": None,
        "fast_runs": 3, "full_runs": 0, "slots": None}


def test_too_few_lines_give_no_minutes(tmp_path):
    out = predict_live.project_tests(project(tmp_path, ledger=[fast(30.0), fast(30.0)]), {"history_min_runs": 3})
    assert (out["fast_min"], out["fast_source"], out["fast_runs"]) == (None, None, 0)


def test_runs_that_ran_nothing_do_not_count(tmp_path):
    root = project(tmp_path, ledger=[fast(30.0), fast(30.0), fast(30.0), fast(1.0, passed=0)])
    assert predict_live.project_tests(root, {"history_min_runs": 3})["fast_min"] == 0.5


def test_only_the_newest_lines_count(tmp_path):
    root = project(tmp_path, ledger=[fast(600.0)] * 3 + [fast(6.0)] * 3)
    assert predict_live.project_tests(root, {"history_min_runs": 3, "history_keep": 3})["fast_min"] == 0.1


def test_archived_run_ledgers_count(tmp_path):
    root = project(tmp_path)
    old = root / ".superlite" / "runs" / "20261101-120000"
    old.mkdir(parents=True)
    (old / "progress.md").write_text("\n".join([full(300.0)] * 3) + "\n", encoding="utf-8")
    assert predict_live.project_tests(root, {"history_min_runs": 3})["full_min"] == 5.0


def test_other_worktrees_ledgers_count(tmp_path):
    main = tmp_path / "main"
    main.mkdir()

    def git(*a):
        subprocess.run(["git", "-C", str(main), *a], check=True, capture_output=True)

    git("init", "-q")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
    git("worktree", "add", "-q", str(tmp_path / "wt"), "-b", "side")
    (main / ".superlite").mkdir()
    (main / ".superlite" / "progress.md").write_text("\n".join([fast(12.0)] * 3) + "\n", encoding="utf-8")
    (tmp_path / "wt" / ".superlite").mkdir()
    assert predict_live.project_tests(tmp_path / "wt", {"history_min_runs": 3})["fast_min"] == 0.2


def test_a_bad_run_min_is_ignored(tmp_path):
    for i, bad in enumerate(("6", -1, 0, True, {"fast": "x"}, [6])):
        root = project(tmp_path, name=f"p{i}", config={"test": "make test", "run_min": bad, "slots": 0})
        out = predict_live.project_tests(root, {})
        assert (out["fast_min"], out["full_min"], out["slots"]) == (None, None, None), bad


def test_no_other_runs_no_contention(tmp_path):
    assert predict_live.contention(project(tmp_path), CFG) == {
        "others": 0, "full_lock": False, "slots": 2, "factor": 1.0, "full_factor": 1.0}


def test_three_live_runs_double_the_test_runs(tmp_path):
    root = project(tmp_path)
    for i in range(3):
        bind(f"s{i}", run_dir(tmp_path, f"other{i}"), os.getpid())
    assert predict_live.contention(root, CFG) == {
        "others": 3, "full_lock": False, "slots": 2, "factor": 2.0, "full_factor": 2.5}


def test_dead_idle_markerless_and_own_runs_do_not_count(tmp_path):
    root = project(tmp_path)
    bind("dead", run_dir(tmp_path, "a"), DEAD)
    bind("idle", run_dir(tmp_path, "b", age_s=3 * 3600), os.getpid())
    nomark = tmp_path / "c" / ".superlite"
    nomark.mkdir(parents=True)
    bind("nomark", nomark, os.getpid())
    (root / ".superlite" / "stable.json").write_text("{}", encoding="utf-8")
    bind("mine", root / ".superlite", os.getpid())
    tree = root / ".superlite" / "trees" / "T1" / ".superlite"
    tree.mkdir(parents=True)
    (tree / "pool.json").write_text("{}", encoding="utf-8")
    bind("tree", tree, os.getpid())
    bind("gone", tmp_path / "gone" / ".superlite", os.getpid())
    (state.home() / "sessions" / "nopid").write_text(f"{run_dir(tmp_path, 'd')}\n", encoding="utf-8")
    (state.home() / "sessions" / "x.d").mkdir()
    assert predict_live.contention(root, CFG)["others"] == 0


def test_two_sessions_of_one_run_count_once(tmp_path):
    root, sd = project(tmp_path), run_dir(tmp_path, "lead")
    bind("lead", sd, os.getpid())
    bind("worker", sd, os.getpid())
    assert predict_live.contention(root, CFG)["others"] == 1


def test_a_fresh_ledger_keeps_an_old_marker_active(tmp_path):
    root, sd = project(tmp_path), run_dir(tmp_path, "lead", age_s=5 * 3600)
    (sd / "progress.md").write_text("- dispatch T1\n", encoding="utf-8")
    bind("lead", sd, os.getpid())
    assert predict_live.contention(root, CFG)["others"] == 1


def test_a_live_full_suite_lock_holder_elsewhere_counts(tmp_path):
    root = project(tmp_path)
    lock = run_tests.full_lock_path("python")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": os.getpid(), "root": str(tmp_path / "elsewhere"), "task": None, "started": time.time()}))
    assert predict_live.contention(root, CFG) == {
        "others": 0, "full_lock": True, "slots": 2, "factor": 1.0, "full_factor": 1.5}


def test_a_live_holder_of_another_toolchain_lock_counts(tmp_path):
    root = project(tmp_path)
    lock = run_tests.full_lock_path("xcode")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": os.getpid(), "root": str(tmp_path / "elsewhere"), "task": None, "started": time.time()}))
    assert predict_live.contention(root, CFG)["full_lock"] is True


def test_a_dead_or_own_lock_holder_does_not_count(tmp_path):
    root = project(tmp_path)
    lock = run_tests.full_lock_path("python")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": DEAD, "root": "/elsewhere", "task": None, "started": 1.0}))
    assert predict_live.contention(root, CFG)["full_lock"] is False
    lock.write_text(json.dumps({"pid": os.getpid(), "root": str(root), "task": "T1", "started": 1.0}))
    assert predict_live.contention(root, CFG)["full_lock"] is False


def test_slots_from_test_cmd_json_override_the_default(tmp_path):
    root = project(tmp_path)
    for i in range(3):
        bind(f"s{i}", run_dir(tmp_path, f"other{i}"), os.getpid())
    assert predict_live.contention(root, CFG, slots=4)["factor"] == 1.0
    assert predict_live.contention(root, CFG, slots=1)["factor"] == 4.0
    assert predict_live.contention(root, {}, slots=None)["slots"] == 2


def test_is_alive():
    assert predict_live.is_alive(os.getpid())
    assert not predict_live.is_alive(DEAD)
    assert not predict_live.is_alive(0)
    assert not predict_live.is_alive(True)
