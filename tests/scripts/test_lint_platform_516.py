"""#516 platform_notes: Swift code behind #if os(...) needs a second platform build."""
from __future__ import annotations

import json

from test_plan_tools import SCRIPTS, pt, run

import plan_tools as ptm  # noqa: E402

DEST = "xcodebuild build -destination 'generic/platform=iOS'"
SWIFT = "Sources/App/Haptics.swift"
IOS = ["import Foundation", "#if os(iOS)", "import UIKit", "#endif"]


def plan(tmp_path, owns=f"{SWIFT}, Tests/AppTests/HapticsTests.swift", tests="fast", extra="", status=None, text=""):
    lines = ["### T1 haptics · Complexity 3 · Est. context 30k", f"**Owns:** {owns}", "**Components:** 1",
             "**LOC owned:** 100", f"**Tests:** {tests}"]
    if status:
        lines.append(f"**Status:** {status}")
    if extra:
        lines.append(f"**Steps:** {extra}")
    body = "\n".join(lines) + "\n\n" + text + "\n"
    p = tmp_path / "plan.md"
    p.write_text("# Plan\n**Goal:** x.\n**Tech stack:** Swift\n\n```mermaid\n%% taskgraph\nflowchart LR\n  T1\n```\n\n" + body,
                 encoding="utf-8")
    return p


def src(tmp_path, lines, rel=SWIFT):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")


def notes(p, root):
    return ptm.platform_notes(ptm.Plan.load(p), root)


def test_owned_swift_file_with_if_os_warns(tmp_path):
    src(tmp_path, IOS)
    assert notes(plan(tmp_path), tmp_path) == [
        "WARNING: PLATFORM: T1 has code behind #if os(iOS) (Sources/App/Haptics.swift); a build for the host platform skips it: "
        "put that platform's build in the task's steps (e.g. xcodebuild build -destination 'generic/platform=iOS') and set **Tests:** slow"]


def test_condition_in_task_text_warns(tmp_path):
    p = plan(tmp_path, text="```swift\n#elseif canImport( AppKit )\nimport AppKit\n```")
    out = notes(p, tmp_path)
    assert len(out) == 1 and "#if canImport(AppKit)" in out[0] and "(task text)" in out[0]


def test_several_conditions_listed_once_in_order(tmp_path):
    src(tmp_path, ["#if os(iOS) || os(tvOS)", "#endif", "#if targetEnvironment(simulator)", "#endif",
                   "  #if os(iOS)", "#endif", "#if os(watchOS)", "#endif"])
    out = notes(plan(tmp_path), tmp_path)
    assert len(out) == 1 and "#if os(iOS), os(tvOS), targetEnvironment(simulator) +1 more (" in out[0]


def test_plain_if_debug_does_not_warn(tmp_path):
    src(tmp_path, ["#if DEBUG", "#endif"])
    assert notes(plan(tmp_path), tmp_path) == []


def test_slow_task_with_destination_build_is_silent(tmp_path):
    src(tmp_path, IOS)
    assert notes(plan(tmp_path, tests="slow", extra=DEST), tmp_path) == []
    assert len(notes(plan(tmp_path, tests="slow"), tmp_path)) == 1


def test_draft_task_is_skipped(tmp_path):
    src(tmp_path, IOS)
    assert notes(plan(tmp_path, status="draft"), tmp_path) == []


def test_missing_or_unreadable_file_is_skipped(tmp_path):
    (tmp_path / "Sources" / "Dir").mkdir(parents=True)
    p = plan(tmp_path, owns="Sources/App/Missing.swift, Sources/Dir.swift")
    (tmp_path / "Sources" / "Dir.swift").mkdir()
    assert notes(p, tmp_path) == []
    src(tmp_path, IOS)
    assert notes(plan(tmp_path), None) == []


def test_lint_prints_platform_warning_and_task_stays_stable(tmp_path):
    src(tmp_path, IOS)
    p = plan(tmp_path)
    cp = pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    assert "WARNING: PLATFORM: T1 has code behind #if os(iOS)" in cp.out, cp.both
    d = json.loads((tmp_path / ".superlite" / "stable.json").read_text(encoding="utf-8"))
    assert "T1" in d["stable"]
