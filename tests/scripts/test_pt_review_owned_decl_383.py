"""#383: the contract check searches every file the task owns, source files first, then owned test code."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

SWIFT_OWNS = "Sources/Kit/A.swift, Tests/KitTests/Support/FakeA.swift"


def write(root: Path, rel: str, text: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def make_plan(root: Path, owns: str, produces: str):
    (root / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n```\n\n"
        f"### T1 kit · Complexity 3\n**Owns:** {owns}\n**Produces:** {produces}\n\n## Review Focus\n- kit: state\n",
        encoding="utf-8")
    return pt_review.parse_plan(root / "plan.md")


def swift_root(tmp_path: Path) -> Path:
    write(tmp_path, "Sources/Kit/A.swift", "public struct A {}\n")
    write(tmp_path, "Tests/KitTests/Support/FakeA.swift", "final class FakeA {}\n")
    return tmp_path


def py_root(tmp_path: Path) -> Path:
    write(tmp_path, "src/pkg/core.py", "def run(x): return x\n")
    write(tmp_path, "tests/helpers.py", "def make_fake(n: int) -> list: return [0] * n\n")
    return tmp_path


def test_find_declaration_tests_flag(tmp_path):
    write(tmp_path, "Tests/T.swift", "struct Foo {}\n")
    assert pt_review.find_declaration(tmp_path, ["Tests/T.swift"], "Foo") is None
    assert pt_review.find_declaration(tmp_path, ["Tests/T.swift"], "Foo", tests=True) == ("Tests/T.swift", 1)


def test_test_owns_lists_owned_test_code(tmp_path):
    plan = make_plan(tmp_path, "Sources/Kit/A.swift, Tests/KitTests/Support/FakeA.swift, docs/a.md", "A")
    assert pt_review.test_owns(plan, "T1") == ["Tests/KitTests/Support/FakeA.swift"]


def test_swift_name_in_owned_test_helper_is_declared(tmp_path):
    root = swift_root(tmp_path)
    plan = make_plan(root, SWIFT_OWNS, "struct A · class FakeA")
    assert pt_review.check_interfaces(plan, root, None) == ([], 2)


def test_swift_name_missing_everywhere_names_every_owned_file(tmp_path):
    root = swift_root(tmp_path)
    plan = make_plan(root, SWIFT_OWNS, "struct Missing")
    out, _n = pt_review.check_interfaces(plan, root, None)
    assert len(out) == 1
    assert out[0].file == "Sources/Kit/A.swift"
    assert out[0].msg.endswith("`Missing` not declared in Sources/Kit/A.swift, Tests/KitTests/Support/FakeA.swift")


def test_python_name_in_owned_test_helper_located(tmp_path):
    root = py_root(tmp_path)
    plan = make_plan(root, "src/pkg/core.py, tests/helpers.py", "pkg.core.run(x) · make_fake(n: int) -> list")
    items = {p.parts[-1]: p for p in pt_review.planned_items(plan, None)}
    _mod, _chain, f = pt_review.locate(root, plan, items["make_fake"])
    assert f == root / "tests/helpers.py"
    out, _n = pt_review.check_interfaces(plan, root, None)
    assert not [m for m in out if "make_fake" in m.msg]


def test_python_source_still_wins(tmp_path):
    root = py_root(tmp_path)
    write(root, "tests/helpers.py", "def run(x): return x\n")
    plan = make_plan(root, "src/pkg/core.py, tests/helpers.py", "run(x)")
    p = pt_review.planned_items(plan, None)[0]
    _mod, _chain, f = pt_review.locate(root, plan, p)
    assert f == root / "src/pkg/core.py"
