# tests/scripts/test_fleet_resume_808.py: sl fleet resume continues a stopped one-turn worker in its own session (#808)
import json
import pytest
from test_fleet_io import world, io  # noqa: F401
import fleet_report
import fleet_resume


class HE(Exception):
    def __init__(self, code="", message=""):
        super().__init__(message or code)
        self.code, self.message = code, message


class Fake:
    HerdrError = HE

    def __init__(self):
        self.calls, self.start_error, self.screen = [], None, "READY\n"

    def create_tab(self, ws, cwd, env):
        self.calls.append(("create_tab", ws))
        return ("t1", "w7:p1")

    def split_pane(self, pane, direction, cwd, env):
        self.calls.append(("split_pane", pane))
        return "w7:p2"

    def create_workspace(self, label, cwd, env):
        self.calls.append(("create_workspace", label))
        return ("w9", "w9:p1")

    def start_agent(self, name, pane, argv, timeout_ms=90000):
        self.calls.append(("start_agent", name, pane, argv))
        if self.start_error:
            raise self.start_error
        return "idle"

    def read_screen(self, name, lines=40, source="visible"):
        return self.screen

    def prompt(self, name, text, until, timeout_ms):
        self.calls.append(("prompt", name, text))
        return "working"

    def call(self, args, timeout_ms=30000, env=None):
        return {}

    def close_pane(self, pane):
        self.calls.append(("close_pane", pane))

    def send_keys(self, name, keys):
        self.calls.append(("send_keys", name, keys))

    def wait_state(self, name, until, timeout_ms):
        return "idle"

    def agent_state(self, name):
        return "idle"

    def of(self, kind):
        return [c for c in self.calls if c[0] == kind]


@pytest.fixture
def fake(world, monkeypatch):
    f = Fake()
    monkeypatch.setattr(io, "hc", f)
    return f


def patch(world, wid="W1", **kw):
    p = world.sd / "fleet.json"
    d = json.loads(p.read_text())
    d["workers"][wid].update(kw)
    for k, v in list(d["workers"][wid].items()):
        if v is None and k in kw:
            del d["workers"][wid][k]
    p.write_text(json.dumps(d))


@pytest.fixture
def stopped(world, fake):
    patch(world, role="package-reviewer", one_turn=True, state="stopped", last_task="rev-T3", session="sess-1234abcd", account="claude1",
          launch={"argv": ["--agent", "superlite:package-reviewer", "--model", "sonnet"], "env": {"K": "v"}, "cwd": str(world.proj)})
    return world


def rec(world, wid="W1"):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def test_resume_relaunches_and_sends_text(stopped, fake, capsys):
    assert fleet_resume.main(["W1", "--text", "run the simulator check", "--plan", str(stopped.sd)]) == 0
    starts = fake.of("start_agent")
    assert len(starts) == 1 and starts[0][2] == "w7:p1"
    assert starts[0][3] == ["--agent", "superlite:package-reviewer", "--model", "sonnet", "--resume", "sess-1234abcd"]
    prompts = fake.of("prompt")
    assert len(prompts) == 1 and prompts[0][2].startswith("run the simulator check")
    assert prompts[0][2].endswith(fleet_report.WORK + " " + fleet_report.NOT_RUN)
    w = rec(stopped)
    assert w["state"] == "busy" and w["task"] == "rev-T3" and w["pane_id"] == "w7:p1" and w["one_turn"] is True
    out = capsys.readouterr().out
    assert "W1 resumed pane=w7:p1 session=sess-123 (package-reviewer, last task rev-T3)\n" in out and "W1 text sent" in out


def test_resume_takes_the_session_from_the_stop_record(stopped, fake):
    patch(stopped, session=None)
    (stopped.sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": 5, "agent_id": "W1", "transcript": "/t/abc-123.jsonl"}) + "\n")
    assert fleet_resume.main(["W1", "--text", "go", "--plan", str(stopped.sd)]) == 0
    assert fake.of("start_agent")[0][3][-2:] == ["--resume", "abc-123"]


def hint(world):
    return "sl fleet spawn"


@pytest.mark.parametrize("case,want", [
    ("empty", "error: resume needs a non-empty --text"),
    ("unknown", "error: unknown worker W9"),
    ("ready", 'error: W1 is ready, not stopped; answer it with: sl fleet send W1 --text "..." --plan {sd}'),
    ("noturn", "error: W1 (implementer) is no one-turn worker; start a fresh one: sl fleet spawn"),
    ("machine", "error: W1 ran on mx; resume continues local workers only; start a fresh one: sl fleet spawn"),
    ("nolaunch", "error: W1 has no launch record; start a fresh one: sl fleet spawn"),
])
def test_resume_refusals(stopped, fake, capsys, case, want):
    wid, text = "W1", "go"
    if case == "empty":
        text = "  "
    elif case == "unknown":
        wid = "W9"
    elif case == "ready":
        patch(stopped, state="ready")
    elif case == "noturn":
        patch(stopped, one_turn=False, role="implementer")
    elif case == "machine":
        patch(stopped, machine="mx")
    elif case == "nolaunch":
        patch(stopped, launch=None)
    assert fleet_resume.main([wid, "--text", text, "--plan", str(stopped.sd)]) == 2
    err = capsys.readouterr().err.strip()
    assert err.startswith(want.format(sd=stopped.sd)) or err.startswith(want.format(sd=io.state.resolve(str(stopped.sd))))
    assert not fake.of("start_agent") and not fake.of("prompt")


def test_resume_without_session_is_blocked(stopped, fake, capsys):
    patch(stopped, session=None)
    assert fleet_resume.main(["W1", "--text", "go", "--plan", str(stopped.sd)]) == 3
    assert capsys.readouterr().out.startswith("BLOCKED: W1 not resumed (no session id); start a fresh one: sl fleet spawn --role package-reviewer")
    assert rec(stopped)["state"] == "stopped" and not fake.of("start_agent")


def test_resume_startup_failure_closes_pane(stopped, fake, capsys):
    fake.start_error = HE("boom", "no shell")
    assert fleet_resume.main(["W1", "--text", "go", "--plan", str(stopped.sd)]) == 3
    assert capsys.readouterr().out.startswith("BLOCKED: W1 not resumed (startup: no shell)")
    assert ("close_pane", "w7:p1") in fake.calls and rec(stopped)["state"] == "stopped"


def test_resume_signed_out(stopped, fake, capsys):
    fake.start_error = HE("boom", "x")
    fake.screen = "Select login method:\n"
    assert fleet_resume.main(["W1", "--text", "go", "--plan", str(stopped.sd)]) == 3
    assert capsys.readouterr().out.startswith("BLOCKED: W1 not resumed (account claude1 signed out: Claude Code sign-in screen); start a fresh one:")
    assert ("close_pane", "w7:p1") in fake.calls and "claude1" in json.loads((stopped.sd / "fleet.json").read_text())["signed_out"]
    assert rec(stopped)["state"] == "stopped" and not fake.of("prompt")


def test_send_refusal_names_resume(stopped, fake, capsys):
    sd = io.state.resolve(str(stopped.sd))
    assert io.main(["send", "W1", "--text", "hi", "--plan", str(stopped.sd)]) == 2
    assert capsys.readouterr().err.strip() == (
        f'error: W1 is stopped (package-reviewer, last task rev-T3); continue its session: sl fleet resume W1 --text "..." --plan {sd}; '
        f"or start a fresh one: sl fleet spawn --role package-reviewer --plan {sd}")
    patch(stopped, machine="mx")
    assert io.main(["send", "W1", "--text", "hi", "--plan", str(stopped.sd)]) == 2
    assert capsys.readouterr().err.startswith("error: W1 is stopped (package-reviewer, last task rev-T3); start a fresh one: ")
