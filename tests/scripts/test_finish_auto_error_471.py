"""finish.read_stops: a commit_task exception's target carries the error (#471)."""
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402


def stops(tmp_path, file, line, context):
    p = tmp_path / "incidents.jsonl"
    p.write_text(json.dumps({"kind": "exception", "agent": "commit_task", "resolution": "open",
                             "file": file, "line": line, "context": context}) + "\n")
    return finish.read_stops(p)


def test_import_failure_target_carries_error(tmp_path):
    got = stops(tmp_path, "notebooks/01_frame.py", 3,
                "T2: ModuleNotFoundError: No module named 'marimo'; nothing committed")
    assert got == [("exception", "commit_task", "notebooks/01_frame.py:3 ModuleNotFoundError: No module named 'marimo'")]


def test_line_zero_crash_target(tmp_path):
    got = stops(tmp_path, "pkg/a.py", 0, "T1: import check crashed under /x/python: boom; nothing committed")
    assert got[0][2] == "pkg/a.py import check crashed under /x/python: boom"


def test_scope_block_keeps_bare_file(tmp_path):
    got = stops(tmp_path, "src/x.py", 0, "T1: change outside Owns blocked by commit_task; nothing committed")
    assert got[0][2] == "src/x.py"


def test_long_reason_cut(tmp_path):
    assert stops(tmp_path, "a.py", 1, "T1: " + "E" * 300)[0][2] == "a.py:1 " + "E" * 150


def test_empty_reason_keeps_file(tmp_path):
    assert stops(tmp_path, "a.py", 2, "T1: ")[0][2] == "a.py:2"
