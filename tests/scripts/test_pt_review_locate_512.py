"""#512: a Produces name resolves to the module the owning task owns before any same-named package module."""
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

NOTE = ("note: part1: T1 Produces registry.register: registry matches "
        "src/proj/a/registry.py, src/proj/b/registry.py; write the full module path")


def write(root: Path, rel: str, text: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def base(root: Path) -> None:
    write(root, "src/proj/__init__.py", "")
    write(root, "src/proj/sub/__init__.py", "")


def make_plan(root: Path, owns: str, produces: str, consumer: bool = False) -> Path:
    t2 = ""
    edge = ""
    if consumer:
        edge = "T1 --> T2\n"
        t2 = ("### T2 use · Complexity 2\n**Owns:** src/proj/use.py\n"
              "**Consumes:** registry.register(name: str) -> None (T1)\n\n")
    (root / "plan.md").write_text(
        f"# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n{edge}```\n\n"
        f"### T1 reg · Complexity 3\n**Owns:** {owns}\n**Produces:** {produces}\n\n{t2}"
        "## Review Focus\n- reg: state\n", encoding="utf-8")
    return root / "plan.md"


def locate(root: Path, plan_path: Path):
    plan = pt_review.parse_plan(plan_path)
    items = pt_review.planned_items(plan, None)
    return pt_review.locate(root, plan, items[0])


def two_registries(root: Path, same: bool) -> None:
    base(root)
    write(root, "src/proj/a/__init__.py", "")
    write(root, "src/proj/b/__init__.py", "")
    write(root, "src/proj/a/registry.py", "def register(name: str) -> None: pass\n")
    write(root, "src/proj/b/registry.py",
          "def register(a, b): pass\n" if same else "def other(): pass\n")


def run_contract(root: Path, *extra: str, capsys) -> tuple[int, str]:
    rc = pt_review.main(["contract", "--plan", str(root / "plan.md"), "--root", str(root), *extra])
    return rc, capsys.readouterr().out


def split_registry(root: Path) -> None:
    base(root)
    write(root, "src/proj/registry.py", "def register(a, b): pass\n")
    write(root, "src/proj/sub/registry.py", "def register(name: str) -> None: pass\n")


def test_owned_module_wins_over_same_named_package_module(tmp_path, capsys):
    split_registry(tmp_path)
    p = make_plan(tmp_path, "src/proj/sub/registry.py, tests/test_registry.py",
                  "registry.register(name: str) -> None")
    assert locate(tmp_path, p) == ("proj.sub.registry", ["register"], tmp_path / "src/proj/sub/registry.py")
    rc, out = run_contract(tmp_path, capsys=capsys)
    assert rc == 0 and "PASS: verified: contract" in out


def test_owned_suffix_of_two_parts(tmp_path):
    split_registry(tmp_path)
    p = make_plan(tmp_path, "src/proj/sub/registry.py", "sub.registry.register(name: str) -> None")
    assert locate(tmp_path, p)[0] == "proj.sub.registry"


def test_full_module_path_still_resolves(tmp_path, capsys):
    split_registry(tmp_path)
    p = make_plan(tmp_path, "src/proj/sub/registry.py", "proj.sub.registry.register(name: str) -> None")
    assert locate(tmp_path, p)[0] == "proj.sub.registry"
    rc, out = run_contract(tmp_path, capsys=capsys)
    assert rc == 0


def test_two_owned_modules_pick_the_one_that_defines_the_name(tmp_path):
    two_registries(tmp_path, same=False)
    p = make_plan(tmp_path, "src/proj/a/registry.py, src/proj/b/registry.py",
                  "registry.register(name: str) -> None")
    assert locate(tmp_path, p)[0] == "proj.a.registry"


def test_ambiguous_owned_modules_note_instead_of_mismatch(tmp_path, capsys):
    two_registries(tmp_path, same=True)
    p = make_plan(tmp_path, "src/proj/a/registry.py, src/proj/b/registry.py",
                  "registry.register(name: str) -> None")
    rc, out = run_contract(tmp_path, capsys=capsys)
    assert rc == 0
    assert NOTE in out
    assert "Produces:" not in out
    mism, n = pt_review.check_interfaces(pt_review.parse_plan(p), tmp_path, None)
    assert mism == [] and n == 1


def test_ambiguous_note_in_seam_run(tmp_path, capsys):
    two_registries(tmp_path, same=True)
    make_plan(tmp_path, "src/proj/a/registry.py, src/proj/b/registry.py",
              "registry.register(name: str) -> None", consumer=True)
    rc, out = run_contract(tmp_path, "--seam", "T1,T2", capsys=capsys)
    assert NOTE in out


def test_unowned_name_keeps_old_resolution(tmp_path):
    base(tmp_path)
    write(tmp_path, "src/proj/registry.py", "def register(a, b): pass\n")
    write(tmp_path, "src/proj/sub/other.py", "def x(): pass\n")
    p = make_plan(tmp_path, "src/proj/sub/other.py", "registry.register(a, b) -> None")
    assert locate(tmp_path, p)[0] == "proj.registry"
