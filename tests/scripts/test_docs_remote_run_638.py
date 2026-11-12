"""#638: the remote full run counts, marker runs, seeded test-cmd and the stamp are documented."""
from pathlib import Path

LANG = Path(__file__).resolve().parents[2] / "docs" / "language.md"


def _para(head):
    text = LANG.read_text(encoding="utf-8")
    return next(p for p in text.split("\n\n") if p.startswith(head))


def test_remote_paragraph_names_638():
    para = _para("**Remote full run.**")
    for needle in ("last pytest summary line", "FAILED", "job.sh: waiting for a free job slot", "-m EXPR", "test_file",
                   "test-cmd.seeded", "delete it to follow", "merge"):
        assert needle in para, needle


def test_configured_full_run_stamps():
    assert "never stamps" not in _para("**User-level default.**")
    para = _para("**Remote full run.**")
    assert "never stamps" not in para
    for needle in ("a green configured --full run", "stamps the unit layer"):
        assert needle in para, needle
