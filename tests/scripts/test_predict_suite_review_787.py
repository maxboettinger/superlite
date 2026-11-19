"""#787: the forecast counts a task's existing test cases and the review rounds of a security-flagged package."""
from __future__ import annotations

import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402
import predict  # noqa: E402

SHIPPED = predict.CONFIG_DIR / "predictor.json"
FOCUS = "## Review Focus\n\n- auth: protocol, state; security review required\n\n"


def shipped():
    return predict.load_coef(str(SHIPPED))


def live_coef(tmp_path, case_s=0.5):
    live = {"tests": {"fast_min": 1.0, "case_s": case_s, "case_source": "prior"}, "contention": {"factor": 1.0}, "root": str(tmp_path)}
    return predict.apply_live(shipped(), live)


def block(tid="T1", owns="src/big.py, tests/test_big.py", tests="fast"):
    return "\n".join([f"### {tid} task · Complexity 2 · Est. context 30k", f"**Owns:** {owns}", "**Components:** 1",
                      "**LOC owned:** 100", f"**Tests:** {tests}", "**Model:** sonnet", ""]) + "\n"


def plan_of(*parts, tmp_path):
    p = tmp_path / "plan.md"
    p.write_text("# P\n\n**Goal:** test.\n\n" + "\n".join(parts), encoding="utf-8")
    return plan_tools.Plan.load(str(p))


def write_cases(tmp_path, n, rel="tests/test_big.py", names=None):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    names = names or [f"test_{i}" for i in range(n)]
    f.write_text("".join(f"def {nm}():\n    pass\n\n" for nm in names), encoding="utf-8")


def predict_one(tmp_path, coef, tests="fast", owns="src/big.py, tests/test_big.py", plan=None):
    pl = plan or plan_of(block(owns=owns, tests=tests), tmp_path=tmp_path)
    return predict.predict_task(pl.tasks[0], predict.load_models(), coef, plan=pl)


def test_count_cases_per_language(tmp_path):
    def mk(name, text):
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        return p
    assert predict.count_cases(mk("a.py", "def test_a():\n    pass\n    async def test_b(self):\n        pass\ndef helper():\n    pass\n")) == 2
    assert predict.count_cases(mk("a.swift", "func testA() {\n}\n@Test func b() {\n}\n")) == 2
    assert predict.count_cases(mk("a.ts", 'it("a", () => {})\ntest.each([1])("b", () => {})\ndescribe("c", () => {})\n')) == 2
    assert predict.count_cases(mk("a.go", "func TestA(t *testing.T) {\n}\n")) == 1
    assert predict.count_cases(mk("a.rs", "#[test]\nfn a() {}\n#[test]\nfn b() {}\n")) == 2
    assert predict.count_cases(mk("a.md", "def test_a():\n")) == 0
    assert predict.count_cases(tmp_path / "missing.py") == 0


def test_suite_term_counts_existing_owned_cases(tmp_path):
    write_cases(tmp_path, 240)
    got = predict_one(tmp_path, live_coef(tmp_path))
    assert got["suite"] == {"files": ["tests/test_big.py"], "cases": 240, "case_s": 0.5, "run_min": 2.0, "extra_min": 3.0}
    assert got["extra_min"] == 3.0
    assert got["est_time_min"] == pytest.approx(6.204, abs=0.001)
    assert got["test_min"] == pytest.approx(4.5)


def test_suite_term_absent_for_new_or_small_suites(tmp_path):
    got = predict_one(tmp_path, live_coef(tmp_path))
    assert "suite" not in got and "extra_min" not in got
    assert got["est_time_min"] == pytest.approx(3.204, abs=0.001)
    write_cases(tmp_path, 60)
    got = predict_one(tmp_path, live_coef(tmp_path))
    assert "suite" not in got and "extra_min" not in got
    assert got["est_time_min"] == pytest.approx(3.204, abs=0.001)


def test_suite_term_reads_cmd_tokens(tmp_path):
    write_cases(tmp_path, 0, names=["test_alpha_1", "test_alpha_2", "test_beta", "test_gamma"])
    coef = live_coef(tmp_path, case_s=60)
    got = predict_one(tmp_path, coef, tests='fast cmd=python -m pytest tests/test_big.py -k "alpha or beta"', owns="src/big.py")
    assert got["suite"]["cases"] == 3
    got = predict_one(tmp_path, coef, tests="fast cmd=python -m pytest tests/test_big.py::test_gamma tests/test_big.py::test_beta", owns="src/big.py")
    assert got["suite"]["cases"] == 2
    got = predict_one(tmp_path, coef, tests='fast cmd=python -m pytest "tests/test_big.py', owns="src/big.py")
    assert "suite" not in got


def test_suite_term_off_without_live(tmp_path):
    write_cases(tmp_path, 240)
    got = predict_one(tmp_path, shipped())
    assert "suite" not in got
    assert got["est_time_min"] == pytest.approx(1.704, abs=0.001)


def test_ledger_case_seconds(tmp_path):
    lines = ["- tests fast passed=100 failed=0 skipped=0 seconds=50.0"] * 3
    lines += ["- tests fast passed=5 failed=0 skipped=0 seconds=9.0", "- tests full passed=900 failed=0 skipped=0 seconds=90.0"]
    led = tmp_path / ".superlite" / "progress.md"
    led.parent.mkdir()
    led.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert predict.ledger_case_seconds([led]) == [0.5, 0.5, 0.5]
    t = predict._read_live(tmp_path, shipped())["tests"]
    assert (t["case_s"], t["case_source"]) == (0.5, "history")
    led.write_text("", encoding="utf-8")
    t = predict._read_live(tmp_path, shipped())["tests"]
    assert (t["case_s"], t["case_source"]) == (0.2, "prior")


def flagged_plan(tmp_path, owns="src/auth/login.py", head=""):
    return plan_of(FOCUS, head, block(owns=owns), tmp_path=tmp_path)


def test_review_rounds_for_flagged_package(tmp_path):
    models, coef = predict.load_models(), shipped()
    pl = flagged_plan(tmp_path)
    plain = predict.predict_task(pl.tasks[0], models, coef)
    got = predict.predict_task(pl.tasks[0], models, coef, plan=pl)
    assert plain["est_time_min"] == pytest.approx(1.704, abs=0.001)
    assert not {"extra_min", "review", "suite"} & set(plain)
    feats, _ = predict.task_features(pl.tasks[0], coef)
    u = round(2 * predict.cost_from(feats, got["est_context"], "opus", models, coef)["usd"]["total"], 6)
    assert got["est_time_min"] == pytest.approx(6.704, abs=0.001)
    assert got["extra_min"] == 5.0
    assert got["review"] == {"why": ["Review Focus auth: security"], "rounds": 2.0, "model": "opus", "min": 5.0, "usd": u}
    assert got["cost"]["review"] == u
    assert got["cost"]["total"] == round(plain["cost"]["total"] + u, 6)
    other = flagged_plan(tmp_path, owns="src/billing/pay.py")
    assert "review" not in predict.predict_task(other.tasks[0], models, coef, plan=other)
    sect = flagged_plan(tmp_path, owns="lib/x.py", head="## Package: auth (login)\n")
    assert predict.predict_task(sect.tasks[0], models, coef, plan=sect)["review"]["why"] == ["Review Focus auth: security"]
    off = dict(coef, review={"rounds": 0})
    assert "review" not in predict.predict_task(pl.tasks[0], models, off, plan=pl)


def test_predict_plan_totals_include_review(tmp_path):
    models, coef = predict.load_models(), shipped()
    pl = plan_of(FOCUS, block("T1", owns="src/auth/login.py"), block("T2", owns="src/plain.py"), tmp_path=tmp_path)
    out = predict.predict_plan(pl, models, coef)
    t1, t2 = out["tasks"]["T1"], out["tasks"]["T2"]
    assert out["totals"]["cost_usd"]["total"] == round(t1["cost"]["total"] + t2["cost"]["total"], 6)
    assert out["totals"]["cost_usd"]["review"] == t1["review"]["usd"]
    solo = plan_of(block("T2", owns="src/plain.py"), tmp_path=tmp_path)
    assert "review" not in predict.predict_plan(solo, models, coef)["totals"]["cost_usd"]


def test_review_term_survives_bad_review_config(tmp_path):
    models, coef = predict.load_models(), shipped()
    pl = flagged_plan(tmp_path)
    bad = dict(coef, review={"cost_factor": "x", "round_min": "y"})
    got = predict.predict_task(pl.tasks[0], models, bad, plan=pl)
    assert "review" not in got and "extra_min" not in got
    assert got["est_time_min"] == pytest.approx(1.704, abs=0.001)


def test_suite_cmd_naming_no_file_falls_back_to_owned_tests(tmp_path):
    write_cases(tmp_path, 240)
    got = predict_one(tmp_path, live_coef(tmp_path), tests="fast cmd=python -m pytest tests/")
    assert got["suite"]["files"] == ["tests/test_big.py"]
    assert got["suite"]["cases"] == 240


def test_suite_negated_k_counts_whole_file(tmp_path):
    write_cases(tmp_path, 0, names=["test_alpha_1", "test_alpha_2", "test_beta", "test_gamma"])
    got = predict_one(tmp_path, live_coef(tmp_path, case_s=60), tests='fast cmd=python -m pytest tests/test_big.py -k "not alpha"', owns="src/big.py")
    assert got["suite"]["cases"] == 4


def test_suite_cmd_naming_non_test_file_falls_back_to_owned_tests(tmp_path):
    write_cases(tmp_path, 240)
    (tmp_path / "manage.py").write_text("def main():\n    pass\n", encoding="utf-8")
    got = predict_one(tmp_path, live_coef(tmp_path), tests="fast cmd=python manage.py test")
    assert got["suite"]["files"] == ["tests/test_big.py"]
    assert got["suite"]["cases"] == 240
