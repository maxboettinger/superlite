"""#551: a lead that does not start blocks only its own batch; the batches named after it still start."""
import sys
from backlog_fixtures import batch as b
from test_backlog_run import bk, get, put, run  # noqa: F401  (bk is a fixture)

LINE = "BLOCKED: W9 account c3 startup: agent target pane w:p{n} is not an available shell; retried once; retried in a fresh pane after W8"


def flaky(monkeypatch, fail_on):
    mod = sys.modules["fleet_lead"]; orig, n = mod.spawn_lead, [0]
    def spawn(main_sd, wt, model="opus", env=None, rc=None):
        n[0] += 1
        if n[0] in fail_on:
            print(LINE.format(n=n[0])); raise SystemExit(3)
        return orig(main_sd, wt, model, env, rc)
    monkeypatch.setattr(mod, "spawn_lead", spawn)


def test_a_failed_lead_does_not_stop_the_batches_after_it(bk, capsys, monkeypatch):
    put(bk, b("B92", ["a.py"]), b("B93", ["b.py"]), b("B94", ["c.py"]))
    flaky(monkeypatch, {2})
    rc, out = run(capsys, "start", "B92", "B93", "B94", "--cap", "8")
    w92, w94 = bk.root / ".claude" / "worktrees" / "superlite-b92-t", bk.root / ".claude" / "worktrees" / "superlite-b94-t"
    assert rc == 2
    assert out.splitlines() == [f"B92 running lead=W1 worktree={w92}", LINE.format(n=2),
                                "BLOCKED: B93 lead did not start; B93 keeps its state, rerun sl backlog start B93",
                                f"B94 running lead=W2 worktree={w94}"]
    assert [get(bk, x)["state"] for x in ("B92", "B93", "B94")] == ["running", "planned", "running"]
    assert get(bk, "B93")["lead"] is None
    assert ("send", "W2", "lead.md", "B94") in bk.calls and not any(c[0] == "send" and c[-1] == "B93" for c in bk.calls)


def test_every_lead_failing_keeps_each_batch_and_exits_2(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"], "parked", reason="tui red", worktree=str(bk.root / ".claude" / "worktrees" / "superlite-b1-t")), b("B2", ["b.py"]))
    flaky(monkeypatch, {1, 2})
    rc, out = run(capsys, "start", "B1", "B2")
    assert rc == 2
    assert [x for x in out.splitlines() if not x.startswith("BLOCKED: W9 ")] == [
        "BLOCKED: B1 lead did not start; B1 keeps its state, rerun sl backlog start B1",
        "BLOCKED: B2 lead did not start; B2 keeps its state, rerun sl backlog start B2"]
    assert (get(bk, "B1")["state"], get(bk, "B1")["reason"], get(bk, "B2")["state"]) == ("parked", "tui red", "planned")
