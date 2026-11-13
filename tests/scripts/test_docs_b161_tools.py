# tests/scripts/test_docs_b161_tools.py: docs/tools.md carries the B161 paragraphs (#667, #668)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_tools_doc_b161():
    text = (ROOT / "docs/tools.md").read_text()
    for needle in ("plan_tools.resolve_plan` resolves a folder through `run_plan`",
                   "is never held for its running owner",
                   "left uncommitted (changed while busy W3 (T6) runs; commit_task T5 again once it is done): F",
                   "history: no plan document (inline run); nothing recorded",
                   "tests (full, CI): <workflow> run <id> green on HEAD <sha> (<url>)"):
        assert needle in text, needle
    assert any(
        ln.startswith("`--plan` takes a plan file or a run folder") for ln in text.splitlines()
    )
