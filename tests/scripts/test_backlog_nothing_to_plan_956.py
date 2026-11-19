"""#956: a plan that leaves out an in-progress issue says `already shipped or in progress`; commands/backlog.md step 2 names the lines."""
from pathlib import Path

import pytest
from test_backlog_cli import bk, cli, bs, bl  # noqa: F401
import backlog_intake as bi  # noqa: E402

DOC = Path(__file__).resolve().parents[2] / "commands" / "backlog.md"
S956 = ("An issue another session builds (a Jira status in the In Progress category, or a worktree or branch naming it) is not planned: "
        "`in progress: #N (<status, worktree or branch>): not planned, another session builds it; sl backlog plan --issues N --add plans it anyway`; "
        "a pinned one is planned anyway with `in progress?: #N (<status, worktree or branch>): planned anyway (pinned); sl backlog skip N drops it`. "
        "A plan that leaves every issue out says `nothing to plan: every issue is already shipped`, or "
        "`nothing to plan: every issue is already shipped or in progress` when an issue another session builds was among them.")
IP = {"number": 1, "title": "One", "reason": "not planned (in progress: branch 1-x)"}
IP_LINE = "in progress: #1 (branch 1-x): not planned, another session builds it; sl backlog plan --issues 1 --add plans it anyway"
SHIPPED = {"number": 2, "title": "Two", "reason": "not planned (shipped: PR #41)"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: [])


def test_in_progress_left_out_names_it(bk, capsys, monkeypatch):
    monkeypatch.setattr(bi, "split_shipped", lambda *a, **k: ([], [IP, SHIPPED], [IP_LINE]))
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert IP_LINE in out
    assert "nothing to plan: every issue is already shipped or in progress" in out.splitlines()
    assert not any(c[0] in ("spawn", "send") for c in bk.calls)


def test_shipped_only_keeps_text(bk, capsys, monkeypatch):
    monkeypatch.setattr(bi, "split_shipped", lambda *a, **k: ([], [SHIPPED], ["already shipped: #2 named by merged PR #41"]))
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert "nothing to plan: every issue is already shipped" in out.splitlines()
    assert "or in progress" not in out


def test_command_step2_names_lines():
    line = next(l for l in DOC.read_text(encoding="utf-8").splitlines() if l.startswith("2. "))
    assert " " + S956 + " An urgent issue while batches run: " in line
