from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")


def rows(*names):
    return "\n".join(l for l in DOC.splitlines() if any(l.startswith(f"| `{n}` |") for n in names))


def test_fleet_rows_name_retry_wait_and_owner():
    r = rows("fleet", "fleet_io")
    for s in ("retried in a fresh pane after", "already collected", "(reported:", "DEAD", "dead", "owner_session", "owner_pid", "state_dir", "fleet: off (moved to", "checker", "only task", "partial"):
        assert s in r, s
    assert "retried once on the same pane after 3 s" not in r


def test_state_and_workflow_rows():
    assert "foreign_worktree" in rows("state", "fleet", "orchestrator")
    assert "render" in rows("commit_task") and "--claim" in rows("commit_task")
    assert "--also" in rows("findings")
    assert "excluded" in rows("graphify_gate") and "graphify-out" in rows("graphify_gate")


def test_state_row_does_not_say_readers_pass_a_foreign_binding():
    r = rows("state")
    assert "while readers," not in r
    assert "a writer or reader" in r
