"""The prime's `## Running the app` section: the run root's `launch` map from .superlite/test-cmd.json (#601)."""
from __future__ import annotations

import json
import subprocess
import sys

from test_plan_tools import SCRIPTS, run
from test_slim_prime import BUILD_PRIME, make, slim

sys.path.insert(0, str(SCRIPTS))
import build_prime  # noqa: E402

NOTE = 'test-cmd.json "launch" must map each platform to {"worker": true|false, "data": "...", "why": "..."}; ignored'
WHY = "the Debug app shares bundle id, container and Keychain with the installed app"


def cfg(tmp_path, launch=None, **extra):
    d = {"language": "go", "test": "make test", **extra}
    if launch is not None:
        d["launch"] = launch
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(d), encoding="utf-8")


def section(text):
    return text.split("## Running the app")[1].split("\n## ")[0]


def lines(text):
    return [ln for ln in section(text).splitlines() if ln.startswith("- ")]


def test_slim_prime_lists_launch_platforms(tmp_path):
    cfg(tmp_path, {"ios": {"worker": True, "data": "-demo: demo account, 3 lists"},
                   "macos": {"worker": False, "why": WHY, "data": "SwiftUI previews only"}})
    _, text = slim(tmp_path, make(tmp_path))
    assert text.index("## Global constraints") < text.index("## Running the app") < text.index("## Stable tasks")
    assert lines(text) == ["- ios: a worker may launch it; data: -demo: demo account, 3 lists",
                           f"- macos: no worker launch ({WHY}); data: SwiftUI previews only"]


def test_full_prime_has_launch_section_before_plan(tmp_path):
    cfg(tmp_path, {"ios": {"worker": True}})
    _, text = slim(tmp_path, make(tmp_path), "f.md", "--prime", "full")
    assert text.index("Rules:") < text.index("## Running the app") < text.index("## Plan")


def test_no_launch_entry_leaves_prime_unchanged(tmp_path):
    p = make(tmp_path)
    _, base = slim(tmp_path, p, "a.md")
    cfg(tmp_path)
    _, with_cfg = slim(tmp_path, p, "b.md")
    assert base.encode() == with_cfg.encode() and "## Running the app" not in with_cfg
    assert (tmp_path / "a.md").read_bytes() == (tmp_path / "b.md").read_bytes()


def test_worker_missing_says_not_recorded(tmp_path):
    cfg(tmp_path, {"web": {"data": "seeded db"}})
    assert lines(slim(tmp_path, make(tmp_path))[1]) == ["- web: worker launch not recorded; data: seeded db"]
    cfg(tmp_path, {"web": {"worker": False}})
    assert lines(slim(tmp_path, make(tmp_path), "b.md")[1]) == ["- web: no worker launch"]


def test_string_platform_value_verbatim(tmp_path):
    cfg(tmp_path, {"web": "npm run dev on a free port; SEED=1 seeds 3 users"})
    assert lines(slim(tmp_path, make(tmp_path))[1]) == ["- web: npm run dev on a free port; SEED=1 seeds 3 users"]


def test_main_checkout_launch_used_from_worktree(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    g = lambda *a, cwd=main: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)  # noqa: E731
    g("init", "-q")
    g("commit", "-q", "--allow-empty", "-m", "init")
    cfg(main, {"ios": {"worker": True, "data": "demo"}})
    wt = tmp_path / "wt"
    g("worktree", "add", "-q", str(wt), "-b", "feat")
    assert not (wt / ".superlite" / "test-cmd.json").exists()
    _, text = slim(wt, make(wt))
    assert lines(text) == ["- ios: a worker may launch it; data: demo"]


def test_mini_prime_has_no_launch_section(tmp_path):
    cfg(tmp_path, {"ios": {"worker": True}})
    _, text = slim(tmp_path, make(tmp_path), "m.md", "--tier", "haiku")
    assert "## Running the app" not in text
    assert "## Running the app" not in (tmp_path / "m.md").read_text(encoding="utf-8")


def test_launch_not_object_ignored_with_note(tmp_path, capsys):
    cfg(tmp_path, ["ios"])
    assert build_prime.launch_section(tmp_path) == ""
    assert capsys.readouterr().err.strip() == NOTE


def test_platform_value_list_skipped(tmp_path, capsys):
    cfg(tmp_path, {"ios": ["x"], "web": "npm run dev"})
    out = build_prime.launch_section(tmp_path)
    assert [ln for ln in out.splitlines() if ln.startswith("- ")] == ["- web: npm run dev"]
    assert capsys.readouterr().err.count(NOTE) == 1


def test_multiline_data_collapsed(tmp_path):
    cfg(tmp_path, {"web": {"worker": True, "data": "a\n  b"}})
    assert "- web: a worker may launch it; data: a b" in build_prime.launch_section(tmp_path)


def test_user_entry_launch_ignored(tmp_path, monkeypatch):
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"go": {"test": "make test", "launch": {"ios": {"worker": True}}},
                                "test": "make test", "launch": {"ios": {"worker": True}}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(user))
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    assert build_prime.launch_section(tmp_path) == ""


def test_non_ascii_kept(tmp_path):
    cfg(tmp_path, {"web": {"worker": True, "data": "Größe ✓"}})
    _, text = slim(tmp_path, make(tmp_path))
    assert "data: Größe ✓" in text
    assert "Größe ✓".encode("utf-8") in (tmp_path / "s.md").read_bytes()
