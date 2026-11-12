"""docs/tools.md rows name the #614 tree build path and cleanup."""
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "tools.md"  # O(1)

SENTENCES = {  # O(1)
    "trees": "Cleanup (#574, #614): run_tests and dispatch refuse below 20 GB free and warn below 50 GB (SUPERLITE_DISK_FLOOR_GB, SUPERLITE_DISK_WARN_GB; 0 turns a check off) and remove the trees of committed tasks and stopped workers that no busy marker holds; `clean` also sweeps the Xcode DerivedData folders of removed trees and, with `--module-cache-hours H`, ModuleCache.noindex entries untouched for H hours; each tree builds with `-derivedDataPath <tree>/.build/DerivedData`.",
    "run_tests": "A tree run exports SUPERLITE_DERIVED_DATA_PATH=<tree>/.build/DerivedData to its setup and command (a test-cmd.json env entry wins); on an Xcode stack whose command has no rewritable xcodebuild word and names no script that reads the variable it prints one WARNING per command; below the warn level it prunes module cache entries older than 24 h and prints `module cache: removed N entries older than 24 h, X GB` (#614).",
    "dispatch": "Before a round it checks the disk like run_tests (refuse below 20 GB, warn below 50 GB), sweeps orphaned DerivedData and drops the trees of committed tasks, stopped workers and evicted agents (#574).",
    "commit_task": "A checkpointed task's test tree is removed unless a run marks it busy (#614).",
    "fleet": "`stop` removes the stopped worker's `worker-<Wn>` tree; `spawn` (not `--for-dispatch`, which dispatch gates) refuses below the disk floor with `BLOCKED: fleet spawn: disk: ...`, exit 3 (#614).",
    "finish": "It removes the run's idle test trees and orphaned DerivedData and says so in one stderr line (#614).",
    "orchestrator": "`end` removes the run's idle test trees and orphaned DerivedData too (#614).",
}


@pytest.mark.parametrize("name", sorted(SENTENCES))  # O(1)
def test_row_names_614_cleanup(name):  # O(n)
    rows = [l for l in DOC.read_text().splitlines() if l.startswith(f"| `{name}` |")]  # O(n)
    assert len(rows) == 1  # O(1)
    assert SENTENCES[name] in rows[0]  # O(1)
