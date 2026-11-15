# tests/scripts/test_golden.py
import json, os, sys, types
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import golden  # noqa: E402

ROW = {"lead": {"cost_usd": 3.0, "turns": 60, "wall_s": 1800}, "workers_total": {"cost_usd": 0.5},
       "tests": {"full": 1}, "grade": {"tasks": 1, "final_rounds": 1}}
HIDDEN = {"exit": 0, "passed": 3, "failed": 0, "skipped": 0, "errors": 0}
SUITE = {"passed": 10, "failed": 0}
FACTS = {"state": "parked", "reason": "BLOCKED (ship not approved)", "hidden": HIDDEN, "suite": SUITE, "row": ROW}
CASE = {"id": "small", "baseline": {"lead_usd": 3.1, "lead_turns": 60}, "test_cmd": "pytest -q",
        "hidden_tests": [{"path": "tests/t.py", "text": "x"}]}


def facts(**kw):
    return {**FACTS, **kw}


def row_with(**kw):
    return {**ROW, **kw}


def test_score_examples():
    assert golden.score(CASE, FACTS) == {"passed": True, "why": [], "warn": [], "lead_usd": 3.0, "total_usd": 3.5,
                                         "lead_turns": 60, "wall_min": 30.0, "hidden_share": 1.0, "suite": SUITE}
    red = {"exit": 1, "passed": 3, "failed": 2, "skipped": 0, "errors": 1}
    r = golden.score(CASE, facts(hidden=red))
    assert r["passed"] is True and r["why"] == [] and r["hidden_share"] == 0.5


def test_score_suite_red_fails():
    r = golden.score(CASE, facts(suite={"passed": 9, "failed": 1}))
    assert r["passed"] is False and r["why"] == ["suite red"]


@pytest.mark.parametrize("suite", [None, {"passed": 0, "failed": 0}])
def test_score_no_green_full_suite_fails(suite):
    r = golden.score(CASE, facts(suite=suite))
    assert r["passed"] is False and r["why"] == ["no green full suite run"]


def test_hidden_share_computed():
    assert golden.hidden_share({"passed": 3, "failed": 2, "errors": 1}) == 0.5
    assert golden.hidden_share({"passed": 0, "failed": 0, "errors": 0}) == 0.0
    assert golden.hidden_share({"passed": 1, "failed": 2, "errors": 0}) == 0.33
    assert golden.hidden_share(None) == 0.0


def test_score_warns_on_share_drop():
    low = {"exit": 1, "passed": 1, "failed": 3, "skipped": 0, "errors": 0}
    r = golden.score(CASE, facts(hidden=low, earlier=[0.75, 1.0]))
    assert r["passed"] is True and r["warn"] == ["hidden tests 0.25 below earlier runs (lowest 0.75)"]
    assert golden.score(CASE, facts(hidden=low, earlier=[]))["warn"] == []
    assert golden.score(CASE, facts(hidden=low, earlier=[0.25, 1.0]))["warn"] == []


def test_score_no_row():
    r = golden.score(CASE, facts(row=None))
    assert r["passed"] is False and r["why"] == ["no cost row"]


def test_score_timeout():
    r = golden.score(CASE, facts(state="timeout", reason="", hidden=None, suite=None))
    assert r["passed"] is False and r["why"] == ["timeout"]


def test_score_other_block():
    r = golden.score(CASE, facts(reason="BLOCKED: tests red"))
    assert r["why"] == ["lead ended: BLOCKED: tests red"]


def test_score_process_facts():
    r = golden.score(CASE, facts(row=row_with(grade={"tasks": 0, "final_rounds": 0}, tests={"full": 0})))
    assert r["why"] == ["no plan tasks", "no final review", "suite never ran"]


def test_score_warns():
    r = golden.score(CASE, facts(row=row_with(lead={"cost_usd": 7.0, "turns": 130, "wall_s": 60})))
    assert r["passed"] is True
    assert r["warn"] == ["lead cost 7.00 above 2x baseline 3.10", "lead turns 130 above 2x baseline 60"]
    assert golden.score({"id": "x"}, facts(row=row_with(lead={"cost_usd": 70, "turns": 900, "wall_s": 1})))["warn"] == []


def test_hidden_check(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (calls.append((cmd, cwd)) or (0, "1 passed in 0.1s")))
    assert golden.hidden_ok(CASE, tmp_path) is True
    assert (tmp_path / "tests/t.py").read_text() == "x"
    assert calls == [(["pytest", "-q", "tests/t.py"], tmp_path)]
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (1, "red"))
    assert golden.hidden_ok(CASE, tmp_path) is False


class Fake:
    def __init__(self, outcomes=None, start_ok=True, row_raises=False):
        self.outcomes = list(outcomes or [True])
        self.start_ok, self.row_raises = start_ok, row_raises
        self.clones, self.cleaned, self.works = [], [], []
        self.i = 0

    def seal(self, case, src, work):
        self.works.append(work)
        c = work / case["id"]
        c.mkdir(parents=True)
        self.clones.append(c)
        return c

    def start(self, clone, config=None):
        return {"ok": True, "lead": "W1", "out": ""} if self.start_ok else {"ok": False, "lead": None, "out": "BLOCKED: B1 lead did not start"}

    def wait(self, clone, timeout_s=5400):
        return {"state": "parked", "reason": "BLOCKED (ship not approved)"}

    def row(self, clone):
        if self.row_raises:
            raise RuntimeError("boom")
        return ROW

    def worktree(self, clone):
        return clone

    def suite(self, clone):
        return {"passed": 10, "failed": 0}

    def cleanup(self, clone):
        self.cleaned.append(clone)


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "plugin.json").write_text('{"version": "1.5.244"}')
    out = tmp_path / "out" / "results.jsonl"
    state = {"i": 0}

    def fake_run(cmd, cwd=None, timeout=None):
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "076a39a"
        return 0, ""
    monkeypatch.setattr(golden, "_run", fake_run)
    return types.SimpleNamespace(repo=repo, out=out, mp=monkeypatch, state=state)


def flaky(env, results):  # each attempt's full suite is green or red
    it = iter(results)
    env.mp.setattr(Fake, "suite", lambda self, clone: {"passed": 10, "failed": 0 if next(it) else 2})
    env.mp.setattr(golden, "hidden_run", lambda case, wt: {"ok": True, "exit": 0, "passed": 1, "failed": 0, "skipped": 0, "errors": 0, "out": "t"})


def test_run_example(env):
    flaky(env, [True])
    rows = golden.run([CASE], env.repo, env.out, seal=Fake())
    assert rows == [{"v": 1, "row": "golden", "case": "small", "attempt": 1, "passed": True, "why": [], "warn": [],
                     "started": True, "lead_usd": 3.0, "total_usd": 3.5, "lead_turns": 60, "wall_min": 30.0, "plugin": "1.5.244+076a39a",
                     "hidden": {"exit": 0, "passed": 1, "failed": 0, "skipped": 0, "errors": 0}, "hidden_share": 1.0,
                     "suite": {"passed": 10, "failed": 0}}]


def test_run_rerun_once(env):
    flaky(env, [False, True])
    rows = golden.run([CASE], env.repo, env.out, seal=Fake())
    assert [(r["attempt"], r["passed"]) for r in rows] == [(1, False), (2, True)]


def test_run_no_rerun(env):
    flaky(env, [False])
    rows = golden.run([CASE], env.repo, env.out, rerun=False, seal=Fake())
    assert [(r["attempt"], r["passed"]) for r in rows] == [(1, False)]


def test_run_start_failure(env):
    fake = Fake(start_ok=False)
    rows = golden.run([CASE], env.repo, env.out, rerun=False, seal=fake)
    assert rows[0]["passed"] is False and rows[0]["why"] == ["lead did not start: BLOCKED: B1 lead did not start"]
    assert fake.cleaned == fake.clones and len(fake.clones) == 1


def test_run_start_failure_marked_and_not_rerun(env):
    fake = Fake(start_ok=False)
    rows = golden.run([CASE], env.repo, env.out, rerun=True, seal=fake)
    assert len(rows) == 1 and rows[0]["started"] is False and rows[0]["passed"] is False
    assert rows[0]["why"][0].startswith("lead did not start: ")


def test_history_skips_unstarted(tmp_path, capsys):
    out = tmp_path / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    rows = [{"row": "golden", "case": "small", "lead_usd": 2.0, "started": True},
            {"row": "golden", "case": "small", "lead_usd": 0.0, "started": False},
            {"row": "golden", "case": "small", "lead_usd": 4.0}]
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert golden.main(["history", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "small: runs 2 median lead $3.00 (noise from 5 runs)"


def test_cli_not_run_line(cli, capsys):
    cli.ok["v"] = False
    cli.started = False
    assert golden.main(["run", "--ids", "small", "--root", cli.root]) == 1
    assert capsys.readouterr().out.strip() == "small: NOT RUN lead did not start: cap: 0"


def test_run_cleanup_always(env):
    fake = Fake(row_raises=True)
    flaky(env, [True])
    with pytest.raises(RuntimeError):
        golden.run([CASE], env.repo, env.out, seal=fake)
    assert fake.cleaned == fake.clones and len(fake.clones) == 1
    assert not fake.works[0].exists()


def test_run_parallel_isolated(env):
    flaky(env, [True, True])
    fake = Fake()
    golden.run([CASE, {**CASE, "id": "typical"}], env.repo, env.out, seal=fake)
    assert len(set(fake.clones)) == 2
    assert len({c.parent.parent for c in fake.clones}) == 1
    assert all(not c.exists() for c in fake.clones)
    assert not fake.clones[0].parent.parent.exists()


def test_results_append(env):
    flaky(env, [True, True])
    golden.run([CASE], env.repo, env.out, seal=Fake())
    first = env.out.read_text()
    golden.run([CASE], env.repo, env.out, seal=Fake())
    text = env.out.read_text()
    assert text.startswith(first) and len(text.splitlines()) == 2


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    ids = ["small", "typical", "large"]
    monkeypatch.setattr(golden.golden_case, "cases", lambda root: [{**CASE, "id": i} for i in ids])
    seen = []
    ok = {"v": True}

    def fake_run(cases, src, out, rerun=True, timeout_s=5400, seal=None):
        seen.append([c["id"] for c in cases])
        if ns.__dict__.get("started") is False:
            return [{"case": c["id"], "passed": False, "started": False, "why": ["lead did not start: cap: 0", "more"]} for c in cases]
        return [{"case": c["id"], "passed": ok["v"] or c["id"] != "small", "why": ["x"]} for c in cases]
    monkeypatch.setattr(golden, "run", fake_run)
    ns = types.SimpleNamespace(root=str(tmp_path), seen=seen, ok=ok)
    return ns


def test_cli_levels(cli):
    assert golden.main(["run", "--level", "minor", "--root", cli.root]) == 0
    assert golden.main(["run", "--level", "major", "--root", cli.root]) == 0
    assert golden.main(["run", "--ids", "large", "--root", cli.root]) == 0
    assert cli.seen == [["small", "typical"], ["small", "typical", "large"], ["large"]]
    assert golden.main(["run", "--ids", "nope", "--root", cli.root]) == 2


def test_cli_exit(cli):
    assert golden.main(["run", "--root", cli.root]) == 0
    cli.ok["v"] = False
    assert golden.main(["run", "--root", cli.root]) == 1


def test_cli_worker_refused(cli, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "1")
    assert golden.main(["run", "--root", cli.root]) == 2


def test_history(tmp_path, capsys):
    out = tmp_path / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    out.write_text("".join(json.dumps({"row": "golden", "case": "small", "lead_usd": v}) + "\n" for v in (2.0, 3.0, 4.0)))
    assert golden.main(["history", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "small: runs 3 median lead $3.00 (noise from 5 runs)"


def test_history_noise_from_five_runs(tmp_path, capsys):
    out = tmp_path / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    out.write_text("".join(json.dumps({"row": "golden", "case": "small", "lead_usd": v}) + "\n" for v in (2.0, 3.0, 4.0, 3.0)))
    golden.main(["history", "--root", str(tmp_path)])
    assert capsys.readouterr().out.strip() == "small: runs 4 median lead $3.00 (noise from 5 runs)"
    out.write_text("".join(json.dumps({"row": "golden", "case": "small", "lead_usd": v}) + "\n" for v in (2.0, 3.0, 4.0, 3.0, 3.0)))
    golden.main(["history", "--root", str(tmp_path)])
    assert capsys.readouterr().out.strip() == "small: runs 5 median lead $3.00 max/min 2.00"


@pytest.mark.parametrize("out,want", [("1 skipped in 0.1s", False), ("3 passed in 1s", True),
                                      ("2 passed, 1 skipped in 1s", False), ("", False)])
def test_hidden_needs_a_passed_test(tmp_path, monkeypatch, out, want):
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (0, out))
    assert golden.hidden_ok(CASE, tmp_path) is want


def test_hidden_text_written_as_utf8(tmp_path, monkeypatch):
    case = {**CASE, "hidden_tests": [{"path": "tests/t.py", "text": "x = 'caf\u00e9'\n"}]}
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (0, "1 passed"))
    real = Path.write_text
    monkeypatch.setattr(Path, "write_text", lambda self, data, encoding=None, **kw: real(self, data, encoding=encoding or "cp1252", **kw))
    golden.hidden_ok(case, tmp_path)
    assert (tmp_path / "tests/t.py").read_bytes() == b"x = 'caf\xc3\xa9'\n"


def test_hidden_check_has_timeout(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (seen.append(timeout) or (0, "")))
    golden.hidden_ok(CASE, tmp_path)
    assert seen == [golden.TEST_TIMEOUT]


def test_score_parked_other_reason_and_error():
    assert golden.score(CASE, facts(reason="idle for 10 minutes"))["why"] == ["lead ended: idle for 10 minutes"]
    assert golden.score(CASE, facts(state="needs_decision", reason="Which?"))["why"] == ["lead ended: needs_decision Which?"]
    assert golden.score(CASE, facts(state="timeout", reason="", hidden=None, suite=None))["why"] == ["timeout"]


def test_hidden_tests_wait_for_lead(env):
    fake = Fake()
    fake.wait = lambda clone, timeout_s=5400: {"state": "timeout", "reason": ""}
    env.mp.setattr(golden, "hidden_run", lambda case, wt: pytest.fail("hidden tests written while the lead may still run"))
    env.mp.setattr(golden, "SLICE_S", 10)
    rows = golden.run([CASE], env.repo, env.out, rerun=False, timeout_s=10, seal=fake)
    assert rows[0]["why"] == ["timeout"] and fake.cleaned == fake.clones


def test_await_cost_cap_reads_live_cost(env):
    waits = []
    fake = Fake()
    fake.wait = lambda clone, timeout_s=5400: waits.append(timeout_s) or {"state": "timeout", "reason": ""}
    fake.lead_cost = lambda clone: 100.0
    res = golden._await(fake, Path("c"), CASE, 5400)
    assert res["state"] == "timeout" and len(waits) == 1


def test_run_keeps_other_rows_on_error(env):
    flaky(env, [True, True])
    fake = Fake()
    real_row = fake.row
    fake.row = lambda clone: (_ for _ in ()).throw(RuntimeError("boom")) if clone.name == "small" else real_row(clone)
    with pytest.raises(RuntimeError):
        golden.run([CASE, {**CASE, "id": "typical"}], env.repo, env.out, rerun=False, seal=fake)
    assert [json.loads(x)["case"] for x in env.out.read_text().splitlines()] == ["typical"]


def test_timed_out_attempt_keeps_live_lead_cost(env):
    fake = Fake()
    fake.wait = lambda clone, timeout_s=5400: {"state": "timeout", "reason": ""}
    fake.row = lambda clone: None
    fake.lead_cost = lambda clone: 9.0
    env.mp.setattr(golden, "SLICE_S", 10)
    rows = golden.run([CASE], env.repo, env.out, rerun=False, timeout_s=10, seal=fake)
    assert rows[0]["why"] == ["timeout"] and rows[0]["lead_usd"] == 9.0 and rows[0]["total_usd"] == 9.0


def test_history_ignores_zero_cost_rows(tmp_path, capsys):
    out = tmp_path / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    out.write_text("".join(json.dumps({"row": "golden", "case": "small", "lead_usd": v}) + "\n" for v in (0.0, 2.0, 4.0)))
    golden.main(["history", "--root", str(tmp_path)])
    assert capsys.readouterr().out.strip() == "small: runs 2 median lead $3.00 (noise from 5 runs)"


def test_history_skips_malformed_line(tmp_path, capsys):
    out = tmp_path / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    out.write_text('{"row": "golden", "case": "small", "lead_usd": 2.0}\n{torn line\n[1]\n')
    assert golden.main(["history", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "small: runs 1 median lead $2.00 (noise from 5 runs)"


def test_cli_run_error_exits_2(cli, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("git clone: no such repo")
    monkeypatch.setattr(golden, "run", boom)
    assert golden.main(["run", "--root", cli.root]) == 2
    assert "golden: git clone: no such repo" in capsys.readouterr().err


def test_run_output_not_utf8_does_not_raise():
    code, out = golden._run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')"])
    assert code == 0 and out.startswith("a") and out.endswith("b")


REAL_STOP = ("BLOCKED: #848 is built and reviewed, but shipping is not approved, so nothing is committed or merged. "
             "The full suite passed (10873 passed, 0 failed)")


LARGE_STOP = ("BLOCKED. Ship isn't approved. Both fixes are built, the full unit suite passes and the final reviewer approved; "
              "nothing is committed and nothing was")


@pytest.mark.parametrize("reason", [REAL_STOP, "BLOCKED (ship not approved)", "BLOCKED: ship is not yet approved",
                                    "BLOCKED: Ship approval missing", "BLOCKED: ship approval not given",
                                    LARGE_STOP, "Ship isn't approved", "not approved to ship", "no ship approval",
                                    "shipping is not approved"])
def test_score_ship_block_reasons_pass(reason):
    r = golden.score(CASE, facts(reason=reason))
    assert r["passed"] is True and r["why"] == []


@pytest.mark.parametrize("reason", ["BLOCKED: tests red", "idle", "BLOCKED: relationship graph broken",
                                    "BLOCKED: reviewer did not approve the plan"])
def test_score_non_ship_block_still_fails(reason):
    assert golden.score(CASE, facts(reason=reason))["why"] == [f"lead ended: {reason}"]


def red_run(cmd, cwd=None, timeout=None):
    return 1, "x" * 2000 + "\nFAILED t.py::a\n2 passed, 1 failed, 1 skipped, 3 errors in 1.0s"


def test_hidden_run_reports_facts(tmp_path, monkeypatch):
    monkeypatch.setattr(golden, "_run", red_run)
    res = golden.hidden_run(CASE, tmp_path)
    assert res["ok"] is False and res["exit"] == 1
    assert (res["passed"], res["failed"], res["skipped"], res["errors"]) == (2, 1, 1, 3)
    assert res["out"].endswith("3 errors in 1.0s") and len(res["out"]) == 1200
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (0, "4 passed in 1s"))
    res = golden.hidden_run(CASE, tmp_path)
    assert res["ok"] is True and (res["passed"], res["failed"], res["skipped"], res["errors"]) == (4, 0, 0, 0)


def run_hidden(env, hidden_run, **attrs):
    def fake_run(cmd, cwd=None, timeout=None):
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "076a39a"
        return hidden_run(cmd, cwd, timeout) if cmd[0] == "pytest" else (0, "")
    env.mp.setattr(golden, "_run", fake_run)
    fake = Fake()
    for k, v in attrs.items():
        setattr(fake, k, v)
    return golden.run([CASE], env.repo, env.out, rerun=False, seal=fake)[0]


def test_row_stores_red_hidden_facts_and_tail(env):
    row = run_hidden(env, red_run)
    assert row["hidden"] == {"exit": 1, "passed": 2, "failed": 1, "skipped": 1, "errors": 3}
    assert row["hidden_out"].endswith("3 errors in 1.0s") and len(row["hidden_out"]) == 1200


def test_row_stores_green_hidden_facts_without_tail(env):
    row = run_hidden(env, lambda cmd, cwd, timeout: (0, "4 passed in 1s"))
    assert row["hidden"] == {"exit": 0, "passed": 4, "failed": 0, "skipped": 0, "errors": 0}
    assert "hidden_out" not in row


def test_row_without_hidden_run_has_no_hidden_key(env):
    env.mp.setattr(golden, "SLICE_S", 10)
    fake = Fake()
    fake.wait = lambda clone, timeout_s=5400: {"state": "timeout", "reason": ""}
    row = golden.run([CASE], env.repo, env.out, rerun=False, timeout_s=10, seal=fake)[0]
    assert "hidden" not in row and "hidden_out" not in row


def test_attempt_saves_patch_before_hidden_tests(env):
    order = []

    def hidden(cmd, cwd, timeout):
        order.append("hidden")
        return 1, "red"
    base_case = {**CASE, "base": "abc"}
    seen = []

    def patch(wt, base):
        order.append("patch")
        seen.append(base)
        return "diff --git a/a b/a\n"
    fake = Fake()
    fake.patch = patch

    def fake_run(cmd, cwd=None, timeout=None):
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "076a39a"
        return hidden(cmd, cwd, timeout) if cmd[0] == "pytest" else (0, "")
    env.mp.setattr(golden, "_run", fake_run)
    row = golden.run([base_case], env.repo, env.out, rerun=False, seal=fake)[0]
    assert order == ["patch", "hidden"] and seen == ["abc"]
    assert row["patch"] == "small-1.patch"
    assert (env.out.parent / "golden" / "small-1.patch").read_text() == "diff --git a/a b/a\n"


def test_attempt_empty_patch_writes_no_file(env):
    fake = Fake()
    fake.patch = lambda wt, base: ""
    env.mp.setattr(golden, "hidden_run", lambda case, wt: {"ok": True, "exit": 0, "passed": 1, "failed": 0, "skipped": 0, "errors": 0, "out": ""})
    row = golden.run([{**CASE, "base": "abc"}], env.repo, env.out, rerun=False, seal=fake)[0]
    assert row["patch"] == "" and not (env.out.parent / "golden").exists()
    assert "no patch saved" in row["warn"]


def test_attempt_empty_patch_warn_carries_the_git_reason(env):
    fake = Fake()
    fake.patch = lambda wt, base: ""
    fake.patch_error = lambda wt: "fatal: bad tree object"
    env.mp.setattr(golden, "hidden_run", lambda case, wt: {"ok": True, "exit": 0, "passed": 1, "failed": 0, "skipped": 0, "errors": 0, "out": ""})
    row = golden.run([{**CASE, "base": "abc"}], env.repo, env.out, rerun=False, seal=fake)[0]
    assert "no patch saved: fatal: bad tree object" in row["warn"]


def test_attempt_without_a_patch_function_has_no_patch_key(env):
    row = golden.run([{**CASE, "base": "abc"}], env.repo, env.out, rerun=False, seal=Fake())[0]
    assert "patch" not in row and "no patch saved" not in row["warn"]


def test_run_red_hidden_tests_with_good_facts_pass(env):
    env.mp.setattr(golden, "hidden_run", lambda case, wt: {"ok": False, "exit": 1, "passed": 3, "failed": 2, "skipped": 0, "errors": 1, "out": "red"})
    row = golden.run([CASE], env.repo, env.out, rerun=False, seal=Fake())[0]
    assert row["passed"] is True and row["why"] == [] and row["hidden_share"] == 0.5
    assert row["hidden_out"] == "red" and row["suite"] == {"passed": 10, "failed": 0}


def test_run_suite_red_fails_the_attempt(env):
    flaky(env, [False])
    row = golden.run([CASE], env.repo, env.out, rerun=False, seal=Fake())[0]
    assert row["passed"] is False and row["why"] == ["suite red"] and row["suite"] == {"passed": 10, "failed": 2}


def test_run_without_suite_summary_fails(env):
    fake = Fake()
    fake.suite = lambda clone: None
    row = golden.run([CASE], env.repo, env.out, rerun=False, seal=fake)[0]
    assert row["why"] == ["no green full suite run"] and "suite" not in row


def test_run_warns_when_share_drops_below_earlier_runs(env):
    earlier = [{"row": "golden", "case": "small", "started": True, "hidden_share": 0.8},
               {"row": "golden", "case": "small", "started": True, "hidden_share": 1.0},
               {"row": "golden", "case": "typical", "started": True, "hidden_share": 1.0},
               {"row": "golden", "case": "small", "started": False, "hidden_share": 0.1},
               {"row": "golden", "case": "small", "started": True}]
    env.out.parent.mkdir(parents=True)
    env.out.write_text("".join(json.dumps(r) + "\n" for r in earlier) + "torn\n")
    env.mp.setattr(golden, "hidden_run", lambda case, wt: {"ok": False, "exit": 1, "passed": 1, "failed": 1, "skipped": 0, "errors": 0, "out": "r"})
    row = golden.run([CASE], env.repo, env.out, rerun=False, seal=Fake())[0]
    assert row["warn"] == ["hidden tests 0.50 below earlier runs (lowest 0.80)"]


def test_run_first_run_has_no_drop_warning(env):
    env.mp.setattr(golden, "hidden_run", lambda case, wt: {"ok": False, "exit": 1, "passed": 0, "failed": 4, "skipped": 0, "errors": 0, "out": "r"})
    row = golden.run([CASE], env.repo, env.out, rerun=False, seal=Fake())[0]
    assert row["warn"] == [] and row["hidden_share"] == 0.0


def test_cli_line_shape(cli, monkeypatch, capsys):
    rows = [{"case": "small", "passed": True, "why": [], "warn": [], "lead_usd": 3.0, "total_usd": 3.5, "wall_min": 30.0,
             "hidden": {"passed": 3, "failed": 2, "errors": 1}},
            {"case": "typical", "passed": False, "why": ["suite red", "no final review"], "warn": ["hidden tests 0.50 below earlier runs (lowest 0.80)"],
             "lead_usd": 1.234, "total_usd": 2.0, "wall_min": 4.5, "hidden": {"passed": 0, "failed": 0, "errors": 0}}]
    monkeypatch.setattr(golden, "run", lambda *a, **k: rows)
    assert golden.main(["run", "--ids", "small,typical", "--root", cli.root]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "small: PASS lead $3.00 total $3.50 30.0 min, hidden 3/6",
        "typical: FAIL lead $1.23 total $2.00 4.5 min, hidden 0/0; why: suite red; no final review; warn: hidden tests 0.50 below earlier runs (lowest 0.80)"]


def test_history_median_hidden_share(tmp_path, capsys):
    out = tmp_path / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    out.write_text("".join(json.dumps({"row": "golden", "case": "small", "lead_usd": 2.0 + i, "hidden_share": s}) + "\n"
                           for i, s in enumerate((0.5, 1.0, 0.75))))
    assert golden.main(["history", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "small: runs 3 median lead $3.00 hidden 0.75 (noise from 5 runs)"
