import sys
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402

def test_status_row_joins_issue_numbers_with_a_space():
    b = {"id": "B1", "issues": [1, 2], "files": [], "depends": [], "decisions": [], "state": "parked", "answers": {},
         "lead": None, "pr": None, "reason": "r"}
    d = {**bs.default(), "repo": "o/r", "batches": [b]}
    assert "B1 | #1 #2 | parked | - | - | r" in bs.status_lines(d)
