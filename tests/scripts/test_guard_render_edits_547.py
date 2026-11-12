"""Coordinator guard (#547): files listed in .superlite/render-edits.json may be edited in an active run."""
import json

import pytest

from test_block_coordinator_edits import bash, proj, run  # noqa: F401


def record(proj, *files):
    data = {"files": {f: {"existed": True} for f in files}, "started": 1}
    (proj / ".superlite" / "render-edits.json").write_text(json.dumps(data, indent=1, sort_keys=True))


@pytest.fixture
def tree(proj):
    (proj / "Demo").mkdir()
    for n in ("Seed.swift", "Other.swift"):
        (proj / "Demo" / n).write_text("a\n")
    return proj


def test_edit_of_recorded_file_allowed(tree):
    record(tree, "Demo/Seed.swift")
    for tool in ("Edit", "Write"):
        assert run(tree, tool, {"file_path": str(tree / "Demo" / "Seed.swift")}).returncode == 0
        assert run(tree, tool, {"file_path": "Demo/Seed.swift"}).returncode == 0
        assert run(tree, tool, {"file_path": str(tree / "Demo" / "Other.swift")}).returncode == 2


def test_unrecorded_stays_blocked(tree):
    assert run(tree, "Edit", {"file_path": str(tree / "Demo" / "Seed.swift")}).returncode == 2
    assert bash(tree, "sed -i '' s/a/b/ Demo/Seed.swift").returncode == 2


def test_bash_write_and_checkout_allowed(tree):
    record(tree, "Demo/Seed.swift")
    assert bash(tree, "sed -i '' s/a/b/ Demo/Seed.swift").returncode == 0
    assert bash(tree, "git checkout HEAD -- Demo/Seed.swift").returncode == 0
    assert bash(tree, "sed -i '' s/a/b/ Demo/Other.swift").returncode == 2


def test_block_message_names_render_edit(tree):
    r = run(tree, "Edit", {"file_path": str(tree / "Demo" / "Other.swift")})
    assert r.returncode == 2 and "sl render_edit start" in r.stderr
    last = r.stderr.splitlines()[-2:]
    assert last[-1] == "Blocked target: Demo/Other.swift"
    assert "sl orchestrator end" in last[0]
    r = bash(tree, "sed -i '' s/a/b/ Demo/Other.swift")
    assert "sl render_edit start" in r.stderr


def test_quoted_key_only(tree):
    record(tree, "Demo/Seed.swift.bak")
    assert run(tree, "Edit", {"file_path": "Demo/Seed.swift"}).returncode == 2
    assert bash(tree, "sed -i '' s/a/b/ Demo/Seed.swift").returncode == 2
