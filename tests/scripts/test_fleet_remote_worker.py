# tests/scripts/test_fleet_remote_worker.py
import contextlib, json, os, subprocess, sys
from pathlib import Path
import pytest
from _fixtures import FIXTURES
from test_fleet import FakeHerdr
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io as fio  # noqa: E402
import fleet_remote as fr  # noqa: E402
import fleet_remote_account as fra  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402
import fleet_state as fs  # noqa: E402
import trees  # noqa: E402

TREE = str(FIXTURES / "fleet" / "remote-tree")


class Routed(FakeHerdr):
    """Records ("on", m) / ("off", m) around the calls made inside `on(m)`."""
    def __init__(self):
        super().__init__(); self.agent_map, self.list_error = {}, False
    @contextlib.contextmanager
    def on(self, m):
        self.calls.append(("on", m))
        try: yield
        finally: self.calls.append(("off", m))
    def agent_states(self):
        self.calls.append(("agent_states",))
        if self.list_error: raise self.HerdrError("timeout", "x")
        return dict(self.agent_map)
    def inside(self):
        """The calls made inside an on-block, and whether any call stood outside one."""
        depth, inside, outside = 0, [], []
        for c in self.calls:
            if c[0] == "on": depth += 1
            elif c[0] == "off": depth -= 1
            else: (inside if depth else outside).append(c)
        return inside, outside


@pytest.fixture
def world(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir(); th = tmp_path / "rh" / ".maxapp" / "trees"; th.mkdir(parents=True)
    proj = tmp_path / "proj"; sd = proj / ".superlite"; (sd / "briefs").mkdir(parents=True)
    monkeypatch.setenv("SUPERLITE_HOME", str(home)); monkeypatch.setenv("FAKE_TREE_HOME", str(th / "proj")); monkeypatch.setenv("FAKE_TREE_LOG", str(tmp_path / "log"))
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    (home / "machine.json").write_text(json.dumps({"remote_tree": [TREE]}))
    fh = Routed()
    for m in (fleet, rw, fio): monkeypatch.setattr(m, "hc", fh)
    panes = []
    def open_pane(sd_, wid, cwd, env, record, machine=None):
        panes.append({"wid": wid, "cwd": cwd, "env": env, "machine": machine, "outside": [c for c in fh.calls]})
        with fs.locked(sd_):
            d = fs.load(sd_); d["workers"][wid] = {**record, "pane_id": "w6:p1"}; fs.save(sd_, d)
        return "w6:p1"
    monkeypatch.setattr(fleet, "open_pane", open_pane)
    monkeypatch.setattr(fr, "check", lambda label: "unreachable: ssh: refused" if label == "down" else "")
    genv = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    def git(*a): return subprocess.run(["git", "-C", str(proj), *a], capture_output=True, text=True, check=True, env=genv).stdout.strip()
    git("init", "-q"); (proj / "kept.txt").write_text("old\n"); (proj / "gone.txt").write_text("x\n")
    git("add", "kept.txt", "gone.txt"); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    monkeypatch.setattr(trees, "base_commit", lambda root: base)
    root = tmp_path / "superlite-root"; root.mkdir()  # no .git: the lookup must not depend on the real checkout
    monkeypatch.setattr(rw, "SUPERLITE_ROOT", str(root))
    monkeypatch.setattr(fr, "plugin", lambda label, r, timeout_s=120: fr.push(label, r, "plugin/abc123", "abc123", [], timeout_s))
    monkeypatch.setattr(rw.routing, "load_cfg", lambda *a, **k: dict(rw.routing.FALLBACK))
    picks = []
    def pick(sd_, label, model, env, remote_home, local_home=None):
        picks.append({"label": label, "model": model, "remote_home": remote_home})
        return ("claude2@box", "/rh/.cfg2") if world_cfg.get("cdir") else ("claude1@box", None)
    world_cfg = {}
    monkeypatch.setattr(fra, "pick", pick)
    monkeypatch.setattr(rw, "_took", lambda *a, **k: True)
    monkeypatch.chdir(proj)
    return type("W", (), {"git": staticmethod(git), "proj": proj, "sd": sd, "fh": fh, "panes": panes, "trees": th / "proj", "tmp": tmp_path, "picks": picks, "cfg": world_cfg, "base": base})


def started(world):
    return rw.spawn(world.sd, "research", None, world.proj, "box")


def record(world, wid="W1"):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def test_spawn_calls_routed(world, capsys):
    r = started(world)
    assert r == {"id": "W1", "account": "claude1@box", "pane_id": "w6:p1", "agent": "superlite:researcher", "model": "sonnet", "role": "research", "machine": "box"}
    assert "W1 account=claude1@box pane=w6:p1 agent=superlite:researcher role=research machine=box" in capsys.readouterr().out
    inside, outside = world.fh.inside()
    assert outside == [] and any(c[0] == "start_agent" for c in inside)
    assert world.panes[0]["machine"] == "box"
    assert record(world)["state"] == "ready" and record(world)["machine"] == "box"


def test_spawn_argv_plugin_dir(world):
    started(world)
    argv = next(c for c in world.fh.calls if c[0] == "start_agent")[2]
    plugin = world.trees / "plugin"
    assert argv[0] == "--plugin-dir" and Path(argv[1]).parent == plugin and Path(argv[1]).is_dir()
    env = world.panes[0]["env"]; tree = str(world.trees / fr.tree_name(world.sd, "W1"))
    assert env["SUPERLITE_STATE_DIR"] == tree + "/.superlite" and "CLAUDE_CONFIG_DIR" not in env
    assert world.panes[0]["cwd"] == tree and Path(tree).is_dir()
    assert record(world)["remote"]["tree"] == tree and record(world)["remote"]["offset"] == 0


def test_spawn_refusals(world, capsys):
    with pytest.raises(ValueError, match="role writer cannot run on a remote machine yet; remote roles: research, final-reviewer, implementer, fixer, package-reviewer"):
        rw.spawn(world.sd, "writer", None, world.proj, "box")
    with pytest.raises(SystemExit) as e:
        rw.spawn(world.sd, "research", None, world.proj, "down")
    assert e.value.code == 3 and "BLOCKED: fleet spawn: machine down: unreachable: ssh: refused" in capsys.readouterr().out
    assert world.panes == []


def test_send_brief(world, capsys):
    started(world)
    b = world.sd / "briefs" / "q.md"; b.write_text("question")
    assert rw.send_brief(world.sd, "W1", str(b), "Q1") == "Q1"
    prompt = next(c for c in world.fh.calls if c[0] == "prompt")
    tree = world.trees / fr.tree_name(world.sd, "W1")
    copy = tree / ".superlite/remote/W1/briefs/q.md"
    assert str(copy) in prompt[2] and str(world.proj) not in prompt[2]
    assert copy.read_text() == "question"
    assert record(world)["state"] == "busy" and record(world)["task"] == "Q1"
    assert any(c[0] == "prompt" for c in world.fh.inside()[0]) and all(c[0] != "prompt" for c in world.fh.inside()[1])
    out = world.tmp / "q.md"; out.write_text("x")
    with pytest.raises(OSError, match="must be inside .* for a remote worker"):
        rw.send_brief(world.sd, "W1", str(out), "Q2")


def test_final_reviewer_ships_packet_tests(world):
    rw.spawn(world.sd, "final-reviewer", None, world.proj, "box")
    b = world.sd / "briefs" / "review-packet.md"; b.write_text("p")
    (world.sd / "briefs" / "review-packet-tests.md").write_text("t")
    rw.send_brief(world.sd, "W1", str(b))
    tree = world.trees / fr.tree_name(world.sd, "W1") / ".superlite" / "briefs"
    copies = world.trees / fr.tree_name(world.sd, "W1") / ".superlite" / "remote" / "W1" / "briefs"
    assert (copies / "review-packet.md").is_file() and (copies / "review-packet-tests.md").read_text() == "t"
    (copies / "review-packet-tests.md").unlink(); (world.sd / "briefs" / "review-packet-tests.md").unlink()
    rw.send_brief(world.sd, "W1", str(b))
    assert not (copies / "review-packet-tests.md").exists()


def test_pushed_packet_is_mapped_to_the_remote_tree(world):
    rw.spawn(world.sd, "final-reviewer", None, world.proj, "box")
    shard = world.sd / "briefs" / "review-packet-tests.md"; shard.write_text(f"tests at {world.proj}/src/x.py")
    b = world.sd / "briefs" / "review-packet.md"; b.write_text(f"read {shard} in full; code in {world.proj}/src")
    rw.send_brief(world.sd, "W1", str(b))
    tree = world.trees / fr.tree_name(world.sd, "W1"); copies = tree / ".superlite" / "remote" / "W1" / "briefs"
    packet, tests = (copies / "review-packet.md").read_text(), (copies / "review-packet-tests.md").read_text()
    assert f"read {copies / 'review-packet-tests.md'} in full; code in {tree}/src" == packet and tests == f"tests at {tree}/src/x.py"
    assert str(world.proj) not in packet + tests and (b.read_text() == f"read {shard} in full; code in {world.proj}/src")
    assert str(copies / "review-packet.md") in next(c for c in world.fh.calls if c[0] == "prompt")[2]


def test_states_and_synced_when_busy(world, monkeypatch):
    started(world)
    world.fh.agent_map = {"sl-proj-w1": "done", "sl-other": "idle"}
    name = record(world)["name"]; world.fh.agent_map = {name: "done"}
    assert rw.states(world.sd) == {name: "done"}
    seen = []
    monkeypatch.setattr(fr, "sync", lambda sd, wid: seen.append(wid) or 0)
    assert seen == []
    d = json.loads((world.sd / "fleet.json").read_text()); d["workers"]["W1"]["state"] = "busy"; (world.sd / "fleet.json").write_text(json.dumps(d))
    rw.states(world.sd); assert seen == ["W1"]


def test_states_down_machine_not_dead(world):
    started(world)
    world.fh.list_error = True
    name = record(world)["name"]
    assert rw.states(world.sd) == {name: None}
    assert record(world)["state"] == "ready"


def test_states_skips_local_and_stopped(world):
    started(world)
    d = json.loads((world.sd / "fleet.json").read_text())
    d["workers"]["W2"] = {"name": "sl-local", "state": "busy", "pane_id": "p"}
    d["workers"]["W1"]["state"] = "stopped"; (world.sd / "fleet.json").write_text(json.dumps(d))
    assert rw.states(world.sd) == {}


def test_stop(world, capsys):
    started(world)
    rw.stop(world.sd, "W1")
    inside, outside = world.fh.inside()
    assert [c[0] for c in inside if c[0] in ("exit_agent", "close_pane")] == ["exit_agent", "close_pane"] and outside == []
    assert record(world)["state"] == "stopped" and not (world.trees / fr.tree_name(world.sd, "W1")).exists()


def test_stop_failed_drop(world, capsys, monkeypatch):
    started(world)
    def boom(*a, **k): raise fr.RemoteError("box unreachable: x")
    monkeypatch.setattr(fr, "drop", boom)
    rw.stop(world.sd, "W1")
    assert "W1 tree kept on box: box unreachable: x" in capsys.readouterr().err and record(world)["state"] == "stopped"


def test_spawn_accepts_trust_dialog_on_start(world):
    world.fh.start_error = "agent_not_ready"; world.fh.screen = "Yes, I trust this folder\n"
    r = started(world)
    assert r["id"] == "W1" and record(world)["state"] == "ready"
    assert any(c[0] == "send_keys" for c in world.fh.inside()[0]) and world.fh.inside()[1] == []


def test_spawn_drops_the_tree_when_open_pane_fails(world, capsys, monkeypatch):
    def boom(*a, **k): raise world.fh.HerdrError("create_failed", "no pane")
    monkeypatch.setattr(fleet, "open_pane", boom)
    with pytest.raises(SystemExit) as e:
        started(world)
    assert e.value.code == 3 and not (world.trees / fr.tree_name(world.sd, "W1")).exists()


def test_spawn_drops_the_tree_when_startup_fails(world, monkeypatch):
    world.fh.start_error = "agent_start_failed"
    with pytest.raises(SystemExit) as e:
        started(world)
    assert e.value.code == 3 and not (world.trees / fr.tree_name(world.sd, "W1")).exists()


def test_spawn_blocked_survives_a_failed_drop(world, monkeypatch):
    def boom(*a, **k): raise fr.RemoteError("box unreachable: x")
    monkeypatch.setattr(fr, "drop", boom); world.fh.start_error = "agent_start_failed"
    with pytest.raises(SystemExit) as e:
        started(world)
    assert e.value.code == 3


def test_remote_send_brief_prints_one_line(world, capsys):
    started(world); capsys.readouterr()
    b = world.sd / "briefs" / "q.md"; b.write_text("question")
    assert fio.send_brief(world.sd, "W1", str(b), "Q1") == "Q1"
    assert capsys.readouterr().out.splitlines() == ["W1 Q1 sent"]


def start_files(world, wid="W1"):
    ref = f"refs/superlite/remote/{fr.tree_name(world.sd, wid)}/start"
    return world.git("ls-tree", "-r", "--name-only", ref).splitlines(), ref


def show(world, ref, path):
    return world.git("show", f"{ref}:{path}")


def push_argv(world, wid="W1"):
    return next(e["argv"] for e in map(json.loads, (world.tmp / "log").read_text().splitlines()) if e["argv"][0] == "push" and fr.tree_name(world.sd, wid) in e["argv"])


def test_spawn_pushes_the_working_state(world):
    (world.proj / "kept.txt").write_text("new\n"); (world.proj / "fresh.txt").write_text("fresh\n")
    (world.proj / "gone.txt").unlink(); (world.sd / "notes.md").write_text("state\n")
    (world.proj / "sub").mkdir(); (world.proj / "sub" / "deep.txt").write_text("deep\n")
    started(world)
    names, ref = start_files(world)
    assert sorted(names) == ["fresh.txt", "kept.txt", "sub/deep.txt"]
    assert show(world, ref, "kept.txt") == "new"
    push = push_argv(world)
    assert push[push.index("--base") + 1] == world.git("rev-parse", ref) and "--file" not in push
    assert record(world)["remote"]["start"] == world.git("rev-parse", ref)


def test_spawn_git_failure_is_blocked(world, capsys, monkeypatch):
    monkeypatch.setattr(trees, "base_commit", lambda root: "deadbeef" * 5)
    with pytest.raises(SystemExit) as e:
        started(world)
    out = capsys.readouterr().out
    assert e.value.code == 3 and out.startswith("BLOCKED: fleet spawn: machine box: ") and "Traceback" not in out


def plan_for(world, owns="src/a.py"):
    (world.sd / "prime.md").write_text(f"Root: {world.proj}\nplan {world.sd}/plan.md\n")
    p = make_plan(world.proj, [{"id": "T3", "owns": owns}])
    return Path(p)


def test_start_commit_files_by_role(world):
    (world.proj / "src").mkdir(); (world.proj / "src" / "a.py").write_text("a\n"); (world.proj / "other.py").write_text("o\n")
    (world.proj / "kept.txt").write_text("edited\n")
    plan = plan_for(world)
    (world.sd / "test-cmd.json").write_text("{}"); (world.sd / "stable.json").write_text(f'{{"r": "{world.proj}"}}')
    r = rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    names, ref = start_files(world)
    assert "src/a.py" in names and "other.py" not in names and show(world, ref, "kept.txt") == "old"
    assert {".superlite/prime.md", f".superlite/{plan.name}", ".superlite/test-cmd.json", ".superlite/stable.json"} <= set(names)
    rec = record(world)["remote"]
    assert rec["write"] is True and rec["owns"] == ["src/a.py", "tests/regression/**"] and rec["snapshot_ref"] == ref.replace("/start", "/stop")
    assert record(world)["account"] == "claude2@box" or record(world)["account"] == "claude1@box"
    # fixer: every changed and untracked file, no prime, mapped brief
    b = world.sd / "briefs" / "f.md"; b.write_text(f"fix {world.proj}/x")
    rw.spawn(world.sd, "fixer", "sonnet", world.proj, "box", brief=str(b))
    names2, ref2 = start_files(world, "W2")
    assert {"src/a.py", "other.py", "kept.txt", ".superlite/briefs/f.md"} <= set(names2) and ".superlite/prime.md" not in names2
    assert record(world, "W2")["remote"]["owns"] is None and record(world, "W2")["remote"]["write"] is True
    # research: working files, read-only
    rw.spawn(world.sd, "research", None, world.proj, "box")
    names3, _ = start_files(world, "W3")
    assert "other.py" in names3 and record(world, "W3")["remote"]["write"] is False


def test_prime_paths_mapped(world):
    plan = plan_for(world)
    plan.write_text(plan.read_text() + f"\nroot {world.proj}\n")
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    names, ref = start_files(world)
    tree = str(world.trees / fr.tree_name(world.sd, "W1"))
    prime, pl = show(world, ref, ".superlite/prime.md"), show(world, ref, f".superlite/{plan.name}")
    assert str(world.proj) not in prime + pl and tree in prime and tree in pl
    assert f"{tree}/.superlite/plan.md" in prime or f"{tree}/.superlite/{plan.name}" in prime
    ask = next(c for c in world.fh.calls if c[0] == "prompt")[2]
    assert ask == f"Read {tree}/.superlite/prime.md, then reply READY"


def test_env_and_account(world):
    env = lambda: world.panes[-1]["env"]
    b = world.sd / "briefs" / "f.md"; b.write_text("fix")
    rw.spawn(world.sd, "fixer", "sonnet", world.proj, "box", brief=str(b))
    assert env()["SUPERLITE_REMOTE_SNAPSHOT"] == f"refs/superlite/remote/{fr.tree_name(world.sd, 'W1')}/stop" and "CLAUDE_CONFIG_DIR" not in env()
    assert world.picks[0]["remote_home"] == str(world.tmp / "rh")
    world.cfg["cdir"] = True
    rw.spawn(world.sd, "research", None, world.proj, "box")
    assert "SUPERLITE_REMOTE_SNAPSHOT" not in env()
    assert env()["CLAUDE_CONFIG_DIR"] == "/rh/.cfg2" and record(world, "W2")["account"] == "claude2@box"


def test_login_screen_blocked(world, capsys):
    world.fh.screen = "Select login method:\n1. Claude account"
    world.cfg["cdir"] = True
    with pytest.raises(SystemExit) as e:
        started(world)
    assert e.value.code == 3
    assert "BLOCKED: fleet spawn: machine box: account claude2 is not signed in on box" in capsys.readouterr().out
    assert any(c[0] == "close_pane" for c in world.fh.calls) and not (world.trees / fr.tree_name(world.sd, "W1")).exists()


def test_part1_research_still_works(world):
    r = started(world)
    assert r["role"] == "research" and r["machine"] == "box" and record(world)["state"] == "ready"
    assert record(world)["account"] == "claude1@box" and "default@" not in record(world)["account"]
    argv = next(c for c in world.fh.calls if c[0] == "start_agent")[2]
    assert argv[0] == "--plugin-dir"


def test_send_task_maps_paths(world):
    plan = plan_for(world)
    rw.spawn(world.sd, "implementer", "sonnet", world.proj, "box", task="T3", plan=str(plan))
    sl = str(rw.SUPERLITE_ROOT) + "/skills/subagent-driven-development/scripts/sl"
    rw.send_task(world.sd, "W1", str(plan), ["T3"], sl)
    msg = [c for c in world.fh.calls if c[0] == "prompt"][-1][2]
    tree = str(world.trees / fr.tree_name(world.sd, "W1"))
    assert str(world.proj) not in msg and tree in msg and str(rw.SUPERLITE_ROOT) not in msg
    assert record(world)["state"] == "busy" and record(world)["task"] == "T3"
    assert any(c[0] == "prompt" for c in world.fh.inside()[0]) and all(c[0] != "prompt" for c in world.fh.inside()[1])


def test_tree_path_uses_the_repository_name_of_the_project(world, capsys, monkeypatch):
    plain = world.tmp / "my app"; plain.mkdir()
    genv = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    def git(*a): return subprocess.run(["git", "-C", str(plain), *a], capture_output=True, text=True, check=True, env=genv).stdout.strip()
    git("init", "-q"); (plain / "a.txt").write_text("a\n"); git("add", "a.txt"); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    base = git("rev-parse", "HEAD"); monkeypatch.setattr(trees, "base_commit", lambda root: base)
    (plain / ".superlite").mkdir()
    with pytest.raises(SystemExit):  # the fake pushes beside the `proj` trees, so the check reports the prediction
        rw.spawn(plain / ".superlite", "research", None, plain, "box")
    assert "expected " + str(world.trees.parent / "my-app") + "/" in capsys.readouterr().out
