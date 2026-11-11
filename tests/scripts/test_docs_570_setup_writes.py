"""#566, #570: setup proposes and writes the test command; tools.md names --propose, --write, the lint warning and the hint."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETUP = (ROOT / "commands" / "setup.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def row(name):
    return next(ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |"))


def test_setup_proposes_and_writes():
    assert "When `origin` is not a `test-cmd.json` file, run `sl testcmd --propose`" in SETUP
    assert "on a yes `sl testcmd --write` writes it" in SETUP
    assert "report its `command` and `origin`" in SETUP and "~/.config/superlite/test-cmd.json" in SETUP


def test_tools_rows():
    assert "`--propose` prints `{\"proposal\", \"from\", \"target\", \"exists\"}`" in row("testcmd")
    assert "`--write [--test CMD] [--test-file T] [--language L]`" in row("testcmd")
    assert "`WARNING: TESTS: no test command resolves for this project; <ids> name no **Tests:** cmd=, ...`" in row("plan_tools")
