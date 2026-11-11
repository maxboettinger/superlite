"""B93: writing-plans SKILL.md documents `**Edges:** hard`, the probe stack error and the platform warning."""
from __future__ import annotations

from pathlib import Path

TEXT = (Path(__file__).resolve().parents[2] / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")


def test_header_names_edges_hard():
    assert ("`**Edges:** hard` (every taskgraph edge is hard: prune and `EDGE:` keep them all, `EXAMPLE:` skips their "
            "consumers, and a consumer waits for its producer's commit even with Wave 0 stubs; use it when a consumer "
            "cannot compile without its producer, such as a Swift package's whole-package compile), ") in TEXT


def test_prune_paragraph_names_edges_hard():
    assert ("or list it in a `%% hard: T1->T2` line inside the taskgraph (or set `**Edges:** hard` in the plan header "
            "to make every edge hard)") in TEXT


def test_probe_entry_names_stack_error():
    assert ("`call=` and `serve=` import Python; lint fails `PROBE: call=<target> imports Python, but T2 owns no "
            "Python file (TypeScript)` (also for `serve=`, or `but the plan's stack is <languages>` when no Owns entry "
            "names a source file and the Tech stack line does) when the code it would import is not Python; "
            "other languages use `run=`") in TEXT


def test_tests_row_names_platform_warning():
    assert ("Swift code behind `#if os(...)`, `#if canImport(...)` or `#if targetEnvironment(...)` compiles only in "
            "that platform's build: lint prints `WARNING: PLATFORM: Tn has code behind ...` until the task is "
            "`Tests: slow` and its text names that build (`-destination`, `-sdk`, `--swift-sdk` or `--triple`).") in TEXT
