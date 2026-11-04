"""Coordinator guard: nohup, timeout, nice and exec run the command after them, which is judged (#121)."""
import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401


@pytest.mark.parametrize("cmd", [
    "nohup rm src/a.py",
    "nice rm src/a.py",
    "nice -n 5 rm src/a.py",
    "nice -10 rm src/a.py",
    "nice --adjustment=5 rm src/a.py",
    "timeout 5 rm src/a.py",
    "timeout -s KILL 5s rm src/a.py",
    "timeout --kill-after=2 5 rm src/a.py",
    "timeout --preserve-status 1m sed -i s/a/b/ src/a.py",
    "exec rm src/a.py",
    "exec -a name rm src/a.py",
    "nohup sed -i s/a/b/ src/a.py",
    "sudo nice rm src/a.py",
    "nohup nice timeout 5 cp /tmp/x src/a.py",
    "timeout 5 bash <<'EOF'\nrm src/a.py\nEOF",
])
def test_wrapped_writes_block(proj, cmd):
    assert bash(proj, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    "nohup sleep 1 > /tmp/log 2>&1",
    "timeout 5 sleep 1",
    "timeout 5 rm /tmp/x",
    "nice -n 5 echo hi > docs/plans/p.md",
    "exec 3>&1",
    "nohup rm .superlite/tmp.json",
])
def test_wrapped_harmless_commands_pass(proj, cmd):
    assert bash(proj, cmd).returncode == 0, cmd
