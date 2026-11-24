"""testcmd gives a maxapp remote test's per-file command the same maxapp remote form (#1147)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import testcmd  # noqa: E402

PIX_TEST = "maxapp remote --timeout 40 'bun install --frozen-lockfile >/dev/null 2>&1 && bunx vitest run --reporter=default'"
PIX_FILE = "bunx vitest run {files} --reporter=default --reporter=junit --outputFile.junit={junit}"
PIX_REMOTE = ("maxapp remote --timeout 40 --kind file 'bun install --frozen-lockfile >/dev/null 2>&1 && "
              "bunx vitest run {files} --reporter=default --reporter=junit --outputFile.junit={junit}'")
NOTE = ('testcmd: .superlite/test-cmd.json: "test" runs through maxapp remote but "test_file" runs on this machine, '
        f'so run_tests --fast runs here; to run it there too, set "test_file" to: {PIX_REMOTE}')


def project(tmp_path, cfg):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def test_remote_test_file_keeps_setup_steps():
    assert testcmd.remote_test_file(PIX_TEST, PIX_FILE) == PIX_REMOTE


def test_remote_test_file_without_setup_steps():
    test = "maxapp remote --timeout 40 'uv run --group dev python -m pytest tests -q'"
    file = "uv run --group dev python -m pytest {files} -q --junitxml={junit}"
    assert testcmd.remote_test_file(test, file) == (
        "maxapp remote --timeout 40 --kind file 'uv run --group dev python -m pytest {files} -q --junitxml={junit}'")


def test_remote_test_file_keeps_every_setup_step():
    test = "maxapp remote 'cd app && bun install && bunx vitest run'"
    assert testcmd.remote_test_file(test, "bunx vitest run {files}") == (
        "maxapp remote --kind file 'cd app && bun install && bunx vitest run {files}'")


def test_remote_test_file_options():
    test = "CI=1 maxapp remote --host box --kind full --fetch out --no-cache -- 'npm test'"
    assert testcmd.remote_test_file(test, "npm test -- {files}") == (
        "CI=1 maxapp remote --host box --no-cache --kind file 'npm test -- {files}'")


def test_remote_test_file_other_operators_keep_no_setup():
    test = "maxapp remote 'bun install; bunx vitest run | tee log'"
    assert testcmd.remote_test_file(test, "bunx vitest run {files}") == "maxapp remote --kind file 'bunx vitest run {files}'"


def test_remote_test_file_several_words():
    test = "maxapp remote --timeout 5 bunx vitest run"
    assert testcmd.remote_test_file(test, "bunx vitest run {files}") == (
        "maxapp remote --timeout 5 --kind file 'bunx vitest run {files}'")


def test_remote_test_file_without_command_after_options():
    assert testcmd.remote_test_file("maxapp remote --timeout 40", "bunx vitest run {files}") == (
        "maxapp remote --timeout 40 --kind file 'bunx vitest run {files}'")
    assert testcmd.remote_test_file("maxapp remote", "npm test -- {files}") == "maxapp remote --kind file 'npm test -- {files}'"
    assert testcmd.remote_test_file("maxapp remote --timeout", "bunx vitest run {files}") is None


def test_remote_test_file_none_cases():
    assert testcmd.remote_test_file("bunx vitest run", PIX_FILE) is None
    assert testcmd.remote_test_file(PIX_TEST, PIX_REMOTE) is None
    assert testcmd.remote_test_file(PIX_TEST, None) is None
    assert testcmd.remote_test_file(PIX_TEST, "") is None
    assert testcmd.remote_test_file(None, PIX_FILE) is None
    assert testcmd.remote_test_file("maxapp remote 'unclosed", PIX_FILE) is None
    assert testcmd.remote_test_file("maxapp test", PIX_FILE) is None
    assert testcmd.remote_test_file("maxapp remote --timeout", PIX_FILE) is None


def test_write_wraps_local_test_file(tmp_path, capsys):
    assert testcmd.main(["--write", "--root", str(tmp_path), "--test", PIX_TEST, "--test-file", PIX_FILE]) == 0
    cfg = json.loads((tmp_path / ".superlite" / "test-cmd.json").read_text(encoding="utf-8"))
    assert cfg["test"] == PIX_TEST
    assert cfg["test_file"] == PIX_REMOTE
    assert f'testcmd: "test" runs through maxapp remote, so "test_file" does too: {PIX_REMOTE}' in capsys.readouterr().err


def test_write_keeps_a_remote_or_a_local_pair(tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert testcmd.main(["--write", "--root", str(a), "--test", PIX_TEST, "--test-file", PIX_REMOTE]) == 0
    assert testcmd.main(["--write", "--root", str(b), "--test", "bunx vitest run", "--test-file", PIX_FILE]) == 0
    assert json.loads((a / ".superlite" / "test-cmd.json").read_text(encoding="utf-8"))["test_file"] == PIX_REMOTE
    assert json.loads((b / ".superlite" / "test-cmd.json").read_text(encoding="utf-8"))["test_file"] == PIX_FILE
    assert "maxapp remote" not in capsys.readouterr().err


def test_testcmd_names_an_existing_mismatch(tmp_path, capsys):
    project(tmp_path, {"language": "typescript", "test": PIX_TEST, "test_file": PIX_FILE, "junit": "{junit}"})
    assert testcmd.remote_note(tmp_path) == NOTE[len("testcmd: "):]
    assert testcmd.main(["--root", str(tmp_path)]) == 0
    assert NOTE in capsys.readouterr().err
    assert testcmd.main(["--propose", "--root", str(tmp_path)]) == 0
    assert NOTE in capsys.readouterr().err
    assert testcmd.main(["--write", "--root", str(tmp_path)]) == 2
    assert NOTE in capsys.readouterr().err


def test_testcmd_quiet_when_test_file_is_remote(tmp_path, capsys):
    project(tmp_path, {"language": "typescript", "test": PIX_TEST, "test_file": PIX_REMOTE})
    assert testcmd.remote_note(tmp_path) == ""
    assert testcmd.main(["--root", str(tmp_path)]) == 0
    assert "runs on this machine" not in capsys.readouterr().err


def test_resolve_runs_the_written_remote_form(tmp_path):
    project(tmp_path, {"language": "typescript", "test": PIX_TEST, "test_file": PIX_REMOTE})
    assert testcmd.resolve(tmp_path, ["src/a.test.ts"])["command"] == PIX_REMOTE.replace("{files}", "src/a.test.ts")


def test_resolve_keeps_a_configured_local_test_file(tmp_path):
    project(tmp_path, {"language": "typescript", "test": PIX_TEST, "test_file": PIX_FILE})
    assert testcmd.resolve(tmp_path, ["src/a.test.ts"])["command"] == PIX_FILE.replace("{files}", "src/a.test.ts")


def test_run_tests_uses_testcmd_remote_helpers():
    import run_tests
    assert run_tests.is_remote_command is testcmd.is_remote_command
    assert run_tests._remote_at is testcmd.remote_at
    assert run_tests.REMOTE_VALUE_OPTS is testcmd.REMOTE_VALUE_OPTS
    assert run_tests.REMOTE_FLAGS is testcmd.REMOTE_FLAGS


def test_tools_md_row_pins_the_messages():
    rows = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
    at = next(i for i, line in enumerate(rows) if line.startswith("| `testcmd` |"))
    row = rows[at + 1]
    assert row.startswith("| `testcmd` remote test_file (#1147) |")
    source = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "testcmd.py").read_text(encoding="utf-8")
    for text in ('"test" runs through maxapp remote but "test_file" runs on this machine',
                 '"test" runs through maxapp remote, so "test_file" does too'):
        assert text in row
        assert text in source
    assert "--kind file" in row
