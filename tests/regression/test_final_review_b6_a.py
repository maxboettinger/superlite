"""Final review b6: a successful single-task commit prints only the SHA on stdout (the dropped foreign file goes to
stderr and is logged as a workaround incident); the hook's worktree walk ends on a relative cwd."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from test_commit_never_silent import commit, log_text, setup  # noqa: E402
from test_run_scripts import write  # noqa: E402
from test_state_hook_order import BASH, HOOK, SNIPPET  # noqa: E402


def test_stdout_is_exactly_the_sha(tmp_path):
    repo = setup(tmp_path, baseline=[])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "notes/x.txt", "mine\n")
    r = commit(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(r.stdout.strip().splitlines()) == 1 and len(r.stdout.strip()) >= 7
    assert "left uncommitted (outside every Owns): notes/x.txt" in r.stderr
    log = log_text(repo)
    assert len([ln for ln in log.splitlines() if "notes/x.txt" in ln and "workaround" in ln]) == 1


def test_relative_cwd_terminates(tmp_path):
    for cwd in ("relative", "a/b", "."):
        r = subprocess.run([BASH, "-c", SNIPPET, "x", '{"cwd":"%s"}' % cwd, str(HOOK)], cwd=tmp_path,
                           capture_output=True, text=True, timeout=20, env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
        assert r.returncode in (0, 1)
