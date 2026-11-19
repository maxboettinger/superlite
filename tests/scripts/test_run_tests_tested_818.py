"""run_tests names the tree it tested and the result bundle it read (GitHub #818)."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, make_plan, run
from test_run_tests_plan_fallback import OUT, git
from test_run_tests_tree_state_511 import set_cmd

sys.path.insert(0, str(SCRIPTS))
import fleet_report  # noqa: E402
import run_tests  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
HEADER = "Test session results, code coverage, and logs:"
TAIL = "; tree .superlite/trees/T1; lacks 1 changed file of the run root: src/b.txt"


def stack(tmp_path, cmd=None):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "src" / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\n_sl_home/\n", encoding="utf-8")
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    plan = make_plan(tmp_path / "docs" / "plans", [{"id": "T1", "owns": "src/a.txt"}, {"id": "T2", "owns": "src/b.txt"}], name="p.md")
    (tmp_path / ".superlite").mkdir()
    set_cmd(tmp_path, cmd or f"sh -c 'echo \"{OUT}\"'")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "src" / "a.txt").write_text("a2", encoding="utf-8")
    (tmp_path / "src" / "b.txt").write_text("b2", encoding="utf-8")
    return plan


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def tree_run(tmp_path, plan, *extra):
    return run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), *extra, cwd=tmp_path)


def bundle_cmd(path):
    return f"sh -c 'printf \"{HEADER}\\n\\t{path}\\n\"; echo \"{OUT}\"'"


def test_result_bundles_examples():
    rb = run_tests.result_bundles
    assert rb(["xcodebuild test -scheme App -resultBundlePath out/r.xcresult"], "", "/w") == ["/w/out/r.xcresult"]
    assert rb(["xcodebuild test -scheme App"], f"{HEADER}\n\t/dd/Logs/Test/Test-App.xcresult\n\n** TEST SUCCEEDED **", "/w") == ["/dd/Logs/Test/Test-App.xcresult"]
    assert rb(["pytest -q"], "3 passed", "/w") == []
    assert rb(["x"], "Writing result bundle at path:\n\t/dd/w.xcresult\n", "/w") == ["/dd/w.xcresult"]
    assert rb(["x -resultBundlePath /abs/r.xcresult"], "", "/w") == ["/abs/r.xcresult"]
    assert rb(["x -resultBundlePath /abs/r.xcresult"], f"{HEADER}\n\t/abs/r.xcresult\n", "/w") == ["/abs/r.xcresult"]
    assert rb(["x -resultBundlePath 'out dir/r.xcresult'"], "", "/w") == ["/w/out dir/r.xcresult"]
    assert rb(["x 'unclosed"], "", "/w") == []
    text = "".join(f"{HEADER}\n\t/dd/{i}.xcresult\n" for i in range(8))
    assert rb(["x"], text, "/w") == [f"/dd/{i}.xcresult" for i in range(5)]


def test_tested_tail_examples():
    tt = run_tests.tested_tail
    assert tt({"tree": ".superlite/trees/T3", "lacks": ["App/Foo.swift", "App/Bar.swift"]}) == "tree .superlite/trees/T3; lacks 2 changed files of the run root: App/Foo.swift, App/Bar.swift"
    assert tt({"tree": ".superlite/trees/worker-W2", "drift": ["a.swift"], "result_bundles": ["/dd/r.xcresult", "/dd/s.xcresult"]}) == "tree .superlite/trees/worker-W2; 1 file changed while the tests ran: a.swift; result bundle /dd/r.xcresult (+1 more)"
    assert tt({"passed": 3, "failed": 0}) == ""
    assert tt({"lacks": list("vwxyz")}) == "lacks 5 changed files of the run root: v, w, x (+2 more)"
    assert tt({"lacks": ["x"]}) == "lacks 1 changed file of the run root: x"
    assert tt({"result_bundles": ["/dd/r.xcresult"]}) == "result bundle /dd/r.xcresult"


def test_outside_bundles():
    ob = run_tests.outside_bundles
    tree = "/w/.superlite/trees/T1"
    assert ob([f"{tree}/.build/DerivedData/Logs/Test/r.xcresult", "/dd/x.xcresult"], tree, "xcodebuild test -scheme A") == ["/dd/x.xcresult"]
    assert ob(["/dd/x.xcresult"], tree, "maxapp test --ios") == []
    assert ob(["/dd/x.xcresult"], tree, "CI=1 maxapp test") == []


def test_summary_line_appends_tail():
    d = {"mode": "fast", "passed": 3, "failed": 0, "tree": ".superlite/trees/T1", "lacks": ["a.swift"]}
    assert run_tests.summary_line(d) == "tests (fast): 3 passed, 0 failed; tree .superlite/trees/T1; lacks 1 changed file of the run root: a.swift"
    assert run_tests.summary_line({"mode": "fast", "passed": 3, "failed": 0}) == "tests (fast): 3 passed, 0 failed"


def test_green_tree_run_names_lacking_files(tmp_path):
    plan = stack(tmp_path)
    cp = tree_run(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    data = summary(tmp_path)
    assert data["tree"] == ".superlite/trees/T1"
    assert data["lacks"] == ["src/b.txt"]
    assert "drift" not in data
    assert "run_tests: tested tree .superlite/trees/T1; lacks 1 changed file of the run root: src/b.txt" in cp.err


def test_drift_recorded_on_green(tmp_path):
    root = tmp_path.resolve()
    plan = stack(tmp_path, f"sh -c 'echo more >> {root}/src/a.txt; echo \"{OUT}\"'")
    cp = tree_run(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["drift"] == ["src/a.txt"]
    assert "1 file changed while the tests ran: src/a.txt" in cp.err


def test_background_wait_line_names_tree(tmp_path):
    plan = stack(tmp_path)
    cp = tree_run(tmp_path, plan, "--background")
    assert cp.returncode == 0, cp.both
    w = run(RUN_TESTS, "--wait", "--timeout", "120", cwd=tmp_path)
    assert w.returncode == 0, w.both
    assert w.err.strip().splitlines()[-1].endswith(TAIL)


def test_bundle_outside_tree_warns(tmp_path):
    out = f"{tmp_path.resolve()}/dd/Logs/Test/x.xcresult"
    tmp_path = tmp_path / "proj"
    tmp_path.mkdir()
    plan = stack(tmp_path, bundle_cmd(out))
    cp = tree_run(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    data = summary(tmp_path)
    assert data["result_bundles"] == [out]
    assert f"result bundle {out} is outside the tree .superlite/trees/T1: it may hold another build's results" in data["warning"]
    assert "run_tests: WARNING: result bundle" in cp.err


def test_bundle_inside_tree_is_relative(tmp_path):
    root = tmp_path.resolve()
    inside = f"{root}/.superlite/trees/T1/.build/DerivedData/Logs/Test/x.xcresult"
    plan = stack(tmp_path, bundle_cmd(inside))
    cp = tree_run(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    data = summary(tmp_path)
    assert data["result_bundles"] == [".superlite/trees/T1/.build/DerivedData/Logs/Test/x.xcresult"]
    assert "warning" not in data
    assert "WARNING: result bundle" not in cp.err


def test_root_run_names_bundle(tmp_path):
    out = f"{tmp_path.resolve()}/dd/x.xcresult"
    tmp_path = tmp_path / "proj"
    tmp_path.mkdir()
    stack(tmp_path, bundle_cmd(out))
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    data = summary(tmp_path)
    assert data["result_bundles"] == [out]
    assert "tree" not in data
    assert f"run_tests: result bundle {out}" in cp.err
    assert "run_tests: tested" not in cp.err


def test_python_run_unchanged(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "test_ok.py", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    data = summary(tmp_path)
    assert not {"tree", "lacks", "drift", "result_bundles"} & set(data)
    assert "run_tests: tested" not in cp.err
    assert "result bundle" not in cp.err


def test_work_contract_names_tree_and_bundle():
    ph = '"tests": "<test command and result line, with the tree and result bundle run_tests named>"'
    for text in (fleet_report.WORK, fleet_report.WORK_BATCH, fleet_report.PLANNED):
        assert ph in text
    msg = fleet_report.brief_message("implementer", "do it")
    assert msg.rstrip().endswith(fleet_report.WORK.rstrip())
    got = fleet_report.parse('Status: DONE\n```json\n{"status": "DONE", "files": [], "tests": "x; tree .superlite/trees/T1", "red": "none - no test", "findings": [], "summary": "s"}\n```\n', allow_json=True)
    assert got["tests"] == "x; tree .superlite/trees/T1"
