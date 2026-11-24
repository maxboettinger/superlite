# tests/scripts/test_backlog_brief_steps_1110.py
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"repo": "o/r", "max_batches": 3}


def test_triage_run_by_source():
    assert bb.triage_run(False) == bb.TRIAGE_RUN
    assert '{"issues": [<n>], "runs": "main"' in bb.TRIAGE_RUN
    assert bb.triage_run(True) == bb.TRIAGE_RUN.replace('{"issues": [<n>], ', '{"issues": ["<KEY>"], ')


def test_jira_triage_steps_name_keys():
    t = bb.triage_brief([{"number": "PIX-1272", "title": "Fix login", "body": "b"}], CTX)
    assert '{\"issues\": [\"<KEY>\"], \"runs\": \"main\"' in t
    assert '{"issues": [<n>], "runs"' not in t


def test_github_triage_steps_keep_numbers():
    t = bb.triage_brief([{"number": 3, "title": "T", "body": "b"}], CTX)
    assert '{"issues": [<n>], "runs": "main"' in t and '"<KEY>"' not in t


def test_note_head_names_note_command():
    assert bb.NOTE_HEAD.startswith("Standing note from main (sl backlog note):")
