"""One coordinator, several plans (#178): a session bound to run A's folder still works on run B from B's worktree.
`state.resolve()` names the linked worktree's own `.superlite` when it holds a run marker, and `dispatch --plan B`
takes its pool and ledger defaults from B after the arguments are parsed, not from the session's binding."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import SCRIPTS  # noqa: E402
from _fixtures import FIXTURES  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

SID = "resolve-per-plan-1"
PLAN = FIXTURES / "run_plan" / "plan.md"


def tool(name, *args, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), *map(str, args)], capture_output=True,
                          text=True, cwd=cwd, encoding="utf-8", timeout=60)


def offered(out):
    """Task ids on the dispatch lines of stdout."""
    return {t for ln in out.splitlines() if ln.startswith("T") for t in ln.split()[0].split(",")}


def two_runs(tmp_path, monkeypatch):
    """Linked worktrees A and B (`.git` is a file), the session bound to A; -> (a, b, launch, plan_b)."""
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    trees = {}
    for name in ("wa", "wb"):
        w = main / ".claude" / "worktrees" / name
        (w / "docs" / "plans").mkdir(parents=True)
        (w / ".git").write_text(f"gitdir: {main}/.git/worktrees/{name}\n", encoding="utf-8")
        (w / ".superlite").mkdir()
        trees[name] = w
    a, b = trees["wa"], trees["wb"]
    plan_b = b / "docs" / "plans" / "plan.md"
    shutil.copy(PLAN, plan_b)
    launch = tmp_path / "launch"
    launch.mkdir()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    state.bind(a / ".superlite")
    return a, b, launch, plan_b


def write_pool(sd, plan, agents=()):
    (sd / "pool.json").write_text(json.dumps({"plan": str(plan), "agents": list(agents)}), encoding="utf-8")


def test_two_plans_one_session(tmp_path, monkeypatch):
    a, b, launch, plan_b = two_runs(tmp_path, monkeypatch)
    write_pool(a / ".superlite", plan_b)  # A: nobody on any task, nothing committed
    write_pool(b / ".superlite", plan_b, [{"id": "a1", "tier": "sonnet", "current": "T1", "busy": True}])  # B: T1 is running
    (b / ".superlite" / "progress.md").write_text("- commit T2 abc1234567 lexer\n", encoding="utf-8")
    monkeypatch.chdir(b)
    assert state._abs(state.resolve()) == state._abs(b / ".superlite")  # the cwd's run wins over the binding
    sub = b / "docs" / "plans"
    monkeypatch.chdir(sub)
    assert state._abs(state.resolve()) == state._abs(b / ".superlite")  # from any folder below the worktree
    own = tool("dispatch", cwd=launch)  # no --plan, launched elsewhere: the binding's run (A)
    assert own.returncode == 0, own.stderr
    assert {"T1", "T2"} <= offered(own.stdout)
    r = tool("dispatch", "--plan", plan_b, cwd=launch)  # B's pool and ledger, the binding still points at A
    assert r.returncode == 0, r.stderr
    assert not offered(r.stdout) & {"T1", "T2"}, r.stdout
    assert "T5" in offered(r.stdout)
    from_b = tool("dispatch", "--plan", plan_b, cwd=sub)  # and the same from inside B
    assert offered(from_b.stdout) == offered(r.stdout)


def test_marker_needed_and_any_marker_counts(tmp_path, monkeypatch):
    a, b, launch, plan_b = two_runs(tmp_path, monkeypatch)
    monkeypatch.chdir(b)
    assert state._abs(state.resolve()) == state._abs(a / ".superlite")  # B holds no run yet: the binding stays
    for marker in ("stable.json", "prime.md", "pool.json"):
        f = b / ".superlite" / marker
        f.write_text("{}\n", encoding="utf-8")
        assert state._abs(state.resolve()) == state._abs(b / ".superlite"), marker
        f.unlink()
    assert state._abs(state.resolve()) == state._abs(a / ".superlite")


def test_order_unchanged_elsewhere(tmp_path, monkeypatch):
    a, b, launch, plan_b = two_runs(tmp_path, monkeypatch)
    (launch / ".superlite").mkdir()
    monkeypatch.chdir(launch)  # no linked worktree here: the binding beats ./.superlite
    assert state._abs(state.resolve()) == state._abs(a / ".superlite")
    main = tmp_path / "main"
    monkeypatch.chdir(main)  # a main checkout (`.git` is a folder) is not a linked worktree
    (main / ".superlite").mkdir()
    (main / ".superlite" / "pool.json").write_text("{}\n", encoding="utf-8")
    assert state._abs(state.resolve()) == state._abs(a / ".superlite")
    (b / ".superlite" / "pool.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(b)
    forced = tmp_path / "forced" / ".superlite"
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(forced))  # the override beats the binding and the cwd's run
    assert state._abs(state.resolve()) == state._abs(forced)
    monkeypatch.chdir(launch)
    assert state._abs(state.resolve()) == state._abs(forced)


def test_dispatch_defaults_after_parse(tmp_path, monkeypatch):
    a, b, launch, plan_b = two_runs(tmp_path, monkeypatch)
    write_pool(a / ".superlite", plan_b)
    write_pool(b / ".superlite", plan_b, [{"id": "a1", "tier": "sonnet", "current": "T1", "busy": True}])
    r = tool("dispatch", "--plan", plan_b, cwd=launch)
    assert r.returncode == 0, r.stderr
    assert "T1" not in offered(r.stdout), r.stdout  # B's pool.json was read
    explicit = tool("dispatch", "--plan", plan_b, "--pool", a / ".superlite" / "pool.json", cwd=launch)
    assert explicit.returncode == 0, explicit.stderr
    assert "T1" in offered(explicit.stdout)  # an explicit --pool still wins
    ledger = tool("dispatch", "--plan", plan_b, "--ledger", a / ".superlite" / "progress.md", cwd=launch)
    assert "T1" not in offered(ledger.stdout)  # the pool default (B) is independent of the ledger flag


def test_where_names_the_worktree_run(tmp_path, monkeypatch):
    a, b, launch, plan_b = two_runs(tmp_path, monkeypatch)
    write_pool(b / ".superlite", plan_b)
    r = tool("state", "where", cwd=b)
    assert r.returncode == 0, r.stderr
    assert str(b / ".superlite") in r.stdout and "worktree" in r.stdout, r.stdout
