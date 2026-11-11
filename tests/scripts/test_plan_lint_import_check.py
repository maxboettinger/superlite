"""Plan lint import check gaps (#457): acyclic_siblings, custom contracts, no tomllib, tsconfig."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("plan_tools", SCRIPTS / "plan_tools.py")
plan_tools = importlib.util.module_from_spec(_spec)
sys.modules["plan_tools"] = plan_tools
_spec.loader.exec_module(plan_tools)

PLAN = '''# Plan
**Goal:** test.

### T1 producer · Complexity 3 (O-1) · Est. context 40k
**Owns:** {t1}
**Produces:** {item}
**Consumes:** none

### T2 consumer · Complexity 3 (O-1) · Est. context 40k
**Owns:** {t2}
**Produces:** Model()
**Consumes:** {item} (T1)
'''
PY_ITEM = "load(order: Order) -> Receipt"
ACYCLIC = "[importlinter]\nroot_package = shop\n\n[importlinter:contract:acyc]\nname = Acyclic\ntype = acyclic_siblings\nancestors = shop\n"
CUSTOM = "[importlinter]\nroot_package = shop\ncontract_types =\n    no_print: shop_lint.NoPrint\n\n[importlinter:contract:np]\nname = No print\ntype = no_print\n"
PYPROJECT = '[tool.importlinter]\nroot_package = "shop"\n\n[[tool.importlinter.contracts]]\nname = "Layers"\ntype = "layers"\nlayers = ["shop.a", "shop.b"]\n'
WARN = ('WARNING: IMPORT: T2 consumes load(order: Order) -> Receipt from T1, but load is declared in shop.a.x, '
        'which shop.b.y may not import (import-linter contract ')


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def plan_in(root: Path, t1: str, t2: str, item: str = PY_ITEM):
    write(root / "plan.md", PLAN.format(t1=t1, t2=t2, item=item))
    return plan_tools.Plan.load(str(root / "plan.md"))


def shop(root: Path, a_x: str = "from shop.b import y\n", b_y: str = "") -> None:
    for f in ("shop/__init__.py", "shop/a/__init__.py", "shop/b/__init__.py"):
        write(root / f, "")
    write(root / "shop/a/x.py", a_x)
    write(root / "shop/b/y.py", b_y)


def test_import_graph_resolves_absolute_relative_and_names(tmp_path):
    shop(tmp_path, a_x="from shop.b import y\nimport shop.c\n", b_y="from ..a import x\nfrom . import helpers\nimport os\n")
    write(tmp_path / "shop/b/helpers.py", "from .y import thing\n")
    write(tmp_path / "shop/c.py", "def f():\n    from shop.a.x import load\n")
    write(tmp_path / "shop/broken.py", "def (:\n")
    g = plan_tools.py_import_graph(tmp_path, ["shop"])
    assert g["shop.a.x"] == {"shop.b.y", "shop.c"}
    assert g["shop.b.y"] == {"shop.a.x", "shop.b.helpers"}
    assert g["shop.b.helpers"] == {"shop.b.y"}
    assert g["shop.c"] == {"shop.a.x"}
    assert g["shop"] == set() and g["shop.a"] == set()
    assert "shop.broken" not in g


def test_import_graph_src_layout(tmp_path):
    write(tmp_path / "src/shop/__init__.py", "")
    write(tmp_path / "src/shop/a.py", "from shop import b\n")
    write(tmp_path / "src/shop/b.py", "")
    assert plan_tools.py_import_graph(tmp_path, ["shop"]) == {"shop": set(), "shop.a": {"shop.b"}, "shop.b": set()}


def test_sibling_cycle_values():
    c = {"type": "acyclic_siblings", "name": "A", "ancestors": ["shop"]}
    g = {"shop.a.x": {"shop.b.y"}, "shop.b.y": set()}
    f = plan_tools.sibling_cycle
    assert f(c, "shop.b.y", "shop.a.x", g) == ["shop.b", "shop.a", "shop.b"]
    assert f(c, "shop.a.x", "shop.b.y", g) is None
    assert f(c, "shop.a.x", "shop.a.z", g) is None
    assert f(c, "shop.b.y", "other.a", g) is None
    assert f(c, "shop.a", "shop.a.x", g) is None
    g3 = {"shop.a.x": {"shop.b.y"}, "shop.b.y": {"shop.c.z"}, "shop.c.z": set()}
    assert f(c, "shop.c.z", "shop.a.x", g3) == ["shop.c", "shop.a", "shop.b", "shop.c"]


def test_sibling_cycle_depth_skip_and_ignore():
    g = {"shop.p.a.x": {"shop.p.b.y"}}
    f = plan_tools.sibling_cycle
    base = {"type": "acyclic_siblings", "ancestors": ["shop"]}
    cyc = ["shop.p.b", "shop.p.a", "shop.p.b"]
    assert f(base, "shop.p.b.y", "shop.p.a.x", g) == cyc
    assert f({**base, "depth": 0}, "shop.p.b.y", "shop.p.a.x", g) is None
    assert f({**base, "depth": 1}, "shop.p.b.y", "shop.p.a.x", g) == cyc
    assert f({**base, "depth": "x"}, "shop.p.b.y", "shop.p.a.x", g) == cyc
    assert f({**base, "skip_descendants": ["shop.p"]}, "shop.p.b.y", "shop.p.a.x", g) is None
    assert f({**base, "skip_descendants": ["shop.*"]}, "shop.p.b.y", "shop.p.a.x", g) is None
    assert f({**base, "ancestors": ["shop.*"]}, "shop.p.b.y", "shop.p.a.x", g) == cyc
    assert f({**base, "ancestors": ["other"]}, "shop.p.b.y", "shop.p.a.x", g) is None
    assert f({**base, "ignore_imports": ["shop.p.a.x -> shop.p.b.y"]}, "shop.p.b.y", "shop.p.a.x", g) is None
    assert f({**base, "ignore_imports": ["shop.p.a.* -> shop.p.b.*"]}, "shop.p.b.y", "shop.p.a.x", g) is None


def test_contract_blocks_acyclic_needs_graph():
    c = {"type": "acyclic_siblings", "ancestors": ["shop"]}
    g = {"shop.a.x": {"shop.b.y"}}
    assert plan_tools.contract_blocks(c, "shop.b.y", "shop.a.x", g) is True
    assert plan_tools.contract_blocks(c, "shop.b.y", "shop.a.x") is False
    assert plan_tools.contract_blocks({**c, "ignore_imports": ["shop.b.y -> shop.a.x"]}, "shop.b.y", "shop.a.x", g) is False


def test_config_reads_acyclic_options(tmp_path):
    write(tmp_path / ".importlinter", ACYCLIC + "depth = 3\nskip_descendants =\n    shop.p\n")
    c = plan_tools.importlinter_config(tmp_path)["contracts"][0]
    assert c["type"] == "acyclic_siblings" and c["ancestors"] == ["shop"]
    assert c["depth"] == 3 and c["skip_descendants"] == ["shop.p"]
    write(tmp_path / ".importlinter", ACYCLIC + "depth = deep\n")
    assert plan_tools.importlinter_config(tmp_path)["contracts"][0]["depth"] == 10
    write(tmp_path / ".importlinter", ACYCLIC)
    assert "depth" not in plan_tools.importlinter_config(tmp_path)["contracts"][0]


def test_acyclic_seam_warns(tmp_path):
    write(tmp_path / ".importlinter", ACYCLIC)
    shop(tmp_path)
    out = plan_tools.import_issues(plan_in(tmp_path, "shop/a/x.py", "shop/b/y.py"), tmp_path)
    assert out == [WARN + '"Acyclic" in .importlinter; cycle shop.b -> shop.a -> shop.b)']


def test_acyclic_no_cycle_silent(tmp_path):
    write(tmp_path / ".importlinter", ACYCLIC)
    shop(tmp_path, a_x="")
    assert plan_tools.import_issues(plan_in(tmp_path, "shop/a/x.py", "shop/b/y.py"), tmp_path) == []


def test_custom_contract_note(tmp_path):
    write(tmp_path / ".importlinter", CUSTOM)
    out = plan_tools.import_issues(plan_in(tmp_path, "shop/a/x.py", "shop/b/y.py"), tmp_path)
    assert out == ['NOTE: IMPORT: import-linter contract "No print" in .importlinter has type no_print, which plan lint does not check']


def test_custom_contract_note_before_warnings(tmp_path):
    write(tmp_path / ".importlinter", CUSTOM + "\n[importlinter:contract:lay]\nname = Layers\ntype = layers\nlayers =\n    shop.a\n    shop.b\n")
    out = plan_tools.import_issues(plan_in(tmp_path, "shop/a/x.py", "shop/b/y.py"), tmp_path)
    assert out == ['NOTE: IMPORT: import-linter contract "No print" in .importlinter has type no_print, which plan lint does not check',
                   WARN + '"Layers" in .importlinter)']


def test_custom_contract_note_needs_python_consumer(tmp_path):
    write(tmp_path / ".importlinter", CUSTOM)
    assert plan_tools.import_issues(plan_in(tmp_path, "web/a.ts", "web/b.ts"), tmp_path) == []


def test_no_tomllib_note(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tomllib", None)
    write(tmp_path / "pyproject.toml", PYPROJECT)
    v = f"{sys.version_info[0]}.{sys.version_info[1]}"
    assert plan_tools.importlinter_config(tmp_path) == {"file": "pyproject.toml", "roots": [], "contracts": [],
                                                       "skipped": f"Python {v} has no tomllib"}
    out = plan_tools.import_issues(plan_in(tmp_path, "shop/a/x.py", "shop/b/y.py"), tmp_path)
    assert out == [f"NOTE: IMPORT: pyproject.toml [tool.importlinter] not read (Python {v} has no tomllib); "
                   "the import-linter seam check is skipped (Python 3.11+ reads it)"]


def test_no_tomllib_quiet_cases(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tomllib", None)
    write(tmp_path / "pyproject.toml", "[project]\nname = 'x'\n")
    assert plan_tools.importlinter_config(tmp_path) is None
    write(tmp_path / "pyproject.toml", PYPROJECT)
    assert plan_tools.import_issues(plan_in(tmp_path, "web/a.ts", "web/b.ts"), tmp_path) == []
    write(tmp_path / ".importlinter", "[importlinter]\nroot_package = shop\n")
    assert plan_tools.importlinter_config(tmp_path) == {"file": ".importlinter", "roots": ["shop"], "contracts": []}


def test_layers_text_unchanged_with_tomllib(tmp_path):
    write(tmp_path / "pyproject.toml", PYPROJECT)
    out = plan_tools.import_issues(plan_in(tmp_path, "shop/a/x.py", "shop/b/y.py"), tmp_path)
    assert out == [WARN + '"Layers" in pyproject.toml)']
