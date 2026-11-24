"""A bare run_tests --wait finds the tree's pointer from a subfolder (#1069)."""
from test_run_tests_wait import RUN_TESTS, run, setup, start


def test_bare_wait_from_subfolder(tmp_path):
    setup(tmp_path)
    _, a = start(tmp_path)
    assert run(RUN_TESTS, "--wait", a, "--timeout", "60", cwd=tmp_path).returncode == 0
    sub = tmp_path / "sub"
    sub.mkdir()
    cp = run(RUN_TESTS, "--wait", "--timeout", "60", cwd=sub)
    assert cp.returncode == 0, cp.both
    assert "tests (full): 1 passed" in cp.err, cp.both
