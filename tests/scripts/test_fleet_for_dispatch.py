# tests/scripts/test_fleet_for_dispatch.py
"""`fleet spawn --for-dispatch` (#181): one call per dispatch round runs dispatch, spawns a worker per `fresh` line and sends each line's tasks."""
import json, os, sys, types
import pytest
from test_fleet import FakeHerdr, world  # noqa: F401  (the one fake herdr and its fixture; T12 extends them)
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402
import fleet  # noqa: E402
import fleet_io  # noqa: E402
REAL = os.environ.get("SUPERLITE_REAL") == "1"
FRESH = "fresh tier=sonnet agent=superlite:implementer"


@pytest.fixture
def dwld(world, monkeypatch):
    """Fake dispatch by default (the lines are scripted through `dwld.lines`); real dispatch.run when SUPERLITE_REAL=1."""
    if not REAL:
        monkeypatch.setattr(fleet_io, "hc", world.fh)  # send talks to the same fake herdr as spawn
    w = types.SimpleNamespace(**vars(world), lines=[], evict={}, tasks_plan=make_plan(world.proj, [{"id": t, "owns": f"src/{t.lower()}.py"} for t in ("T1", "T2", "T3", "T4", "T5")], name="plan2.md"))
    if not REAL:
        monkeypatch.setattr(dispatch, "run", lambda *a, **k: (list(w.lines), dict(w.evict)))
    return w


def _sent(w):
    """[(worker agent name, task message)] of every send, told apart from the prime prompt by the task heading."""
    return [(c[1], c[2]) for c in w.fh.calls if c[0] == "prompt" and c[2].startswith("# Task")]


def _go(w):
    return fleet.main(["spawn", "--for-dispatch", "--plan", str(w.tasks_plan)])


@pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")
def test_for_dispatch_spawns_per_line(dwld, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); fleet.spawn(dwld.sd, dwld.plan, "sonnet", dwld.proj); capsys.readouterr()  # W1 is already there
    dwld.lines = [("T2,T4", FRESH), ("T3", FRESH), ("T5", "agent=W1 tier=sonnet")]
    assert _go(dwld) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["W2 T2,T4 sent", "W3 T3 sent", "W1 T5 sent"]
    sent = _sent(dwld)
    assert [(n, m.splitlines()[0]) for n, m in sent] == [(fleet.fs.agent_name(dwld.sd, "W2"), "# Tasks T2, T4"), (fleet.fs.agent_name(dwld.sd, "W3"), "# Task T3"), (fleet.fs.agent_name(dwld.sd, "W1"), "# Task T5")]
    workers = json.loads((dwld.sd / "fleet.json").read_text())["workers"]
    assert {k: (v["state"], v["task"]) for k, v in workers.items()} == {"W1": ("busy", "T5"), "W2": ("busy", "T2,T4"), "W3": ("busy", "T3")}
    assert [c[0] for c in dwld.fh.calls].count("start_agent") == 3  # W1 before the call, two fresh workers inside it


@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_blocked_spawn_continues(dwld, capsys):
    fleet.main(["on"]); dwld.fh.start_error = "agent_not_ready"; dwld.fh.screen = "Select login method\n"
    orig, starts = dwld.fh.start_agent, []
    def start(*a, **k):
        starts.append(a)
        if len(starts) == 2: dwld.fh.screen = "READY\n"  # only the first start sees the login screen
        return orig(*a, **k)
    dwld.fh.start_agent = start
    dwld.lines = [("T2,T4", FRESH), ("T3", FRESH)]
    assert _go(dwld) == 3
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("BLOCKED: T2,T4 not sent (") and "Select login method" in out[0] and out[0].endswith(")")
    assert out[1:] == ["W2 T3 sent"]
    assert [n for n, _ in _sent(dwld)] == [fleet.fs.agent_name(dwld.sd, "W2")]


WAVE0 = "wave0 tier=haiku agent=superlite:implementer-haiku"


@pytest.fixture
def brief_calls(monkeypatch):
    """T5's `fleet_io.send_brief`, faked (it may not exist yet): records its calls, prints the line T5 prints, returns the label."""
    calls = []
    def send_brief(sd, wid, brief, label=""):
        calls.append((sd, wid, brief, label)); print(f"{wid} {label} sent"); return label
    monkeypatch.setattr(fleet_io, "send_brief", send_brief, raising=False)
    return calls


@pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")
def test_wave0_line_spawns_haiku_and_sends_brief(dwld, capsys, brief_calls):
    fleet.main(["on"])
    sd = dwld.sd.resolve(); (sd / "briefs").mkdir(); (sd / "briefs" / "wave0.md").write_text("wave 0 brief\n")
    dwld.lines = [("T0", WAVE0), ("T1", FRESH)]
    assert _go(dwld) == 0
    assert capsys.readouterr().out.splitlines() == ["W1 T0 sent", "W2 T1 sent"]
    assert brief_calls == [(sd, "W1", str(sd / "briefs" / "wave0.md"), "T0")]
    starts = [c for c in dwld.fh.calls if c[0] == "start_agent"]
    assert len(starts) == 2 and "haiku" in starts[0][2] and "superlite:implementer-haiku" in starts[0][2]
    assert any(c[0] == "prompt" and "prime-haiku.md" in c[2] for c in dwld.fh.calls)


@pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")
def test_wave0_line_without_brief_is_blocked_and_the_rest_goes_on(dwld, capsys, brief_calls):
    fleet.main(["on"])
    dwld.lines = [("T0", WAVE0), ("T1", FRESH)]
    assert _go(dwld) == 3
    assert capsys.readouterr().out.splitlines() == ["BLOCKED: T0 not sent (no .superlite/briefs/wave0.md; run wave0 --plan PLAN)", "W1 T1 sent"]
    assert brief_calls == [] and [c[0] for c in dwld.fh.calls].count("start_agent") == 1  # no worker for a brief that is not there


@pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")
@pytest.mark.parametrize("line, why", [(("T5", "agent=W9 tier=sonnet"), "unknown worker W9"), (("T5", "poll W1,W2 tier=sonnet"), "no fleet decision: poll W1,W2 tier=sonnet")])
def test_unsendable_line_is_blocked_not_dropped(dwld, capsys, line, why):
    fleet.main(["on"]); dwld.lines = [line, ("T3", FRESH)]
    assert _go(dwld) == 3
    assert capsys.readouterr().out.splitlines() == [f"BLOCKED: T5 not sent ({why})", "W1 T3 sent"]


@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_failed_send_is_blocked_and_the_rest_goes_on(dwld, capsys):
    fleet.main(["on"]); dwld.lines = [("T2", FRESH), ("T3", FRESH)]
    orig = dwld.fh.prompt
    def prompt(name, text, until, ms):
        if text.startswith("# Task T2"): raise dwld.fh.HerdrError("agent_prompt_stalled", "stalled")
        return orig(name, text, until, ms)
    dwld.fh.prompt = prompt
    assert _go(dwld) == 3
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("BLOCKED: T2 not sent (") and "stalled" in out[0] and out[1:] == ["W2 T3 sent"]


@pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")
def test_evictions_go_to_stderr(dwld, capsys):
    fleet.main(["on"]); dwld.lines = [("T1", FRESH)]; dwld.evict = {"A": "no task fits"}
    assert _go(dwld) == 0
    cap = capsys.readouterr()
    assert "evict=A no task fits" in cap.err and "evict" not in cap.out


def test_real_dispatch_run_feeds_for_dispatch(world, monkeypatch, capsys):
    """No scripted lines: the real dispatch.run decides, one ready task starts one worker. Runs in both modes."""
    if not REAL:
        monkeypatch.setattr(fleet_io, "hc", world.fh)
    fleet.main(["on"])
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(world.plan)]) == 0
    assert capsys.readouterr().out.splitlines() == ["W1 T1 sent"]
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["task"] == "T1"


def test_fleet_md_names_for_dispatch():
    text = (SCRIPTS.parent / "fleet.md").read_text(encoding="utf-8")
    assert "fleet spawn --for-dispatch" in text and "one call per dispatch round" in text
