"""commit_task passes --plan to the background probe_run and names the generated probe files (#417)."""
import sys

from test_autocommit import SCRIPTS, checkpoint, make_repo, write

sys.path.insert(0, str(SCRIPTS))

SRC = "def parse(t):\n    return t.split()\n"
TEST = "def test_p():\n    assert 1\n"
DEEP = "tests/regression/test_probe_deep_1.py"
ADAPTER = "tests/regression/_probe_adapter.py"


def test_launch_passes_plan(tmp_path, monkeypatch):
    import commit_task
    seen = []
    probe = tmp_path / "probe_run.py"
    probe.write_text("")
    plan = tmp_path / "plan.md"
    plan.write_text("## Review Focus\n\n- pkg: deep\n", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_PROBE_RUN", str(probe))
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: seen.append(cmd))
    assert commit_task.launch_probes("abc1234", str(plan))
    assert seen[-1][-6:] == ["--commit", "abc1234", "--categories", "deep", "--plan", str(plan)]
    commit_task.launch_probes("abc1234", str(tmp_path / "missing.md"))
    assert "--plan" not in seen[-1]
    commit_task.launch_probes("abc1234")
    assert "--plan" not in seen[-1]


def test_probe_files_line(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", SRC)
    write(repo, "tests/test_a.py", TEST)
    write(repo, DEEP, TEST)
    write(repo, ADAPTER, "X = 1\n")
    r = checkpoint(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    sha, line = r.stdout.splitlines()
    assert len(sha) == 40
    assert line == (f"T1: probe files committed: {ADAPTER} {DEEP} (a background probe_run wrote them; "
                    "a false positive: sl probe_run --dismiss test_probe_deep_1 --plan plan.md)")


def test_no_line_without_probe_files(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", SRC)
    write(repo, "tests/test_a.py", TEST)
    r = checkpoint(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == r.stdout.strip().splitlines()[0] + "\n" and len(r.stdout.strip()) == 40


def test_adapter_only_line(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", SRC)
    write(repo, "tests/test_a.py", TEST)
    write(repo, ADAPTER, "X = 1\n")
    r = checkpoint(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[1] == f"T1: probe files committed: {ADAPTER} (a background probe_run wrote them)"


def test_unchanged_recheckpoint_no_line(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", SRC)
    write(repo, "tests/test_a.py", TEST)
    write(repo, DEEP, TEST)
    assert checkpoint(repo, "T1").returncode == 0
    r = checkpoint(repo, "T1")
    assert r.returncode == 0
    assert "no change since" in r.stdout and "probe files" not in r.stdout
