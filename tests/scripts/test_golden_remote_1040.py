# tests/scripts/test_golden_remote_1040.py: remote golden attempt (#1040)
import json, sys, threading
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import golden_remote as gr  # noqa: E402
import herdr_client as hc  # noqa: E402

TREE = "/h/trees/superlite/golden/small-1-abc123"
CASE = {"id": "small", "base": "abc", "test_cmd": "pytest"}
HOST_ROW = {"v": 1, "row": "golden", "case": "small", "attempt": 1, "passed": True, "why": [], "warn": [], "started": True,
            "lead_usd": 3.0, "total_usd": 3.5, "lead_turns": 60, "wall_min": 30.0, "patch": "small-1.patch", "plugin": ""}
PATCH = b"diff --git a/a b/a\n"
PLUGIN = "1.5.244+076a39a"


class Env:
    def __init__(self, monkeypatch, tmp_path):
        self.calls, self.reads, self.results = [], {}, [None, (0, "ok")]
        self.start_args = self.push_args = self.run_args = None
        self.push_error = self.drop_error = None
        self.src, self.out_dir = tmp_path / "src", tmp_path / "out"
        self.src.mkdir()
        self.reads[f"{TREE}/.superlite/golden/row.json"] = [json.dumps(HOST_ROW).encode(), b""]
        self.reads[f"{TREE}/.superlite/golden/small-1.patch"] = [PATCH, b""]
        mp = monkeypatch
        mp.setattr(gr, "POLL_S", 0)
        mp.setattr(gr, "_token", lambda: "abc123")
        mp.setattr(gr, "_PLUGINS", {})
        mp.setattr(gr, "_drop_ref", lambda src, ref: self.calls.append(("drop_ref", src, ref)))
        mp.setattr(gr.fr, "plugin", self.plugin)
        mp.setattr(gr.fr, "push", self.push)
        mp.setattr(gr.fr, "read", self.read)
        mp.setattr(gr.fr, "drop", self.drop)
        mp.setattr(gr.ra, "start_commit", self.start_commit)
        mp.setattr(gr.rw, "run_script", self.run_script)
        mp.setattr(gr.rw, "script_result", self.script_result)
        mp.setattr(gr.rw, "close_script", lambda label, ws: self.calls.append(("close", label, ws)))
        self.plugin_calls = []

    def plugin(self, *a):
        self.plugin_calls.append(a)
        return "/h/plugin"

    def start_commit(self, *a):
        self.start_args = a
        return "c0ffee"

    def push(self, *a):
        self.push_args = a
        if self.push_error:
            raise self.push_error
        return TREE

    def run_script(self, *a):
        self.run_args = a
        self.calls.append(("run",))
        return "w1"

    def script_result(self, label, out):
        self.calls.append(("result",))
        r = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(r, Exception):
            raise r
        return r

    def read(self, label, path, offset=0, timeout_s=30):
        chunks = self.reads.get(path)
        if not chunks:
            return b""
        c = chunks.pop(0) if len(chunks) > 1 else chunks[0]
        if isinstance(c, Exception):
            raise c
        return c

    def drop(self, *a):
        self.calls.append(("drop", *a))
        if self.drop_error:
            raise self.drop_error

    def go(self, case=None, earlier=(0.5,), abort=None, timeout_s=60):
        return gr.attempt("mxn", case or {**CASE}, self.src, timeout_s, 1, PLUGIN, self.out_dir, list(earlier), abort or threading.Event())

    def script(self, earlier=" --earlier 0.5"):
        return (f"python3 /h/plugin/skills/subagent-driven-development/scripts/golden.py attempt --case {TREE}/.superlite/golden/case.json "
                f"--n 1 --timeout 60 --out-dir {TREE}/.superlite --row {TREE}/.superlite/golden/row.json{earlier}")


@pytest.fixture
def env(monkeypatch, tmp_path):
    return Env(monkeypatch, tmp_path)


def not_run(why):
    return {"v": 1, "row": "golden", "case": "small", "attempt": 1, "passed": False, "why": [why], "warn": [], "lead_usd": 0.0,
            "total_usd": 0.0, "lead_turns": 0, "wall_min": 0.0, "started": False, "plugin": PLUGIN, "machine": "mxn"}


def test_ready_ok(monkeypatch):
    monkeypatch.setattr(gr.fr, "tree_argv", lambda: ["x"])
    monkeypatch.setattr(gr.fr, "target", lambda m: m)
    monkeypatch.setattr(gr.fr, "check", lambda m: "")
    assert gr.ready("mxn") == ""


def test_ready_no_remote_tree(monkeypatch):
    monkeypatch.setattr(gr.fr, "tree_argv", lambda: None)
    assert gr.ready("mxn").startswith("no remote_tree command in ") and gr.ready("mxn").endswith("machine.json")


def test_ready_unknown_machine(monkeypatch):
    monkeypatch.setattr(gr.fr, "tree_argv", lambda: ["x"])
    monkeypatch.setattr(gr.fr, "target", lambda m: (_ for _ in ()).throw(gr.fr.RemoteError(f"no enabled Herdr machine {m} (herdr machine list)")))
    assert gr.ready("nope") == "no enabled Herdr machine nope (herdr machine list)"


def test_ready_unreachable(monkeypatch):
    monkeypatch.setattr(gr.fr, "tree_argv", lambda: ["x"])
    monkeypatch.setattr(gr.fr, "target", lambda m: m)
    monkeypatch.setattr(gr.fr, "check", lambda m: "unreachable: ssh timeout")
    assert gr.ready("down") == "unreachable: ssh timeout"


def test_ready_status_failed(monkeypatch):
    monkeypatch.setattr(gr.fr, "tree_argv", lambda: ["x"])
    monkeypatch.setattr(gr.fr, "target", lambda m: m)
    monkeypatch.setattr(gr.fr, "check", lambda m: "herdr machine status failed: timeout")
    assert gr.ready("m") == "herdr machine status failed: timeout"


def test_attempt_round_trip(env):
    row = env.go()
    assert row == {**HOST_ROW, "plugin": PLUGIN, "machine": "mxn"}
    assert (env.out_dir / "golden" / "small-1.patch").read_bytes() == PATCH
    assert env.start_args == (str(env.src), "abc", [], {".superlite/golden/case.json": json.dumps({**CASE}).encode("utf-8")},
                              "refs/superlite/golden/small-1-abc123")
    assert env.push_args == ("mxn", str(env.src), "golden/small-1-abc123", "c0ffee", [], 600)
    assert env.run_args == ("mxn", TREE, env.script(), TREE + "/.superlite/golden/attempt.out", "sl:golden small-1")
    assert ("close", "mxn", "w1") in env.calls
    assert ("drop", "mxn", str(env.src), "golden/small-1-abc123") in env.calls
    assert ("drop_ref", env.src, "refs/superlite/golden/small-1-abc123") in env.calls


def test_attempt_no_earlier_flag(env):
    env.go(earlier=())
    assert env.run_args[2] == env.script(earlier="")
    assert "--earlier" not in env.run_args[2]


def test_attempt_test_cmd_rides_along(env):
    (env.src / ".superlite").mkdir()
    (env.src / ".superlite" / "test-cmd.json").write_bytes(b'{"a": 1}')
    env.go()
    assert env.start_args[3][".superlite/test-cmd.json"] == b'{"a": 1}'


def test_attempt_push_error_is_not_run(env):
    env.push_error = gr.fr.RemoteError("mxn unreachable: ssh")
    assert env.go() == not_run("machine mxn: mxn unreachable: ssh")
    assert ("run",) not in env.calls and not [c for c in env.calls if c[0] == "drop"]


def test_attempt_host_exit_is_not_run(env):
    env.results = [(2, "x\ngolden: cannot read case y")]
    assert env.go()["why"] == ["machine mxn: host attempt exit 2: golden: cannot read case y"]
    assert ("close", "mxn", "w1") in env.calls and [c for c in env.calls if c[0] == "drop"]


def test_attempt_abort_is_not_run(env):
    env.results = [None]
    ab = threading.Event()
    ab.set()
    assert env.go(abort=ab)["why"] == ["machine mxn: aborted"]
    assert ("close", "mxn", "w1") in env.calls


def test_attempt_deadline_is_not_run(env, monkeypatch):
    monkeypatch.setattr(gr, "SLACK_S", 0)
    env.results = [None]
    assert env.go(timeout_s=0)["why"] == ["machine mxn: no result within 0 s"]


def test_attempt_read_errors_retried(env):
    err = gr.fr.RemoteError("mxn unreachable: x")
    env.results = [err, err, (0, "ok")]
    assert env.go()["passed"] is True


def test_attempt_read_errors_give_up(env):
    env.results = [gr.fr.RemoteError("mxn unreachable: x")]
    row = env.go()
    assert row["why"] == ["machine mxn: cannot read the host result: mxn unreachable: x"]
    assert len([c for c in env.calls if c == ("result",)]) == gr.READ_TRIES == 5


def test_attempt_row_unreadable_is_not_run(env):
    env.reads[f"{TREE}/.superlite/golden/row.json"] = [b"not json", b""]
    assert env.go()["why"][0].startswith("machine mxn: host row unreadable: ")


def test_attempt_patch_unreadable_warns(env):
    env.reads[f"{TREE}/.superlite/golden/small-1.patch"] = [gr.fr.RemoteError("gone")]
    row = env.go()
    assert row["patch"] == "" and row["warn"][-1] == "no patch saved: cannot read it from mxn: gone"
    assert {k: v for k, v in row.items() if k not in ("patch", "warn")} == {k: v for k, v in {**HOST_ROW, "plugin": PLUGIN, "machine": "mxn"}.items() if k not in ("patch", "warn")}


def test_attempt_patch_bad_name_ignored(env, tmp_path):
    env.reads[f"{TREE}/.superlite/golden/row.json"] = [json.dumps({**HOST_ROW, "patch": "../x.patch"}).encode(), b""]
    row = env.go()
    assert row["patch"] == "" and row["warn"][-1] == "no patch saved: bad name ../x.patch"
    assert not (env.out_dir / "x.patch").exists() and not list((env.out_dir / "golden").glob("*")) if (env.out_dir / "golden").exists() else True


def test_attempt_drop_failure_is_one_stderr_line(env, capsys):
    env.drop_error = gr.fr.RemoteError("busy")
    assert env.go()["passed"] is True
    assert capsys.readouterr().err == "golden: tree golden/small-1-abc123 kept on mxn: busy\n"


def test_plugin_tree_pushed_once_per_label(env):
    env.go()
    env.reads[f"{TREE}/.superlite/golden/row.json"] = [json.dumps(HOST_ROW).encode(), b""]
    env.reads[f"{TREE}/.superlite/golden/small-1.patch"] = [PATCH, b""]
    env.results = [(0, "ok")]
    env.go()
    assert env.plugin_calls == [("mxn", gr.rw.SUPERLITE_ROOT, 600)]
