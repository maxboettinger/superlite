"""Tests for the import-linter seam check of plan_tools (#404)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("plan_tools", SCRIPTS / "plan_tools.py")
plan_tools = importlib.util.module_from_spec(_spec)
sys.modules["plan_tools"] = plan_tools
_spec.loader.exec_module(plan_tools)

PYPROJECT = '''[tool.importlinter]
root_package = "shop"

[[tool.importlinter.contracts]]
name = "Layers"
type = "layers"
layers = ["shop.web", "shop.core"]
'''

PLAN = '''# Plan
**Goal:** test.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 views · Complexity 3 (O-1) · Est. context 40k
**Owns:** {t1}
**Produces:** load(order: Order) -> Receipt
**Consumes:** none

### T2 models · Complexity 3 (O-1) · Est. context 40k
**Owns:** {t2}
**Produces:** Model()
**Consumes:** load(order: Order) -> Receipt (T1)
'''


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def plan_in(root: Path, t1: str = "shop/web/views.py", t2: str = "shop/core/models.py"):
    write(root / "plan.md", PLAN.format(t1=t1, t2=t2))
    return plan_tools.Plan.load(str(root / "plan.md"))


def lay(layers, containers=(), **kw):
    return {"type": "layers", "layers": list(layers), "containers": list(containers), "name": "L", **kw}


def test_layers_lower_may_not_import_higher():
    c = lay(["shop.web", "shop.core"])
    b = plan_tools.contract_blocks
    assert b(c, "shop.core.models", "shop.web.views") is True
    assert b(c, "shop.web.views", "shop.core.models") is False
    assert b(c, "shop.core.a", "shop.core.b") is False


def test_layers_siblings_and_containers():
    c = lay(["web", "api | cli", "core"], ["shop"])
    b = plan_tools.contract_blocks
    assert b(c, "shop.api.x", "shop.cli.y") is True
    c2 = lay(["web", "api : cli", "core"], ["shop"])
    assert b(c2, "shop.api.x", "shop.cli.y") is False
    c3 = lay(["(web)", "core"], ["shop"])
    assert b(c3, "shop.core.x", "shop.web.y") is True
    assert b(c, "other.api.x", "other.cli.y") is False
    assert b(c, "shop.api.x", "other.web.y") is False


def test_independence_forbidden_protected():
    b = plan_tools.contract_blocks
    ind = {"type": "independence", "modules": ["shop.a", "shop.b"]}
    assert b(ind, "shop.a.x", "shop.b.y") is True
    assert b(ind, "shop.a.x", "shop.a.z") is False
    fb = {"type": "forbidden", "source_modules": ["shop.core"], "forbidden_modules": ["shop.web"]}
    assert b(fb, "shop.core.m", "shop.web.v") is True
    assert b(fb, "shop.web.m", "shop.core.v") is False
    pr = {"type": "protected", "protected_modules": ["shop.db"], "allowed_importers": ["shop.repo"]}
    assert b(pr, "shop.web.v", "shop.db.s") is True
    assert b(pr, "shop.repo.r", "shop.db.s") is False
    assert b(pr, "shop.db.a", "shop.db.b") is False
    assert b({"type": "acyclic_siblings"}, "shop.a.x", "shop.b.y") is False


def test_wildcards_and_ignore():
    b = plan_tools.contract_blocks
    ind = {"type": "independence", "modules": ["shop.*"]}
    assert b(ind, "shop.a.x", "shop.b.y") is True
    assert plan_tools.module_within("shop.*.models", "shop.a.models.user") == "shop.a.models"
    assert plan_tools.module_within("shop.*", "shop.a.b") == "shop.a"
    assert plan_tools.module_within("shop.**", "shop.a.b") == "shop.a"
    assert plan_tools.module_within("shop.*.x", "shop.a.b.x") is None
    assert plan_tools.module_within("shop.**.x", "shop.a.b.x") == "shop.a.b.x"
    assert plan_tools.module_within("shop.core", "shop.core.x", as_packages=False) is None
    assert plan_tools.module_within("shop.core", "shop.core", as_packages=False) == "shop.core"
    c = lay(["shop.web", "shop.core"], ignore_imports=["shop.core.models -> shop.web.views"])
    assert b(c, "shop.core.models", "shop.web.views") is False
    assert b(c, "shop.core.other", "shop.web.views") is True


def test_config_ini_and_toml(tmp_path):
    write(tmp_path / "setup.cfg", '''[metadata]
name = x

[importlinter]
root_packages =
    shop
    billing

[importlinter:contract:one]
name = One
type = layers
layers =
    # top
    shop.web

    shop.core
containers = shop
as_packages = no
''')
    cfg = plan_tools.importlinter_config(tmp_path)
    assert cfg["file"] == "setup.cfg" and cfg["roots"] == ["shop", "billing"]
    assert cfg["contracts"] == [{"name": "One", "type": "layers", "layers": ["shop.web", "shop.core"],
                                 "containers": ["shop"], "ignore_imports": [], "as_packages": False}]
    (tmp_path / "setup.cfg").unlink()
    write(tmp_path / ".importlinter", "[importlinter]\nroot_package = shop\n[importlinter:contract:a]\ntype = forbidden\n"
          "source_modules = shop.a\nforbidden_modules = shop.b\n")
    cfg = plan_tools.importlinter_config(tmp_path)
    assert cfg["file"] == ".importlinter" and cfg["contracts"][0]["name"] == "a"
    assert cfg["contracts"][0]["source_modules"] == ["shop.a"]
    (tmp_path / ".importlinter").unlink()
    write(tmp_path / "setup.cfg", "[metadata]\nname = x\n")
    write(tmp_path / "pyproject.toml", PYPROJECT)
    cfg = plan_tools.importlinter_config(tmp_path)
    assert cfg == {"file": "pyproject.toml", "roots": ["shop"], "contracts": [
        {"name": "Layers", "type": "layers", "layers": ["shop.web", "shop.core"], "containers": [],
         "ignore_imports": [], "as_packages": True}]}
    write(tmp_path / "pyproject.toml", "[tool.importlinter\nbroken")
    assert plan_tools.importlinter_config(tmp_path) is None


def test_py_module_values():
    f = plan_tools.py_module
    assert f("src/shop/core/models.py", ["shop"]) == "shop.core.models"
    assert f("shop/__init__.py", ["shop"]) == "shop"
    assert f("tools/x.py", ["shop"]) is None
    assert f("src/shop/a/__init__.py", ["shop"]) == "shop.a"


def test_python_seam_warns(tmp_path):
    write(tmp_path / "pyproject.toml", PYPROJECT)
    out = plan_tools.import_issues(plan_in(tmp_path), tmp_path)
    assert out == ["WARNING: IMPORT: T2 consumes load(order: Order) -> Receipt from T1, but load is declared in "
                   "shop.web.views, which shop.core.models may not import (import-linter contract \"Layers\" in pyproject.toml)"]


def test_allowed_direction_silent(tmp_path):
    write(tmp_path / "pyproject.toml", PYPROJECT)
    plan = plan_in(tmp_path, "shop/core/models.py", "shop/web/views.py")
    assert plan_tools.import_issues(plan, tmp_path) == []


def test_no_config_silent(tmp_path):
    assert plan_tools.import_issues(plan_in(tmp_path), tmp_path) == []


def test_swift_388_unchanged(tmp_path):
    here = Path(__file__).parent
    spec = importlib.util.spec_from_file_location("t388", here / "test_plan_lint_imports_388.py")
    t388 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t388)
    root = t388.make(tmp_path)
    write(root / "pyproject.toml", "[tool.importlinter\nbroken")
    plan = plan_tools.Plan.load(str(root / "plan.md"))
    got = plan_tools.import_issues(plan, root)
    assert got == ["WARNING: IMPORT: T2 consumes FailedCardPreview(_ error: LakeError) from T1, but LakeError is declared in Lake, "
                   "which target AreaHealth may not import (Packages/Kit/Package.swift) dependencies: Core, Metrics, Dashboard, Charts"]
