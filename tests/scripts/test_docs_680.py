"""metrics.md and tools.md describe the batch cost record (#680)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METRICS = (ROOT / "skills" / "subagent-driven-development" / "metrics.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def test_thinking_line_fixed():
    assert "thinking tokens are not stored" not in METRICS
    assert "output_tokens_details" in METRICS


def test_row_fields_named():
    for word in ("batch-costs.jsonl", "blocked_wait_s", "wakeups", "workers_total", "grade", "letter", "unmeasured"):
        assert word in METRICS, word


def test_tools_lines():
    for word in ("batch_cost", "main_cost", "report --batches"):
        assert word in TOOLS, word
