"""#712: a test-cmd.json holding only pythonpath is accepted without a note; sl testcmd runs without --root."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

IGNORED = 'test-cmd.json ignored: needs a JSON object with a "test" command'


def cfg(root, data):
    (root / ".superlite").mkdir(parents=True, exist_ok=True)
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps(data), encoding="utf-8")


def test_pythonpath_only_is_silent(tmp_path, capsys):
    cfg(tmp_path, {"pythonpath": ["tools"]})
    assert testcmd.read_config(tmp_path) is None
    assert capsys.readouterr().err == ""


def test_related_and_pythonpath_are_silent(tmp_path, capsys):
    cfg(tmp_path, {"pythonpath": ["tools"], "related": "tests/test_{src}.py"})
    assert testcmd.read_config(tmp_path) is None
    assert capsys.readouterr().err == ""


def test_other_keys_without_test_still_note(tmp_path, capsys):
    for data in ({"tests": "pytest"}, {"pythonpath": ["tools"], "test_file": "pytest {files}"}, {}):
        cfg(tmp_path, data)
        assert testcmd.read_config(tmp_path) is None
        assert capsys.readouterr().err.strip() == IGNORED


def test_cli_without_root_resolves_detection(tmp_path):
    cfg(tmp_path, {"pythonpath": ["tools"]})
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "testcmd.py")], capture_output=True, text=True,
                       cwd=tmp_path, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "ignored" not in r.stderr
    out = json.loads(r.stdout.splitlines()[0])
    assert out["language"] == "python" and out["origin"] == "detection"


def test_seed_note_quiet_for_an_own_copy_without_command(tmp_path, monkeypatch):
    main = tmp_path / "main"
    wt = tmp_path / "wt"
    cfg(main, {"language": "python", "test": "pytest"})
    cfg(wt, {"pythonpath": ["tools"]})
    monkeypatch.setattr(testcmd, "_main_checkout_root", lambda root: main)
    assert testcmd.seed_note(wt) == ""
    cfg(wt, {"language": "python", "test": "pytest -x"})
    assert "is the one that runs" in testcmd.seed_note(wt)
