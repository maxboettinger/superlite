"""#243: the implementer prime asks for the SUPERLITE_REAL switch only on pytest projects."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RULE = ("- For each producer your task consumes, test against a fake. pytest projects only: make it **swappable**, "
        "one fixture returns the fake by default and the real implementation when `SUPERLITE_REAL=1`; "
        "the seam check reruns those Python tests against real code. Other test runners never see `SUPERLITE_REAL`: "
        "add no such switch; keep the fake in a test-support file, or test against the real implementation.")


@pytest.mark.parametrize("name", ["implementer.md", "implementer-haiku.md"])
def test_real_switch_rule_is_pytest_only(name):
    text = (ROOT / "agents" / name).read_text(encoding="utf-8")
    assert RULE in text.splitlines()
    assert text.count("SUPERLITE_REAL") == 2
    assert "swappable fake" not in text and "reruns the same tests" not in text
