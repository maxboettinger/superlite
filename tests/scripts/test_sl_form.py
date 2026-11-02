"""sl runs as an executable in every brief: no `bash <abs sl>` wording in owned docs or printed briefs."""
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SL = SCRIPTS / "sl"
BASH_FORM = re.compile(r'bash ("?\$SL"?|<abs|<skill-dir>|"<superlite-root>)')


def owned_docs():
    files = list((ROOT / "agents").glob("*.md"))
    files += list((ROOT / "skills").glob("*/SKILL.md"))
    files.append(ROOT / "skills" / "subagent-driven-development" / "fixing.md")
    files += list((ROOT / "commands").glob("*.md"))
    files.append(ROOT / "docs" / "tools.md")
    return files


def test_no_bash_form_in_owned_docs():
    for f in owned_docs():
        text = f.read_text(encoding="utf-8")
        assert not BASH_FORM.search(text), f.relative_to(ROOT).as_posix()


def test_wave0_prompt_executable():
    src = (SCRIPTS / "wave0.py").read_text(encoding="utf-8")
    assert "bash {sl}" not in src
    assert 'bash "$SL"' not in src


def test_prime_task_line_executable():
    src = (SCRIPTS / "build_prime.py").read_text(encoding="utf-8")
    assert "bash $SUPERLITE" not in src


def test_wait_line_executable(monkeypatch):
    import run_tests

    monkeypatch.setattr(run_tests, "__file__", "/x/run_tests.py")
    assert run_tests.wait_line("/p/s.json").startswith("wait: /x/sl run_tests --wait")
    monkeypatch.setattr(run_tests, "__file__", "/a b/run_tests.py")
    assert run_tests.wait_line("/p/s.json").startswith('wait: "/a b/sl" run_tests --wait')


@pytest.mark.skipif(os.name == "nt", reason="POSIX exec bit")
def test_sl_has_exec_bit():
    assert os.access(SL, os.X_OK)


def test_fallback_named():
    for rel in ("skills/using-superlite/references/claude-code-tools.md", "docs/tools.md"):
        t = (ROOT / rel).read_text(encoding="utf-8")
        assert "Permission denied" in t and "bash" in t, rel


def test_using_superlite_under_cap():
    assert len((ROOT / "skills" / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")) < 1500
