"""#533: docs name the user-level default test command."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANGUAGE = (ROOT / "docs" / "language.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SETUP = (ROOT / "commands" / "setup.md").read_text(encoding="utf-8")
LANG_FIRST = "(`.superlite/test-cmd.json`, else the user-level default `~/.config/superlite/test-cmd.json`, else detection from its marker files)"
LANG_PARA = "**User-level default.** `~/.config/superlite/test-cmd.json` (`SUPERLITE_USER_TEST_CMD` names another file) holds one entry per language"
TOOLS_ROW = "else the user-level default `~/.config/superlite/test-cmd.json` (one entry per detected language, `swift` for an Xcode project too; `SUPERLITE_USER_TEST_CMD` names another file), else detection"
SETUP_LINE = "report its `command` and `origin`"


def test_language_md():
    assert LANG_FIRST in LANGUAGE and LANG_PARA in LANGUAGE
    assert "the single file on the worker's machine, the full suite on the remote runner" in LANGUAGE


def test_tools_row():
    row = next(ln for ln in TOOLS.splitlines() if ln.startswith("| `testcmd` |"))
    assert TOOLS_ROW in row and "`origin`" in row
    assert "`related` is set. Wave 0 (T0) runs it as the check that `run_tests` detects the stack." in row


def test_setup_md():
    assert SETUP_LINE in SETUP and "~/.config/superlite/test-cmd.json" in SETUP
