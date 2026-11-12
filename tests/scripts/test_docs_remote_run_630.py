"""#630: the remote full run and the unit-layer resume are documented."""
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_language_md_documents_the_remote_full_run():
    text = (DOCS / "language.md").read_text(encoding="utf-8")
    para = next(p for p in text.split("\n\n") if p.startswith("**Remote full run.**"))
    for needle in ('"test_file"', '"lock": false', "maxapp remote", "install step", "a fast run resolves to the remote",
                   "scripts/test_layers.py run unit", "unit: running", "digests taken before the run"):
        assert needle in para, needle


def test_testing_md_documents_the_resume():
    text = (DOCS / "testing.md").read_text(encoding="utf-8")
    assert "Running `run unit` again waits on that same run" in text
