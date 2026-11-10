"""#494: the unit layer passes a wait limit and reports a still-running run as running, not red."""
import subprocess
import sys
import types

from test_test_layers import cli, repo, stale_names, store_file, tl  # noqa: F401


def test_unit_command_wait():
    assert tl.unit_command(1200) == f"{tl.SL} run_tests --full --background && {tl.SL} run_tests --wait --timeout 1200"
    assert tl.COMMANDS["unit"].endswith("--wait --timeout 540")


def test_wait_flag_and_env(monkeypatch, repo, tmp_path):
    seen = []

    def fake(cmd, **kw):
        seen.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(tl.subprocess, "run", fake)
    state = str(tmp_path / "s.json")

    def run(*extra, env=None):
        monkeypatch.delenv("SUPERLITE_UNIT_WAIT", raising=False)
        if env is not None:
            monkeypatch.setenv("SUPERLITE_UNIT_WAIT", env)
        seen.clear()
        tl.main(["run", "unit", *extra, "--root", str(repo), "--state", state])
        return [c for c in seen if isinstance(c, str)][-1]

    assert "--timeout 900" in run("--wait", "900")
    assert "--timeout 700" in run(env="700")
    assert "--timeout 900" in run("--wait", "900", env="700")
    assert "--timeout 540" in run(env="x")


def running_override(pid=None):
    part = f" (pid {pid} still running)" if pid else ""
    return (f"printf 'tests: no result yet after 540 s{part}; run again: sl run_tests --wait /x/s.json\\n' >&2; exit 2")


def test_no_result_is_running_not_red(repo):
    p = subprocess.Popen(["sleep", "30"])
    try:
        r = cli(repo, "run", "unit", "--command-override", "unit=" + running_override(p.pid))
        assert r.returncode == 4
        assert "unit: running" in r.stdout and "sl run_tests --wait /x/s.json" in r.stdout
        assert "unit: red" not in r.stdout
        assert "unit running run in progress" in cli(repo, "status").stdout.splitlines()
        assert "unit" not in stale_names(repo)
    finally:
        p.kill()
        p.wait()
    assert "unit" in stale_names(repo)


def test_no_pid_running_clears_mark(repo):
    r = cli(repo, "run", "unit", "--command-override", "unit=" + running_override())
    assert r.returncode == 4
    assert "unit running" not in cli(repo, "status").stdout


def test_red_stays_red(repo):
    r = cli(repo, "run", "unit", "--command-override", "unit=echo boom >&2; exit 1")
    assert r.returncode == 1
    assert "unit: red" in r.stdout


def test_running_and_red_exit_1(repo):
    r = cli(repo, "run", "unit", "headless", "--command-override", "unit=" + running_override(), "headless=false")
    assert r.returncode == 1
