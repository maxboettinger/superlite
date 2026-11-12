import json

import pytest

from test_rewrite_test_runs import denied, proj, run  # noqa: F401

TEST_CMD = {
    "test": "remote-run exec --timeout 30 'bun install --frozen-lockfile >/dev/null 2>&1 && bun test'",
    "test_file": "remote-run exec --timeout 30 'bun test {file}'",
}


@pytest.fixture
def project(proj):
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps(TEST_CMD))
    return proj


@pytest.mark.parametrize("cmd", [
    "remote-run exec --timeout 30 'bun install --frozen-lockfile >/dev/null 2>&1 && bunx prettier --check .'",
    "remote-run exec 'bun install --frozen-lockfile >/dev/null'",
    'remote-run exec "bun install >/dev/null 2>&1; bun run typecheck"',
])
def test_quoted_install_redirect_passes(project, cmd):
    r = run(project, cmd)
    assert r.returncode == 0 and r.stderr == "", (r.returncode, r.stderr)


@pytest.mark.parametrize("cmd", [
    "remote-run exec 'bun test >/dev/null'",
    "remote-run exec --timeout 30 'bun test' >/dev/null",
    "remote-run exec 'bun install >/dev/null 2>&1 && npx vitest run >/dev/null'",
    "pytest -q >/dev/null",
])
def test_hidden_runner_output_is_denied(project, cmd):
    denied(run(project, cmd))
