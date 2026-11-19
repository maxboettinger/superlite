# tests/scripts/test_backlog_seed_doc_797.py
"""seed_test_cmd's docstring names the seed record backlog_run writes after it (#797)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import backlog  # noqa: E402


def test_seed_docstring_names_the_record():
    doc = backlog.seed_test_cmd.__doc__
    for s in (".superlite/test-cmd.seeded", "testcmd.record_seed", "backlog_run.cmd_start", "#638"):
        assert s in doc, s
