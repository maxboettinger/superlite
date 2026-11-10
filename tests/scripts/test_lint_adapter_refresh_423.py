"""#423: lint rebuilds (--stable) or reports (plain) a probe adapter that no longer matches the plan's Probe entries."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

import plan_tools  # noqa: E402
import pt_review  # noqa: E402
from test_plan_tools import make_plan, pt  # noqa: E402

REL = ".superlite/probes/adapter.py"


def write_plan(root: Path, call: str, name: str = "plan.md") -> Path:
    p = root / name
    p.write_text(f"# p\n\n**Probe entry:** call={call}\n", encoding="utf-8")
    return p


def build(root: Path, plan: Path) -> Path:
    assert pt_review.main(["adapter", "--plan", str(plan), "--root", str(root)]) == 0
    return root / REL


def literal(path: Path, name: str):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def root_line(path: Path) -> str:
    return next(ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("ROOT = "))


def test_current_adapter_quiet(tmp_path):
    plan = write_plan(tmp_path, "a.parse")
    adapter = build(tmp_path, plan)
    before = adapter.read_text(encoding="utf-8")
    assert plan_tools.refresh_adapter(str(plan)) == ""
    assert adapter.read_text(encoding="utf-8") == before


def test_rebuilds_after_entry_change(tmp_path):
    plan = write_plan(tmp_path, "a.parse")
    adapter = build(tmp_path, plan)
    root_before = root_line(adapter)
    write_plan(tmp_path, "a.parse2")
    line = plan_tools.refresh_adapter(str(plan))
    assert line == f"ADAPTER: rebuilt {REL} (the plan's Probe entries changed)"
    assert literal(adapter, "ENTRIES") == pt_review.plan_entries(pt_review.parse_plan(plan))
    assert literal(adapter, "ENTRIES")[0]["call"] == "a.parse2"
    assert root_line(adapter) == root_before


def test_no_write_says_run(tmp_path):
    plan = write_plan(tmp_path, "a.parse")
    adapter = build(tmp_path, plan)
    before = adapter.read_text(encoding="utf-8")
    write_plan(tmp_path, "a.parse2")
    sl = (SCRIPTS / "sl").as_posix()
    line = plan_tools.refresh_adapter(str(plan), write=False)
    assert line == f"RUN: {sl} plan_tools adapter --plan {plan.resolve()} (the probe adapter is stale: the plan's Probe entries changed)"
    assert adapter.read_text(encoding="utf-8") == before


def test_removed_without_entries(tmp_path):
    plan = write_plan(tmp_path, "a.parse")
    adapter = build(tmp_path, plan)
    plan.write_text("# p\n\nno entries\n", encoding="utf-8")
    line = plan_tools.refresh_adapter(str(plan))
    assert line == f"ADAPTER: removed {REL} (the plan has no Probe entry lines)"
    assert not adapter.exists()


def test_hand_written_and_other_plan_left(tmp_path):
    plan = write_plan(tmp_path, "a.parse")
    adapter = build(tmp_path, plan)
    other = write_plan(tmp_path, "a.parse", "other.md")
    adapter.write_text("ENTRIES = []\nPLAN = %r\n" % str(plan.resolve()), encoding="utf-8")
    hand = adapter.read_text(encoding="utf-8")
    assert plan_tools.refresh_adapter(str(plan)) == ""
    assert adapter.read_text(encoding="utf-8") == hand
    adapter = build(tmp_path, other)
    write_plan(tmp_path, "a.parse2")
    mine = adapter.read_text(encoding="utf-8")
    assert plan_tools.refresh_adapter(str(plan)) == ""
    assert adapter.read_text(encoding="utf-8") == mine


def stale_project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def parse(text):\n    return text\n\n\ndef parse2(text):\n    return text\n", encoding="utf-8")
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/a.py, tests/test_a.py"}])
    text = plan.read_text(encoding="utf-8")
    plan.write_text(text + "\n**Probe entry:** call=a.parse\n", encoding="utf-8")
    adapter = build(tmp_path, plan)
    plan.write_text(text + "\n**Probe entry:** call=a.parse2\n", encoding="utf-8")
    return plan, adapter


def test_lint_stable_prints_rebuilt(tmp_path):
    plan, adapter = stale_project(tmp_path)
    cp = pt("lint", "--stable", "--plan", plan, cwd=tmp_path)
    assert f"ADAPTER: rebuilt {REL} (the plan's Probe entries changed)" in cp.out, cp.both
    assert literal(adapter, "ENTRIES")[0]["call"] == "a.parse2"


def test_plain_lint_prints_run(tmp_path):
    plan, adapter = stale_project(tmp_path)
    before = adapter.read_text(encoding="utf-8")
    base = pt("lint", "--plan", plan, cwd=tmp_path)
    assert f"RUN: {(SCRIPTS / 'sl').as_posix()} plan_tools adapter --plan {plan.resolve()} (the probe adapter is stale" in base.out, base.both
    assert adapter.read_text(encoding="utf-8") == before
    assert base.returncode in (0, 1)


def test_rebuild_recomputes_import_roots(tmp_path):
    plan = write_plan(tmp_path, "a.parse")
    adapter = build(tmp_path, plan)
    assert literal(adapter, "IMPORT_ROOTS") == []
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "a.py").write_text("def parse(t):\n    return t\n", encoding="utf-8")
    (tmp_path / ".superlite" / "test-cmd.json").write_text('{"pythonpath": ["lib"]}', encoding="utf-8")
    write_plan(tmp_path, "a.parse2")
    assert plan_tools.refresh_adapter(str(plan)).startswith("ADAPTER: rebuilt")
    assert literal(adapter, "IMPORT_ROOTS") == ["lib"]
