"""#630: `test_layers.py run unit` waits on its own pending background run and stamps it from the digests taken before it."""
import subprocess
from pathlib import Path

from test_test_layers import cli, repo, stale_names  # noqa: F401  (puts scripts/ on sys.path)
import layer_store  # noqa: E402


def no_result(pid, rerun):
    return f"printf 'tests: no result yet after 540 s (pid {pid} still running); run again: {rerun}\\n' >&2; exit 2"


def waiter(tmp_path, body):
    script, log = tmp_path / "wait.sh", tmp_path / "wait-args.txt"
    script.write_text(f'echo "$@" >> {log}\n{body}\n')
    return script, log


def start_pending(repo, tmp_path, script):
    sleeper = subprocess.Popen(["sleep", "120"])
    summary = tmp_path / "s.json"
    r = cli(repo, "run", "unit", "--command-override", "unit=" + no_result(sleeper.pid, f"sh {script} {summary}"))
    assert r.returncode == 4 and "unit: running" in r.stdout, r.stdout + r.stderr
    assert "python3 scripts/test_layers.py run unit` again" in r.stdout
    return sleeper, summary


def stop(p):
    p.kill()
    p.wait()


def test_pending_record_round_trip(tmp_path):
    s = tmp_path / "test-layers.json"
    layer_store.start_run(s, "unit", "ab12", 4242, wait="sl run_tests --wait /r/s.json")
    assert layer_store.pending(s, "unit") == {"pid": 4242, "digest": "ab12", "wait": "sl run_tests --wait /r/s.json"}
    assert layer_store.pending(s, "headless") == {}
    layer_store.start_run(s, "tui", "cd34", 7)
    assert layer_store.pending(s, "tui") == {"pid": 7, "digest": "cd34"}


def test_second_run_waits_on_pending_run_and_stamps(repo, tmp_path):
    script, log = waiter(tmp_path, "exit 0")
    sleeper, summary = start_pending(repo, tmp_path, script)
    try:
        r = cli(repo, "run", "unit", "--command-override", "unit=exit 1")
        assert r.returncode == 0 and "unit: green" in r.stdout, r.stdout + r.stderr
        assert log.read_text().split() == [str(summary), "--timeout", "540"]
        assert "unit" not in stale_names(repo)
    finally:
        stop(sleeper)


def test_changed_file_starts_a_new_run(repo, tmp_path):
    script, log = waiter(tmp_path, "exit 0")
    sleeper, _ = start_pending(repo, tmp_path, script)
    try:
        (repo / "hooks" / "x").write_text("changed\n")
        r = cli(repo, "run", "unit", "--command-override", "unit=exit 1")
        assert r.returncode == 1 and "unit: red" in r.stdout
        assert not log.exists()
    finally:
        stop(sleeper)


def test_red_pending_run_clears_the_record(repo, tmp_path):
    script, log = waiter(tmp_path, "echo boom >&2; exit 1")
    sleeper, _ = start_pending(repo, tmp_path, script)
    try:
        r = cli(repo, "run", "unit", "--command-override", "unit=exit 1")
        assert r.returncode == 1 and "unit: red" in r.stdout
        r = cli(repo, "run", "unit", "--command-override", "unit=exit 0")
        assert r.returncode == 0 and len(log.read_text().splitlines()) == 1
    finally:
        stop(sleeper)


def test_still_running_keeps_the_record(repo, tmp_path):
    sleeper = subprocess.Popen(["sleep", "120"])
    try:
        script, log = tmp_path / "wait.sh", tmp_path / "wait-args.txt"
        script.write_text(f'echo "$@" >> {log}\n' + no_result(sleeper.pid, f"sh {script} {tmp_path / 's.json'}") + "\n")
        r = cli(repo, "run", "unit", "--command-override", "unit=" + no_result(sleeper.pid, f"sh {script} {tmp_path / 's.json'}"))
        assert r.returncode == 4
        r = cli(repo, "run", "unit", "--command-override", "unit=exit 1")
        assert r.returncode == 4 and "unit: running" in r.stdout and len(log.read_text().splitlines()) == 1
        assert "unit running run in progress" in cli(repo, "status").stdout.splitlines()
        script.write_text(f'echo "$@" >> {log}\nexit 0\n')
        r = cli(repo, "run", "unit", "--command-override", "unit=exit 1")
        assert r.returncode == 0 and "unit: green" in r.stdout
    finally:
        stop(sleeper)


def test_dead_pending_run_without_summary_starts_new_run(repo, tmp_path):
    script, log = waiter(tmp_path, "exit 0")
    sleeper, _ = start_pending(repo, tmp_path, script)
    stop(sleeper)
    r = cli(repo, "run", "unit", "--command-override", "unit=exit 0")
    assert r.returncode == 0 and not log.exists()


def test_dead_pending_run_with_summary_is_resumed(repo, tmp_path):
    script, log = waiter(tmp_path, "exit 0")
    sleeper, summary = start_pending(repo, tmp_path, script)
    stop(sleeper)
    summary.write_text("{}")
    r = cli(repo, "run", "unit", "--command-override", "unit=exit 1")
    assert r.returncode == 0 and log.exists()


def test_green_run_stamps_digests_from_before_the_run(repo):
    r = cli(repo, "run", "unit", "--command-override", "unit=echo changed > hooks/x")
    assert r.returncode == 0 and "unit: green" in r.stdout
    assert "unit" in stale_names(repo)
