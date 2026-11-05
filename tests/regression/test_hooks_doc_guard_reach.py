"""Final review: docs/hooks.md names what the Python guard judge reaches (piped and process-substitution programs,
7z, cpio, nested bodies), not the old bash guard's limits."""
from pathlib import Path

HOOKS = (Path(__file__).resolve().parents[2] / "docs" / "hooks.md").read_text(encoding="utf-8")


def test_guard_paragraph_matches_the_judge():
    assert "process substitution (`bash <(echo ...)`) is out of reach" not in HOOKS
    assert "other archivers (`7z`, `ditto`, `cpio`) are out of reach" not in HOOKS
    assert "bodies one level deep" not in HOOKS
    assert "is an unknown target, which blocks while the guard enforces" in HOOKS
    assert "up to 8 levels deep" in HOOKS
