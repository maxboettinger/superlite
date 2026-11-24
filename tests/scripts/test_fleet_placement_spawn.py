# tests/scripts/test_fleet_placement_spawn.py
import json, sys, types
import pytest
from test_fleet import FakeHerdr, world  # noqa: F401 (world is the fixture)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io as fio  # noqa: E402
import fleet_placement as fp  # noqa: E402
import fleet_remote_worker as frw  # noqa: E402


@pytest.fixture
def pl(world, tmp_path, monkeypatch, capsys):
    """Placement on (machine.json names remote_room and remote_tree); choose answers `r.pick`; remote spawn and sends are recorded."""
    home = tmp_path / "home"; home.mkdir()
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    (home / "machine.json").write_text(json.dumps({"remote_room": ["x"], "remote_tree": ["y"]}))
    fleet.main(["on"]); capsys.readouterr()
    brief = world.proj / "b.md"; brief.write_text("do it")
    r = types.SimpleNamespace(**vars(world), brief=brief, pick="box", asked=[], briefs=[], skips=[], remote=[], sends=[], local=[], sent_briefs=[], fail=None, n=[0])

    def choose(sd, role, project, now=None, brief=None):
        r.asked.append(role); r.briefs.append(brief); return r.pick
    monkeypatch.setattr(fp, "choose", choose)
    monkeypatch.setattr(fp, "skip", lambda sd, label, why, minutes=10.0, now=None: r.skips.append((label, why)))

    def rspawn(sd, role, tier, project, label, cfg=None, task=None, plan=None, brief=None):
        if r.fail:
            print(f"BLOCKED: fleet spawn: machine {label}: {r.fail}"); raise SystemExit(3)
        r.n[0] += 1; wid = f"W{r.n[0]}"; r.remote.append((role, tier, label, task, brief))
        d = fleet.fs.load(sd); d["workers"][wid] = {"state": "ready", "role": role, "machine": label}; fleet.fs.save(sd, d)
        return {"id": wid}
    monkeypatch.setattr(frw, "spawn", rspawn)
    monkeypatch.setattr(frw, "send_task", lambda sd, wid, plan, tasks, sl: r.sends.append((wid, list(tasks))))
    monkeypatch.setattr(fio, "send_brief", lambda sd, wid, b, label="", **k: r.sent_briefs.append(wid) or label)
    real = fleet.spawn

    def spawn(sd, plan, tier, project, *a, **k):
        if k.get("machine"):
            return real(sd, plan, tier, project, *a, **k)
        r.n[0] += 1; wid = f"W{r.n[0]}"; r.local.append((tier, k.get("role", "implementer")))
        d = fleet.fs.load(sd); d["workers"][wid] = {"state": "ready", "role": "implementer"}; fleet.fs.save(sd, d)
        print(f"{wid} local")
        return {"id": wid}
    monkeypatch.setattr(fleet, "spawn", spawn)
    return r


def test_placed_remote_spawn(pl, capsys):
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert pl.asked == ["research"] and pl.remote == [("research", None, "box", None, str(pl.brief))] and pl.local == []
    assert pl.sent_briefs == ["W1"]


def test_remote_failure_spawns_local_without_blocked_line(pl, capsys):
    pl.fail = "unreachable: ssh refused"
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    out = capsys.readouterr().out
    assert "placement: box unavailable (unreachable: ssh refused); local" in out
    assert "BLOCKED" not in out and "W1 local" in out
    assert [s[0] for s in pl.skips] == ["box"] and "unreachable" in pl.skips[0][1] and len(pl.local) == 1


def test_remote_other_exit_keeps_its_output(pl, capsys, monkeypatch):
    def boom(*a, **k):
        print("BLOCKED: fleet spawn: something else"); raise SystemExit(2)
    monkeypatch.setattr(frw, "spawn", boom)
    with pytest.raises(SystemExit) as ei:
        fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)])
    assert ei.value.code == 2 and "something else" in capsys.readouterr().out and pl.local == [] and pl.skips == []


def test_machine_local_forces_local(pl, capsys):
    assert fleet.main(["spawn", "--machine", "local", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert pl.asked == [] and pl.remote == [] and len(pl.local) == 1


def test_placement_off_unchanged(pl, tmp_path, monkeypatch, capsys):
    (tmp_path / "home" / "machine.json").write_text("{}")
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert pl.asked == [] and pl.remote == [] and capsys.readouterr().out.strip() == "W1 local"


def test_local_pick_is_local(pl, capsys):
    pl.pick = None
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert pl.asked == ["research"] and pl.remote == [] and len(pl.local) == 1


@pytest.fixture
def disp(pl, monkeypatch):
    import dispatch
    from test_plan_tools import make_plan
    plan = make_plan(pl.proj, [{"id": t, "owns": f"src/{t.lower()}.py"} for t in ("T3", "T4", "T5")], name="plan2.md")
    pl.plan2, pl.lines, pl.fsends = plan, [], []
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: (list(pl.lines), {}))
    monkeypatch.setattr(fio, "send", lambda sd, plan, wid, tasks, sl, root: pl.fsends.append((wid, list(tasks))))
    monkeypatch.setattr(fio, "hint_lines", lambda *a, **k: [])
    d = fleet.fs.load(pl.sd); d["workers"]["W2"] = {"state": "ready", "role": "implementer"}; fleet.fs.save(pl.sd, d)
    pl.n[0] = 2
    return pl


def test_for_dispatch_mixed_lines(disp, capsys):
    disp.lines = [("T3", "fresh tier=sonnet agent=superlite:implementer"), ("T4", "agent=W2 tier=sonnet"),
                  ("T5", "poll W1,W2 tier=sonnet"), ("T0", "wave0 tier=haiku"), ("T6", "fresh tier=haiku")]
    fleet.main(["spawn", "--for-dispatch", "--plan", str(disp.plan2)])
    out = capsys.readouterr().out
    assert [(x[0], x[2], x[3]) for x in disp.remote] == [("implementer", "box", "T3"), ("implementer", "box", "T5")]
    assert disp.sends == [("W3", ["T3"]), ("W4", ["T5"])]
    assert disp.fsends == [("W2", ["T4"]), ("W5", ["T6"])]  # T4 reused as today, the haiku line local
    assert "W3 T3 sent machine=box" in out and "W4 T5 sent machine=box" in out
    assert disp.local == [("haiku", "implementer")]  # the haiku fresh line; wave0 has no brief file and spawns nothing
    assert disp.asked == ["implementer", "implementer"]


def test_for_dispatch_remote_failure_goes_local(disp, capsys):
    disp.fail = "unreachable: ssh refused"
    disp.lines = [("T3", "fresh tier=sonnet agent=superlite:implementer")]
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(disp.plan2)]) == 0
    out = capsys.readouterr().out
    assert "placement: box unavailable (unreachable: ssh refused); local" in out and "BLOCKED" not in out
    assert disp.local == [("sonnet", "implementer")] and disp.fsends == [("W3", ["T3"])] and [s[0] for s in disp.skips] == ["box"]


def test_placement_command(world, tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"; home.mkdir(); monkeypatch.setenv("SUPERLITE_HOME", str(home))
    (home / "machine.json").write_text(json.dumps({"remote_room": ["x"], "remote_tree": ["y"]}))
    monkeypatch.setattr(fp, "room", lambda sd, **k: {"local": {"state": "ready", "room": 12}, "box": {"state": "ready", "room": 10}})
    fleet.main(["on"]); capsys.readouterr()
    assert fleet.main(["placement", "local"]) == 0 and capsys.readouterr().out.strip() == "placement: local"
    assert fp.enabled(world.sd) is False
    assert fleet.main(["placement", "spread"]) == 0 and capsys.readouterr().out.strip() == "placement: spread"
    assert fleet.main(["placement"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "placement: spread" and "local: ready room 12" in out and "box: ready room 10" in out


def test_placed_value_error_is_not_a_remote_failure(pl, capsys, monkeypatch):
    def bad(*a, **k):
        raise ValueError("unknown role: zzz")
    monkeypatch.setattr(frw, "spawn", bad)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 2
    cap = capsys.readouterr()
    assert "unknown role" in cap.err and "unavailable" not in cap.out and pl.skips == [] and pl.local == []


def _fail_send(pl, monkeypatch, fail_ids):
    """send_brief raises a Herdr timeout for the worker ids in `fail_ids` ("*" = every worker); stop is recorded and prints a line."""
    stopped = []
    monkeypatch.setattr(fleet, "stop", lambda sd, ids=None, **k: stopped.extend(ids or []) or print("stopped " + ",".join(ids or [])))

    def send(sd, wid, b, label="", **k):
        if "*" in fail_ids or wid in fail_ids:
            raise fleet.hc.HerdrError("timeout", "timed out waiting for agent status")
        pl.sent_briefs.append(wid)
    monkeypatch.setattr(fio, "send_brief", send)
    return stopped


def test_placed_send_failure_spawns_local(pl, capsys, monkeypatch):
    stopped = _fail_send(pl, monkeypatch, {"W1"})
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    out = capsys.readouterr().out
    assert "placement: box unavailable (W1 not sent: timed out waiting for agent status); local" in out
    assert "BLOCKED" not in out and "stopped" not in out and "W2 local" in out
    assert stopped == ["W1"] and pl.sent_briefs == ["W2"] and len(pl.local) == 1
    assert [s[0] for s in pl.skips] == ["box"] and "not sent" in pl.skips[0][1]


def test_placed_then_local_send_failure_blocks_once(pl, capsys, monkeypatch):
    stopped = _fail_send(pl, monkeypatch, {"*"})
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 3
    out = capsys.readouterr().out
    assert "placement: box unavailable" in out and out.count("BLOCKED") == 1 and "BLOCKED: W2 b not sent (timed out waiting for agent status)" in out
    assert stopped == ["W1", "W2"] and len(pl.local) == 1 and len(pl.skips) == 1


def test_forced_machine_send_failure_still_blocks(pl, capsys, monkeypatch):
    stopped = _fail_send(pl, monkeypatch, {"*"})
    assert fleet.main(["spawn", "--machine", "box", "--role", "research", "--brief", str(pl.brief)]) == 3
    out = capsys.readouterr().out
    assert "BLOCKED: W1 b not sent (timed out waiting for agent status)" in out and "placement:" not in out
    assert stopped == ["W1"] and pl.local == [] and pl.skips == []


def test_for_dispatch_send_failure_goes_local(disp, capsys, monkeypatch):
    stops = []
    monkeypatch.setattr(fleet, "stop", lambda sd, ids=None, **k: (stops.append(list(ids or [])), print(f"stopped {list(ids or [])}"), list(ids or []))[-1])

    def bad(sd, wid, plan, tasks, sl):
        raise fio.hc.HerdrError("account_signed_out", "the account is signed out on this machine; run /login for it there")
    monkeypatch.setattr(frw, "send_task", bad)
    disp.lines = [("T3", "fresh tier=sonnet agent=superlite:implementer")]
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(disp.plan2)]) == 0
    out = capsys.readouterr().out
    assert "placement: box unavailable (W3 not sent: the account is signed out on this machine; run /login for it there); local" in out
    assert "BLOCKED" not in out and "stopped ['W3']" not in out
    assert disp.local == [("sonnet", "implementer")] and disp.fsends == [("W4", ["T3"])]
    assert ["W3"] in stops and [x[0] for x in disp.skips] == ["box"]


def test_placed_send_failure_survives_failing_stop(pl, capsys, monkeypatch):
    _fail_send(pl, monkeypatch, {"W1"})

    def boom(sd, ids=None, **k):
        raise OSError("host unreachable")
    monkeypatch.setattr(fleet, "stop", boom)
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    out = capsys.readouterr().out
    assert "placement: box unavailable" in out and "W2 local" in out and pl.sent_briefs == ["W2"]


def test_plain_spawn_hands_placement_the_brief(pl):
    assert fleet.main(["spawn", "--role", "research", "--brief", str(pl.brief)]) == 0
    assert pl.asked == ["research"] and pl.briefs == [str(pl.brief)]


def test_placed_passes_brief_to_choose(pl, monkeypatch):
    seen = []
    monkeypatch.setattr(fp, "choose", lambda sd, role, project, now=None, brief=None: seen.append((role, brief)) or "box")
    assert fleet._placed(pl.sd, "research", pl.proj, brief="/b/R1.md") == "box"
    assert fleet._placed(pl.sd, "implementer", pl.proj) == "box"
    assert seen == [("research", "/b/R1.md"), ("implementer", None)]


def test_placed_haiku_skips_choose_with_brief(pl, monkeypatch):
    monkeypatch.setattr(fp, "choose", lambda *a, **k: pytest.fail("choose called"))
    assert fleet._placed(pl.sd, "implementer", pl.proj, "haiku", brief="/b/x.md") is None
