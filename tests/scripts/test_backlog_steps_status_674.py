# tests/scripts/test_backlog_steps_status_674.py
import sys

from backlog_fixtures import batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402

S1 = {"issues": [12], "runs": "main", "command": "git lfs install", "why": "LFS hooks"}
S2 = {"runs": "user", "command": "gh auth login", "question": "Who signs in?"}
L1 = "step B2: main runs this: git lfs install (#12: LFS hooks)"


def data(*batches, **kw):
    return {**bs.default(), "repo": "o/r", "batches": list(batches), **kw}


def test_step_lines_examples():
    assert bs.step_lines([{"id": "B2", "state": "planned", "main_steps": [S1]}]) == [L1]
    assert bs.step_lines([{"id": "B3", "state": "running", "main_steps": [S2]}]) == ["step B3: Max runs this: gh auth login (decision: Who signs in?)"]
    assert bs.step_lines([{"id": "B4", "state": "shipped", "main_steps": [{"runs": "main", "command": "x"}]}]) == []


def test_status_lines_print_steps():
    d = data(b("B1", ["a.py"], "shipped"), b("B2", ["b.py"], main_steps=[S1]),
             outside=[{"number": 9, "title": "t", "reason": "too big"}])
    lines = bs.status_lines(d)
    i = lines.index(L1)
    assert lines[i - 1].startswith("B2 |") and lines[i + 1].startswith("too big")


def test_status_why_cut():
    why = " ".join(["word"] * 40)[:200]
    ln = bs.step_lines([{"id": "B2", "state": "planned", "main_steps": [{**S1, "why": why}]}])[0]
    cut = ln.split("(#12: ")[1][:-1]
    assert len(cut) <= 80 and why.startswith(cut) and cut.endswith("word")


def test_status_strips_control_chars():
    ln = bs.step_lines([{"id": "B2", "state": "planned", "main_steps": [{"runs": "main", "command": "a\x07b"}]}])
    assert ln == ["step B2: main runs this: a b"]


def test_plan_prints_steps():
    d = data(b("B2", ["b.py"], main_steps=[S1]))
    assert L1 in bs.status_lines(d)
