from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "tools.md"


def test_tools_md_names_the_trims():  # O(1)
    text = DOC.read_text(encoding="utf-8")
    for needle in (
        "build error: <file>:<line>: <message>",
        "titles and files",
        "at READY",
        "any other file",
        "read the file for the rest",
    ):
        assert needle in text, needle
