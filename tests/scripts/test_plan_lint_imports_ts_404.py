"""Tests for the TypeScript workspace seam check of plan_tools (#404)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("plan_tools", SCRIPTS / "plan_tools.py")
plan_tools = importlib.util.module_from_spec(_spec)
sys.modules["plan_tools"] = plan_tools
_spec.loader.exec_module(plan_tools)

PLAN = '''# Plan
**Goal:** test.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 loader · Complexity 3 (O-1) · Est. context 40k
**Owns:** {t1}
**Produces:** loadOrder(id: string) -> Order
**Consumes:** none

### T2 page · Complexity 3 (O-1) · Est. context 40k
**Owns:** {t2}
**Produces:** Page()
**Consumes:** loadOrder(id: string) -> Order (T1)
'''


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def pkg(root: Path, rel: str, name: str, **deps) -> None:
    data = {"name": name}
    data.update(deps)
    write(root / rel / "package.json", json.dumps(data))


def plan_in(root: Path, t1="packages/core/src/order.ts", t2="packages/web/src/page.tsx"):
    write(root / "plan.md", PLAN.format(t1=t1, t2=t2))
    return plan_tools.Plan.load(str(root / "plan.md"))


def two(root: Path, web_deps=None, **extra):
    pkg(root, "packages/core", "@shop/core")
    pkg(root, "packages/web", "@shop/web", **(web_deps or {"dependencies": {"react": "18"}}))


def test_ts_packages_example(tmp_path):
    pkg(tmp_path, "packages/core", "@shop/core")
    pkg(tmp_path, "packages/web", "@shop/web", dependencies={"react": "18"})
    got = plan_tools.ts_packages(tmp_path)
    assert got["@shop/core"]["dir"] == tmp_path / "packages/core"
    assert got["@shop/core"]["deps"] == set()
    assert got["@shop/web"]["deps"] == {"react"}
    assert got["@shop/web"]["manifest"] == "packages/web/package.json"


def test_ts_seam_warns(tmp_path):
    two(tmp_path)
    plan = plan_in(tmp_path)
    assert plan_tools.ts_import_issues(plan, tmp_path) == [
        "WARNING: IMPORT: T2 consumes loadOrder(id: string) -> Order from T1, but loadOrder is declared in @shop/core, "
        "which package @shop/web may not import (packages/web/package.json) dependencies: react"]


def test_ts_no_deps_says_none(tmp_path):
    pkg(tmp_path, "packages/core", "@shop/core")
    pkg(tmp_path, "packages/web", "@shop/web")
    out = plan_tools.ts_import_issues(plan_in(tmp_path), tmp_path)
    assert out and out[0].endswith("dependencies: none")


def test_ts_declared_dependency_silent(tmp_path):
    two(tmp_path, {"devDependencies": {"@shop/core": "workspace:*"}})
    assert plan_tools.ts_import_issues(plan_in(tmp_path), tmp_path) == []


def test_ts_same_package_silent(tmp_path):
    two(tmp_path)
    plan = plan_in(tmp_path, t2="packages/core/src/page.tsx")
    assert plan_tools.ts_import_issues(plan, tmp_path) == []


def test_single_package_silent(tmp_path):
    pkg(tmp_path, "packages/core", "@shop/core")
    assert plan_tools.ts_packages(tmp_path) == {}
    assert plan_tools.ts_import_issues(plan_in(tmp_path), tmp_path) == []


def test_ts_skips_node_modules_and_bad_json(tmp_path):
    two(tmp_path)
    pkg(tmp_path, "node_modules/x", "x")
    write(tmp_path / "packages/bad/package.json", "{not json")
    write(tmp_path / "packages/noname/package.json", json.dumps({"version": "1"}))
    assert set(plan_tools.ts_packages(tmp_path)) == {"@shop/core", "@shop/web"}


def test_ts_type_declared_in_scan(tmp_path):
    two(tmp_path)
    write(tmp_path / "packages/core/src/order.ts", "export interface Order {}\n")
    plan = plan_in(tmp_path, t1="packages/util/src/load.ts")
    pkg(tmp_path, "packages/util", "@shop/util")
    out = plan_tools.ts_import_issues(plan, tmp_path)
    assert any("Order is declared in @shop/core" in w for w in out)


def test_ts_deepest_package_wins(tmp_path):
    pkg(tmp_path, ".", "shop")
    pkg(tmp_path, "packages/web", "@shop/web")
    pkg(tmp_path, "packages/core", "@shop/core")
    out = plan_tools.ts_import_issues(plan_in(tmp_path), tmp_path)
    assert out and "package @shop/web may not import" in out[0]


def test_import_issues_has_all_stacks(tmp_path):
    two(tmp_path)
    write(tmp_path / "pyproject.toml", '[tool.importlinter]\nroot_package = "shop"\n\n[[tool.importlinter.contracts]]\nname = "Layers"\ntype = "layers"\nlayers = ["shop.web", "shop.core"]\n')
    plan = plan_in(tmp_path)
    plan_tools.Plan  # noqa
    out = plan_tools.import_issues(plan, tmp_path)
    assert out and "@shop/web" in out[-1]
