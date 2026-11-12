"""Coordinator guard (#547): files listed in .superlite/render-edits.json may be edited in an active run."""
import json
import os

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


def test_render_edits_file_is_protected(tree):
    record(tree, "Demo/Seed.swift")
    target = tree / ".superlite" / "render-edits.json"
    for tool in ("Edit", "Write"):
        assert run(tree, tool, {"file_path": str(target)}).returncode == 2
        assert run(tree, tool, {"file_path": ".superlite/render-edits.json"}).returncode == 2
    assert bash(tree, "echo '{}' > .superlite/render-edits.json").returncode == 2
    assert bash(tree, "cp /tmp/x .superlite/render-edits.json").returncode == 2


def test_recorded_hardlink_is_blocked(tree):
    (tree / "src").mkdir()
    (tree / "src" / "app.py").write_text("a\n")
    try:
        os.link(tree / "src" / "app.py", tree / "Demo" / "Hard.swift")
    except OSError:
        pytest.skip("no hard links")
    record(tree, "Demo/Hard.swift")
    assert run(tree, "Write", {"file_path": str(tree / "Demo" / "Hard.swift")}).returncode == 2
    assert run(tree, "Write", {"file_path": "Demo/Hard.swift"}).returncode == 2
    assert bash(tree, "sed -i '' s/a/b/ Demo/Hard.swift").returncode == 2


def test_recorded_symlink_is_blocked(tree):
    (tree / "src").mkdir()
    (tree / "src" / "app.py").write_text("a\n")
    try:
        os.symlink(tree / "src" / "app.py", tree / "Demo" / "Link.swift")
    except OSError:
        pytest.skip("no symlinks")
    record(tree, "Demo/Link.swift")
    assert run(tree, "Write", {"file_path": str(tree / "Demo" / "Link.swift")}).returncode == 2
    assert run(tree, "Write", {"file_path": "Demo/Link.swift"}).returncode == 2
    assert bash(tree, "sed -i '' s/a/b/ Demo/Link.swift").returncode == 2
