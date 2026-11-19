# tests/scripts/test_fleet_remote_prompt_931.py
import json, sys
import pytest
from test_fleet_remote_worker import world, started  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote_worker as rw  # noqa: E402

MSG = "Read the brief at /x/y/brief.md and answer it"
STATUS = "timed out waiting for agent status"


def script(world, errors, state="idle", screen="READY\n"):
    fh, calls = world.fh, []
    def prompt(name, text, until, timeout_ms):
        calls.append((text, until, timeout_ms))
        if errors:
            raise fh.HerdrError("timeout", errors.pop(0))
    fh.prompt, fh.agent_state, fh.screen = prompt, (lambda name: state), screen
    return calls


def test_status_timeout_idle_empty_resends_once(world):
    calls = script(world, [STATUS])
    rw._prompt("sl-w1", MSG)
    assert calls == [(MSG, ["working"], rw.REMOTE_PROMPT_MS)] * 2


def test_status_timeout_working_counts_as_sent(world):
    calls = script(world, [STATUS], state="working")
    rw._prompt("sl-w1", MSG)
    assert len(calls) == 1


def test_status_timeout_text_on_screen_raises(world):
    calls = script(world, [STATUS], screen="> " + MSG[:40] + "\n")
    with pytest.raises(world.fh.HerdrError):
        rw._prompt("sl-w1", MSG)
    assert len(calls) == 1


def test_status_timeout_second_failure_raises(world):
    calls = script(world, [STATUS, STATUS])
    with pytest.raises(world.fh.HerdrError, match="agent status"):
        rw._prompt("sl-w1", MSG)
    assert len(calls) == 2


def test_status_timeout_sign_in_raises_signed_out(world):
    calls = script(world, [STATUS], screen="Please run /login\n")
    with pytest.raises(world.fh.HerdrError) as e:
        rw._prompt("sl-w1", MSG)
    assert e.value.code == rw.SIGNED_OUT and len(calls) == 1


@pytest.mark.parametrize("account,msg", [("claude2@box", "account claude2 is not signed in on box; run /login for it there"),
                                         ("", "the account is signed out on this machine; run /login for it there")])
def test_signed_out_prompt_names_account(world, account, msg):
    started(world)
    p = world.sd / "fleet.json"
    d = json.loads(p.read_text()); d["workers"]["W1"]["account"] = account; p.write_text(json.dumps(d))
    b = world.sd / "briefs" / "q.md"; b.write_text("question")
    script(world, [STATUS], screen="Please run /login\n")
    with pytest.raises(world.fh.HerdrError) as e:
        rw.send_brief(world.sd, "W1", str(b), "Q1")
    assert e.value.code == rw.SIGNED_OUT and e.value.message == msg
