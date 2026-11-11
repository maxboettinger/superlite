"""B95 (#450, B88 and B92 follow-ups): testing, language and hooks docs name 1.5.79 to 1.5.103."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTING = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
LANGUAGE = (ROOT / "docs" / "language.md").read_text(encoding="utf-8")
HOOKS = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")


def has(text, *tokens):
    missing = [t for t in tokens if t not in text]
    assert not missing, missing


def test_testing_store_line_is_per_checkout():
    assert "the file list of the last green run live in one store" not in TESTING
    has(TESTING, "each checkout's last green file list")


def test_testing_unit_layer():
    has(TESTING, "run --wait", "SUPERLITE_UNIT_WAIT", "unit: running", "exit 4", "--limit", ".output.log",
        "no tests ran")


def test_language_xcode_and_swift():
    has(LANGUAGE, "membership", "not in a test target", "file:line", "(crashed)")


def test_hooks_guard():
    has(HOOKS, "Refused command:", "rmdir", "+")
