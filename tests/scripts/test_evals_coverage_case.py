"""brainstorm-coverage eval: hidden gaps in the spec, graders read the design doc."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_evals_suite import frontmatter  # noqa: E402

CASE = Path(__file__).resolve().parents[2] / "evals/brainstorm-coverage"
GRADERS = CASE / "graders"


def test_spec_hides_the_graded_gaps(tmp_path):
    subprocess.run(["bash", str(CASE / "scaffold.sh")], cwd=tmp_path, check=True)
    spec = (tmp_path / "docs/spec.md").read_text().lower()
    assert "cron" in spec and "notes import" in spec
    for word in ("migrat", "rollback", "roll back", "untrusted", "secur", "limit", "size", "error", "fail", "lock"):
        assert word not in spec, word
    import json
    assert len(json.loads((tmp_path / "notes.json").read_text())) == 2
    assert "json.load" in (tmp_path / "src/notes/store.py").read_text()


def test_graders_read_the_design_doc():
    for name in ("raises-limits", "raises-migration", "raises-rollback", "raises-untrusted-input"):
        fm = frontmatter(GRADERS / f"{name}.md")
        assert fm["type"] == "llm", name
        assert "source: file" in fm["focus"] and "docs/design.md" in fm["focus"], name
    fm = frontmatter(GRADERS / "design-written.md")
    assert fm["type"] == "file_exists" and fm["path"] == "docs/design.md"
    assert not (GRADERS / "raises-errors.md").exists()
    assert not (GRADERS / "skill-fired.md").exists()


def test_reads_coverage_stays_with_only():
    fm = frontmatter(GRADERS / "reads-coverage.md")
    assert fm["type"] == "tool_used" and fm["tool"] == "Read" and fm["arm"] == "with-only"


def test_prompt_is_unattended():
    prompt = (CASE / "prompt.md").read_text()
    assert prompt.startswith("/superlite:brainstorming ")
    for s in ("decide yourself", "docs/design.md", "no plan and no code"):
        assert s in prompt
    case = (CASE / "case.yaml").read_text()
    assert "Write" in case and "AskUserQuestion" not in case
