"""probe_run: `raises=` in a Probe entry names expected errors, generated files lint clean (#418), and --plan (#420)."""
from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
PROBE_RUN = SDD / "probes" / "probe_run.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pt = _load("pt_review_raises_418", SDD / "scripts" / "pt_review.py")
pr = _load("probe_run_raises_418", PROBE_RUN)

SOURCE = '''

class DomainError(Exception):
    pass


class BadInput(DomainError):
    pass


def parse(text):
    if text.isdigit():
        return int(text)
    if KEY_PREFIX and text.startswith(KEY_PREFIX):
        return {}["missing"]
    raise BadInput(text[:20])
'''


def project(tmp_path: Path, key_prefix: str | None = None) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text(f"KEY_PREFIX = {key_prefix!r}\n" + SOURCE, encoding="utf-8")
    return root


def plan_with(root: Path, entry: str) -> Path:
    p = root / "plan.md"
    p.write_text(f"# p\n\n**Probe entry:** {entry}\n", encoding="utf-8")
    return p


def build_adapter(root: Path, plan: Path) -> Path:
    assert pt.main(["adapter", "--plan", str(plan), "--root", str(root)]) == 0
    return root / ".superlite" / "probes" / "adapter.py"


def hand_adapter(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("from a import parse\n\n\ndef call(text):\n    return parse(text)\n", encoding="utf-8")
    return path


def probe_run(*args, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PROBE_RUN), *map(str, args)], capture_output=True, text=True,
                          timeout=300, cwd=cwd)


def results(root: Path) -> dict:
    return json.loads((root / ".superlite" / "probes" / "probe-results.json").read_text(encoding="utf-8"))


def unused_imports(text: str) -> list[str]:
    """Top-level imports never used by name (what ruff F401 reports); stdlib only."""
    tree = ast.parse(text)
    bound = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                bound[(a.asname or a.name).split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for a in node.names:
                bound[a.asname or a.name] = a.name
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    return sorted(k for k in bound if k not in used)


def pytest_file(root: Path, test: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test], cwd=root,
                          capture_output=True, text=True)


def test_plan_raises_reads_every_probe_entry(tmp_path):
    plan = plan_with(tmp_path, "call=a.parse · raises=`BadInput`, a.Other · run=python -m a")
    assert pr.plan_raises(plan) == ["BadInput", "a.Other"]
    plan.write_text("# p\n\n**Probe entry:** call=a.parse · raises=X\n\n**Probe entry:** call=b.f · Raises=Y X\n",
                    encoding="utf-8")
    assert pr.plan_raises(plan) == ["X", "Y"]
    assert pr.plan_raises(plan_with(tmp_path, "call=a.parse")) == []
    assert pr.plan_raises(tmp_path / "missing.md") == []


def test_named_raise_matches_bases_and_dotted_names():
    ns = {"__name__": "a"}
    exec("class DomainError(Exception):\n    pass\n\n\nclass BadInput(DomainError):\n    pass\n", ns)
    e = ns["BadInput"]("x")
    for names in (["BadInput"], ["DomainError"], ["a.BadInput"], ["a.DomainError"], ["Other", "BadInput"]):
        assert pr.named_raise(e, names), names
    for names in ([], ["Other"], ["b.BadInput"], ["Bad"]):
        assert not pr.named_raise(e, names), names
    assert not pr.named_raise(KeyError("k"), ["BadInput"])


def test_adapter_consts_reads_the_generated_constants(tmp_path):
    root = project(tmp_path)
    plan = plan_with(root, "call=a.parse · raises=BadInput")
    consts = pr.adapter_consts(build_adapter(root, plan))
    assert consts["PLAN"] == str(plan.resolve()) and consts["ENTRIES"] == [{"package": "a", "call": "a.parse"}]
    assert pr.adapter_consts(hand_adapter(root / "hand.py")) == {}
    assert pr.adapter_consts(root / "missing.py") == {}


def test_raises_turns_a_domain_error_into_a_rejection(tmp_path):
    root = project(tmp_path)
    adapter = build_adapter(root, plan_with(root, "call=a.parse · raises=BadInput"))
    p = probe_run("--adapter", adapter, "--root", root, "--categories", "deep")
    res = results(root)
    assert p.returncode == 0, p.stdout + p.stderr
    assert res["raises"] == ["BadInput"] and res["failures"] == []
    assert {x["status"] for x in res["probes"]} == {"pass"}
    assert not (root / "tests" / "regression").exists()


def test_without_raises_the_domain_error_stays_a_crash(tmp_path):
    root = project(tmp_path)
    adapter = build_adapter(root, plan_with(root, "call=a.parse"))
    p = probe_run("--adapter", adapter, "--root", root, "--categories", "deep")
    res = results(root)
    assert p.returncode == 1 and res["raises"] == []
    assert {g["exc"] for g in res["failures"]} == {"BadInput"}


@pytest.mark.parametrize("name", ["DomainError", "a.BadInput"])
def test_raises_matches_a_base_class_or_a_dotted_name(tmp_path, name):
    root = project(tmp_path)
    adapter = build_adapter(root, plan_with(root, f"call=a.parse · raises={name}"))
    p = probe_run("--adapter", adapter, "--root", root, "--categories", "deep")
    assert p.returncode == 0 and results(root)["failures"] == [], p.stdout + p.stderr


def test_raises_flag_serves_a_hand_written_adapter(tmp_path):
    root = project(tmp_path)
    adapter = hand_adapter(root / "adapter.py")
    p = probe_run("--adapter", adapter, "--root", root, "--categories", "deep", "--raises", "BadInput")
    assert p.returncode == 0, p.stdout + p.stderr
    assert results(root)["raises"] == ["BadInput"] and results(root)["failures"] == []


def test_real_crash_still_gets_a_lint_clean_regression_test(tmp_path):
    root = project(tmp_path, key_prefix="(")
    adapter = build_adapter(root, plan_with(root, "call=a.parse · raises=BadInput"))
    probe_run("--adapter", adapter, "--root", root, "--categories", "deep")
    failures = results(root)["failures"]
    assert [g["exc"] for g in failures] == ["KeyError"], failures
    test = root / failures[0]["regression_test"]
    text = test.read_text(encoding="utf-8")
    assert "RAISES = ('BadInput',)" in text and unused_imports(text) == []
    copy = test.parent / "_probe_adapter.py"
    assert copy.read_text(encoding="utf-8").startswith("# ruff: noqa\n# flake8: noqa\n")
    ruff = shutil.which("ruff")
    if ruff:
        lint = subprocess.run([ruff, "check", "--isolated", "--no-cache", str(test), str(copy)],
                              capture_output=True, text=True)
        assert lint.returncode == 0, lint.stdout
    run = pytest_file(root, str(test))
    assert run.returncode == 1 and "KeyError" in run.stdout, run.stdout[-800:]


def test_generated_test_treats_named_errors_as_expected(tmp_path):
    root = project(tmp_path)
    adapter = build_adapter(root, plan_with(root, "call=a.parse · raises=BadInput"))
    cfg = pr.Cfg(root.resolve(), adapter.resolve(), None, 10.0)
    cfg.raises = ["BadInput"]
    group = {"category": "deep", "kind": "crash", "key": "k", "probe": "deep/call_x", "size": 1}
    rep = {"status": "crash", "input": "'x'",
           "probe_meta": {"entry": "call", "name": "n", "module": "/nonexistent.py"}}
    rel = pr._write_regression(cfg, group, rep)
    assert "RAISES = ('BadInput',)" in (root / rel).read_text(encoding="utf-8")
    run = pytest_file(root, rel)
    assert run.returncode == 0, run.stdout[-800:]


def test_plan_folder_sets_root_adapter_and_outputs(tmp_path):
    root = project(tmp_path)
    build_adapter(root, plan_with(root, "call=a.parse · raises=BadInput"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    p = probe_run("--plan", root / ".superlite", "--categories", "deep", cwd=elsewhere)
    assert p.returncode == 0, p.stdout + p.stderr
    res = results(root)
    assert Path(res["root"]) == root.resolve() and res["raises"] == ["BadInput"]
    assert (root / ".superlite" / "incidents.jsonl").is_file()
    assert not (elsewhere / ".superlite").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_plan_file_supplies_raises_for_a_hand_written_adapter(tmp_path):
    root = project(tmp_path)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    plan = plan_with(root, "call=a.parse · raises=BadInput")
    hand_adapter(root / ".superlite" / "probes" / "adapter.py")
    p = probe_run("--plan", plan, "--categories", "deep", cwd=tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert results(root)["raises"] == ["BadInput"] and results(root)["failures"] == []


def test_explicit_options_win_over_plan_defaults(tmp_path):
    root = project(tmp_path)
    build_adapter(root, plan_with(root, "call=a.parse · raises=BadInput"))
    out = tmp_path / "out.json"
    p = probe_run("--plan", root / ".superlite", "--out", out, "--categories", "deep", cwd=tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["raises"] == ["BadInput"]
    assert not (root / ".superlite" / "probes" / "probe-results.json").exists()


def test_plan_that_does_not_exist_is_a_usage_error(tmp_path):
    p = probe_run("--plan", tmp_path / "nope.md", "--categories", "deep", cwd=tmp_path)
    assert p.returncode == 2 and "probe_run: --plan not found:" in p.stderr
