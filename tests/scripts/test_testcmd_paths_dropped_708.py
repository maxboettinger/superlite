"""testcmd marks --fast paths a command cannot take and names {files} for a {file} typo (#708)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import testcmd  # noqa: E402


def project(tmp_path, cfg):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def test_test_only_drops_paths(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh"})
    spec = testcmd.resolve(tmp_path, ["a.sh"])
    assert spec["command"] == "bash all.sh"
    assert spec["paths_dropped"] is True


def test_test_file_without_files_drops_paths(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh", "test_file": "bash one.sh"})
    spec = testcmd.resolve(tmp_path, ["a.sh"])
    assert spec["command"] == "bash one.sh"
    assert spec["paths_dropped"] is True


def test_files_template_keeps_paths(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh", "test_file": "bash run.sh {files}"})
    spec = testcmd.resolve(tmp_path, ["a.sh", "b.sh"])
    assert spec["command"] == "bash run.sh a.sh b.sh"
    assert spec["paths_dropped"] is False


def test_names_template_keeps_paths(tmp_path):
    project(tmp_path, {"language": "go", "test": "go test ./...", "test_file": "go test -run {names} ./..."})
    assert testcmd.resolve(tmp_path, ["pkg/a_test.go"])["paths_dropped"] is False


def test_no_paths_is_not_dropped(tmp_path):
    project(tmp_path, {"language": "shell", "test": "bash all.sh"})
    assert testcmd.resolve(tmp_path, [])["paths_dropped"] is False


def test_file_singular_note_once(tmp_path, capsys):
    project(tmp_path, {"language": "shell", "test": "bash all.sh", "test_file": "bash {file}"})
    testcmd.config_source(tmp_path)
    testcmd.config_source(tmp_path)
    err = capsys.readouterr().err
    assert err.count('testcmd: .superlite/test-cmd.json: "test_file" holds {file}; the placeholder for --fast paths is {files}') == 1


def test_file_note_for_test_key(tmp_path, capsys):
    project(tmp_path, {"language": "shell", "test": "bash {file}"})
    testcmd.resolve(tmp_path, ["a.sh"])
    assert '"test" holds {file}' in capsys.readouterr().err


def test_shell_variable_is_no_typo(tmp_path, capsys):
    project(tmp_path, {"language": "shell", "test": "for file in t/*.sh; do bash ${file}; done"})
    testcmd.config_source(tmp_path)
    assert "holds {file}" not in capsys.readouterr().err


def test_user_entry_note_names_its_file(tmp_path, monkeypatch, capsys):
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"python": {"test": "runner pytest", "test_file": "runner pytest {file}"}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(user))
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    cfg, src, origin = testcmd.config_source(proj)
    assert src == "user"
    assert f'testcmd: {origin}: "test_file" holds {{file}}' in capsys.readouterr().err
