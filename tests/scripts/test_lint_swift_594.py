"""#594: Swift lint ignores generic parameters as types and honours the project's test destinations."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from test_plan_lint_imports_388 import PLAN_TOOLS, imports, plan_tools, write

MANIFEST = '''// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "App",
    targets: [
        .target(name: "AppFeatures"),
        .target(name: "Agent"),
    ]
)
'''

PICKER = "WrappingMenuPicker.init(selection: Binding<String>, content: () -> Content)"


def plan_text(produces=PICKER):
    return f'''# Plan
**Goal:** test.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 picker · Complexity 3 (O-1) · Est. context 40k
**Owns:** Sources/AppFeatures/WrappingMenuPicker.swift
**Produces:** {produces}
**Consumes:** none

### T2 use · Complexity 3 (O-1) · Est. context 40k
**Owns:** Sources/Agent/Use.swift
**Produces:** Use()
**Consumes:** {produces} (T1)
'''


def make(tmp_path, picker="struct WrappingMenuPicker<Content: View>: View {\n}\n", produces=PICKER, extra=None):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    write(root / "Package.swift", MANIFEST)
    write(root / "Sources/AppFeatures/WrappingMenuPicker.swift", picker)
    write(root / "Sources/AppFeatures/Content.swift", "enum Content {}\n")
    for rel, body in (extra or {}).items():
        write(root / rel, body)
    write(root / "plan.md", plan_text(produces))
    return root


def lint(root):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(PLAN_TOOLS), "lint", "--plan", str(root / "plan.md")],
                          capture_output=True, text=True, cwd=root, env=env, timeout=120).stdout


def test_swift_generic_params_values():
    f = plan_tools.swift_generic_params
    assert f("struct WrappingMenuPicker<Content: View, Label>: View {") == {"Content", "Label"}
    assert f("    public init<T: Codable>(value: T) {") == {"T"}
    assert f("Box<Item>.init(item: Item)") == {"Item"}
    assert f(PICKER) == set()
    assert f("func f<each T>(_ x: repeat each T)") == {"T"}


def test_destination_conds_values():
    f = plan_tools.destination_conds
    assert f("platform=macOS") == {"os(macOS)", "canImport(AppKit)"}
    assert f("platform=iOS Simulator,name=iPhone 16") == {"os(iOS)", "targetEnvironment(simulator)", "canImport(UIKit)"}
    assert f("generic/platform=iOS") == {"os(iOS)", "canImport(UIKit)"}
    assert f("platform=macOS,variant=Mac Catalyst") == {"os(iOS)", "targetEnvironment(macCatalyst)", "canImport(UIKit)"}
    assert f("id=ABC") == set()
    assert "os(xrOS)" in f("platform=visionOS Simulator")
    assert "os(tvOS)" in f("platform=tvOS")


def test_generic_param_not_an_import(tmp_path):
    assert imports(lint(make(tmp_path))) == []


def test_real_type_still_warns(tmp_path):
    root = make(tmp_path, produces=PICKER + " -> CardModel", extra={"Sources/AppFeatures/Card.swift": "struct CardModel {}\n"})
    out = imports(lint(root))
    assert len(out) == 1 and "T2 consumes" in out[0] and "CardModel is declared in AppFeatures" in out[0]


def test_member_generic_skipped(tmp_path):
    root = make(tmp_path, picker="struct Plain {\n  init<Content>(x: Int) {}\n}\n")
    assert imports(lint(root)) == []


# destinations

SWIFT = "Sources/App/Haptics.swift"


def pplan(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text("# Plan\n**Goal:** x.\n**Tech stack:** Swift\n\n```mermaid\n%% taskgraph\nflowchart LR\n  T1\n```\n\n"
                 "### T1 haptics · Complexity 3 · Est. context 30k\n"
                 f"**Owns:** {SWIFT}\n**Components:** 1\n**LOC owned:** 100\n**Tests:** fast\n", encoding="utf-8")
    return p


def platform(tmp_path, cfg, conds):
    write(tmp_path / SWIFT, "\n".join(conds) + "\n")
    write(tmp_path / ".superlite/test-cmd.json", json.dumps(cfg))
    return plan_tools.platform_notes(plan_tools.Plan.load(pplan(tmp_path)), tmp_path)


def test_macos_destination_covers_os_macos(tmp_path):
    cfg = {"language": "swift", "test": "xcodebuild test -scheme App -destination 'platform=macOS'"}
    assert platform(tmp_path, cfg, ["#if os(macOS)", "#endif"]) == []


def test_destinations_key_covers(tmp_path):
    cfg = {"language": "swift", "test": "xcodebuild test -scheme App", "destinations": ["platform=iOS Simulator,name=iPhone 16"]}
    assert platform(tmp_path, cfg, ["#if os(iOS)", "#endif"]) == []


def test_uncovered_cond_still_named(tmp_path):
    cfg = {"language": "swift", "test": "xcodebuild test -scheme App -destination 'platform=macOS'"}
    out = platform(tmp_path, cfg, ["#if os(macOS)", "#elseif os(iOS)", "#endif"])
    assert len(out) == 1 and "os(iOS)" in out[0] and "os(macOS)" not in out[0]


def test_negated_cond_not_covered(tmp_path):
    cfg = {"language": "swift", "test": "xcodebuild test -scheme App -destination 'platform=macOS'"}
    assert len(platform(tmp_path, cfg, ["#if !os(macOS)", "#endif"])) == 1


def test_swift_test_covers_nothing(tmp_path):
    cfg = {"language": "swift", "test": "swift test"}
    assert len(platform(tmp_path, cfg, ["#if os(macOS)", "#endif"])) == 1
