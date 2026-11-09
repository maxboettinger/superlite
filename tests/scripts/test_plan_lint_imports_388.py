"""Tests for plan_tools import_issues (#388): a seam type a consumer's SwiftPM target may not import."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
PLAN_TOOLS = SCRIPTS / "plan_tools.py"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("plan_tools", PLAN_TOOLS)
plan_tools = importlib.util.module_from_spec(_spec)
sys.modules["plan_tools"] = plan_tools
_spec.loader.exec_module(plan_tools)

MANIFEST = '''// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "Kit",
    targets: [
        .target(name: "Core"),
        .target(name: "Lake", dependencies: ["Core"]),
        .target(name: "Metrics", dependencies: ["Core", "Lake"]),
        .target(name: "Dashboard", dependencies: ["Core", "Lake", "Metrics"]),
        .target(
            name: "AreaHealth",
            dependencies: [
                "Core", "Metrics", "Dashboard", // not Lake
                .product(name: "Charts", package: "swift-charts"),
            ],
            swiftSettings: [.define("X")]
        ),
        .testTarget(name: "AreaHealthTests", dependencies: ["AreaHealth"]),
        .target(name: "Custom", path: "Custom/X"),
    ]
)
'''

PLAN = '''# Plan
**Goal:** test.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 dashboard card · Complexity 3 (O-1) · Est. context 40k
**Owns:** Packages/Kit/Sources/Dashboard/FailedCardPreview.swift
**Produces:** FailedCardPreview(_ error: LakeError)
**Consumes:** none

### T2 health card · Complexity 3 (O-1) · Est. context 40k
**Owns:** Packages/Kit/Sources/AreaHealth/HealthCard.swift
**Produces:** HealthCard()
**Consumes:** FailedCardPreview(_ error: LakeError) (T1)
'''

PLAN3 = '''# Plan
**Goal:** test.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 card · Complexity 3 (O-1) · Est. context 40k
**Owns:** Packages/Kit/Sources/Dashboard/Card.swift
**Produces:** card(score: HealthScore) -> Int
**Consumes:** none

### T2 health card · Complexity 3 (O-1) · Est. context 40k
**Owns:** Packages/Kit/Sources/AreaHealth/HealthCard.swift
**Produces:** HealthCard()
**Consumes:** card(score: HealthScore) -> Int (T1)

### T3 score · Complexity 3 (O-1) · Est. context 40k
**Owns:** Packages/Kit/Sources/Lake/HealthScore.swift
**Produces:** HealthScore
**Consumes:** none
'''


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make(tmp_path: Path, plan: str = PLAN, manifest: bool = True) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    if manifest:
        write(root / "Packages/Kit/Package.swift", MANIFEST)
    src = root / "Packages/Kit/Sources"
    write(src / "Lake/LakeError.swift", "// public enum Nope {}\npublic enum LakeError: Error { case down }\n")
    write(src / "Core/Period.swift", "public struct Period {}\n")
    write(root / "plan.md", plan)
    return root


def lint(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(PLAN_TOOLS), "lint", "--plan", str(root / "plan.md")],
                          capture_output=True, text=True, cwd=root, env=env, timeout=120)


def imports(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if "IMPORT:" in ln]


def test_signature_types_values():
    sig = plan_tools.parse_signature("FailedCardPreview(_ error: LakeError, at: [Period]) -> Card?")
    assert plan_tools.signature_types(sig) == ["LakeError", "Period", "Card"]
    assert plan_tools.signature_types(plan_tools.parse_signature("run(x: int) -> str")) == []


def test_manifest_with_nested_calls(tmp_path):
    root = make(tmp_path)
    t = plan_tools.swift_targets(root)
    assert t["AreaHealth"] == {"dir": root / "Packages/Kit/Sources/AreaHealth",
                               "deps": {"Core", "Metrics", "Dashboard", "Charts"},
                               "manifest": "Packages/Kit/Package.swift"}
    assert t["AreaHealthTests"]["dir"] == root / "Packages/Kit/Tests/AreaHealthTests"
    assert t["Custom"]["dir"] == root / "Packages/Kit/Custom/X"
    assert t["Lake"]["deps"] == {"Core"}


def test_consumer_target_without_dependency_warns(tmp_path):
    root = make(tmp_path)
    out = lint(root).stdout
    assert imports(out) == [
        "WARNING: IMPORT: T2 consumes FailedCardPreview(_ error: LakeError) from T1, but LakeError is declared in Lake, "
        "which target AreaHealth may not import (Packages/Kit/Package.swift) dependencies: Core, Metrics, Dashboard, Charts"]


def test_allowed_dependency_is_silent(tmp_path):
    root = make(tmp_path, PLAN.replace("AreaHealth/HealthCard.swift", "Dashboard/Other.swift"))
    assert imports(lint(root).stdout) == []


def test_typealias_in_allowed_module_is_silent(tmp_path):
    root = make(tmp_path)
    write(root / "Packages/Kit/Sources/Metrics/Aliases.swift", "public typealias LakeError = Lake.LakeError\n")
    assert imports(lint(root).stdout) == []


def test_type_produced_by_plan_task(tmp_path):
    root = make(tmp_path, PLAN3)
    got = imports(lint(root).stdout)
    assert len(got) == 1 and "HealthScore is declared in Lake" in got[0]


def test_no_package_swift_no_warning(tmp_path):
    root = make(tmp_path, PLAN3, manifest=False)
    assert imports(lint(root).stdout) == []


def test_warning_is_not_an_issue(tmp_path):
    root = make(tmp_path)
    plan = plan_tools.Plan.load(str(root / "plan.md"))
    args = plan_tools.build_parser().parse_args(["lint", "--plan", str(root / "plan.md")])
    issues, warnings = plan_tools.lint_plan(plan, args)
    assert not any("IMPORT" in str(i) for i in issues)
    assert any("IMPORT:" in w for w in warnings)
    stable, _fix, _pi = plan_tools.stable_partition(plan, issues, warnings)
    assert "T2" in stable
