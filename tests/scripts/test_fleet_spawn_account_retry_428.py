"""#428: a stalled prime is waited for longer and resent once; a start that stays slow is retried once on another account."""
import json, os
import pytest
from test_fleet import world  # noqa: F401
from test_fleet_for_dispatch import dwld, _go, FRESH  # noqa: F401
import fleet
REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted herdr replies need the in-process fake")
STALL = ("agent_prompt_stalled", "agent prompt produced no observed working or blocked state within 5000 ms; current status is idle")
APP = "timed out waiting for app response after 5000 ms"


def nm(w, wid):
    return fleet.fs.agent_name(w.sd, wid)


def workers(w):
    return json.loads((w.sd / "fleet.json").read_text())["workers"]


def stall(w, times):
    """prompt raises the stall for the first times[wid] prompts to that worker, then answers as the fake; returns the prompted names."""
    orig, seen, limit = w.fh.prompt, [], {nm(w, k): n for k, n in times.items()}
    def prompt(name, text, until, ms):
        seen.append(name)
        if seen.count(name) <= limit.get(name, 0):
            raise w.fh.HerdrError(*STALL)
        return orig(name, text, until, ms)
    w.fh.prompt = prompt
    return seen


def late(w, reply):
    """The wait for a late start (until working or blocked): `reply` is the state herdr reports, or "timeout" to raise herdr's timeout."""
    orig = w.fh.wait_state
    def wait(name, until, ms):
        if list(until) == ["working", "blocked"]:
            w.fh.calls.append(("late_wait", name, ms))
            if reply == "timeout":
                raise w.fh.HerdrError("timeout", "agent wait timed out")
            return reply
        return orig(name, until, ms)
    w.fh.wait_state = wait


def blank(w, *wids):
    """These workers' screens never show READY."""
    orig, names = w.fh.read_screen, {nm(w, k) for k in wids}
    w.fh.read_screen = lambda name, lines=40, source="visible": "\n" if name in names else orig(name, lines, source)


def first_try(err):
    return [l for l in err.splitlines() if l.startswith("W1 ")]


def test_a_prime_that_starts_late_is_not_resent(world):
    fleet.main(["on"]); seen = stall(world, {"W1": 9}); late(world, "working")
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    assert seen == [nm(world, "W1")] and fleet.STALL_WAIT_MS == 30000
    assert ("late_wait", nm(world, "W1"), fleet.STALL_WAIT_MS) in world.fh.calls
    assert ("wait_state", nm(world, "W1"), ["idle", "done", "blocked"]) in world.fh.calls


def test_ready_on_screen_after_the_late_wait_is_not_resent(world):
    fleet.main(["on"]); seen = stall(world, {"W1": 9}); late(world, "timeout")
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1" and seen == [nm(world, "W1")]


def test_no_late_start_resends_the_prime_once(world):
    fleet.main(["on"]); seen = stall(world, {"W1": 1}); late(world, "timeout")
    orig = world.fh.read_screen
    world.fh.read_screen = lambda name, lines=40, source="visible": orig(name, lines, source) if len(seen) >= 2 else "\n"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    assert seen == [nm(world, "W1")] * 2 and "W2" not in workers(world)


def test_a_late_blocked_state_is_no_ready_and_not_retried(world, capsys):
    fleet.main(["on"]); capsys.readouterr(); stall(world, {"W1": 9}); late(world, "blocked")
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and capsys.readouterr().out.startswith("BLOCKED: W1 no READY")
    assert list(workers(world)) == ["W1"]


def test_a_second_stall_retries_once_on_another_account(world, capsys):
    fleet.main(["on"]); capsys.readouterr()
    seen = stall(world, {"W1": 2}); late(world, "timeout"); blank(world, "W1")
    w = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert (w["id"], w["account"]) == ("W2", "claude1")
    ws = workers(world)
    assert (ws["W1"]["state"], ws["W1"]["account"], ws["W2"]["state"]) == ("blocked", "claude3", "ready")
    cap = capsys.readouterr()
    assert cap.out.splitlines() == [f"W2 account=claude1 pane={w['pane_id']} agent={w['agent']}"]
    assert first_try(cap.err) == [f"W1 account claude3 startup: {STALL[0]}: {STALL[1]}; retrying on account claude1"]
    assert seen == [nm(world, "W1")] * 2 + [nm(world, "W2")]
    assert ("close_pane", ws["W1"]["pane_id"]) in world.fh.calls
    assert "fleet spawn retry: startup: agent_prompt_stalled" in (world.sd / "incidents.jsonl").read_text()


def test_with_no_other_account_the_retry_uses_the_same_one(world, capsys):
    fleet.main(["on", "--accounts", "claude3"]); capsys.readouterr()
    stall(world, {"W1": 2}); late(world, "timeout"); blank(world, "W1")
    w = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert (w["id"], w["account"]) == ("W2", "claude3")
    cap = capsys.readouterr()
    assert first_try(cap.err)[0].endswith("; retrying on account claude3") and "BLOCKED" not in cap.out


def test_a_retry_that_fails_again_blocks_naming_the_first_try(world, capsys):
    fleet.main(["on"]); capsys.readouterr()
    seen = stall(world, {"W1": 2, "W2": 2}); late(world, "timeout"); blank(world, "W1", "W2")
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3
    assert capsys.readouterr().out.splitlines() == [f"BLOCKED: W2 account claude1 startup: {STALL[0]}: {STALL[1]}; retried after W1 on claude3"]
    assert len(seen) == 4 and sorted(workers(world)) == ["W1", "W2"]
    assert {v["state"] for v in workers(world).values()} == {"blocked"}


@pytest.mark.parametrize("code,message", [("timeout", "herdr agent start timed out"), ("exit", APP)])
def test_a_slow_start_retries_on_another_account(world, capsys, code, message):
    fleet.main(["on"]); capsys.readouterr()
    orig, n = world.fh.start_agent, [0]
    def start(*a, **k):
        n[0] += 1
        if n[0] == 1:
            raise world.fh.HerdrError(code, message)
        return orig(*a, **k)
    world.fh.start_agent = start
    w = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert (w["id"], w["account"], n[0]) == ("W2", "claude1", 2)
    assert first_try(capsys.readouterr().err)[0].endswith("; retrying on account claude1")


def test_other_startup_errors_get_no_account_retry(world, capsys):
    fleet.main(["on"]); capsys.readouterr()
    world.fh.start_error = "agent_not_ready"; world.fh.screen = "Select login method\n"
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    cap = capsys.readouterr()
    assert e.value.code == 3 and cap.out.startswith("BLOCKED: W1 account claude3 startup: Select login method")
    assert "retrying" not in cap.err and list(workers(world)) == ["W1"]


def test_for_dispatch_sends_to_the_retried_worker(dwld, capsys):
    fleet.main(["on"]); capsys.readouterr()
    stall(dwld, {"W1": 2}); late(dwld, "timeout"); blank(dwld, "W1")
    dwld.lines = [("T2", FRESH)]
    assert _go(dwld) == 0
    assert capsys.readouterr().out.splitlines() == ["W2 T2 sent"]
