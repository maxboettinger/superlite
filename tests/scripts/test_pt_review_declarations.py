"""Tests for pt_review: declaration contract for non-Python producers and the checkpoint diff."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)


def swift(tmp_path: Path) -> Path:
    dest = tmp_path / "swiftproj"
    shutil.copytree(HERE / "fixtures" / "review_swift", dest)
    return dest


def basic(tmp_path: Path) -> Path:
    dest = tmp_path / "basicproj"
    shutil.copytree(HERE / "fixtures" / "review_basic", dest)
    return dest


def contract(proj: Path, *extra: str) -> int:
    return pt_review.main(["contract", "--plan", str(proj / "plan.md"), "--root", str(proj), *extra])


def test_swift_produces_declared_is_verified(tmp_path, capsys):
    proj = swift(tmp_path)
    assert contract(proj, "--seam", "T1,T2") == 0
    out = capsys.readouterr().out
    assert "part1:" in out and "checked by declaration" in out
    log = [json.loads(ln) for ln in (proj / ".superlite" / "incidents.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in log] == ["verified"]


def test_swift_produces_missing_is_mismatch(tmp_path, capsys):
    proj = swift(tmp_path)
    plan = proj / "plan.md"
    plan.write_text(plan.read_text().replace("NotificationPreferences.level(for", "Missing.thing(for", 1))
    assert contract(proj, "--seam", "T1,T2") == 1
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.startswith("MISMATCH part1")]
    assert len(lines) == 1 and "`Missing`" in lines[0] and "Sources/Kit/Notifications.swift" in lines[0]


def test_check_interfaces_values(tmp_path):
    proj = swift(tmp_path)
    plan = pt_review.parse_plan(proj / "plan.md")
    assert pt_review.check_interfaces(plan, proj, ["T1"]) == ([], 1)


def test_declaration_ignores_comments_and_strings(tmp_path):
    (tmp_path / "A.swift").write_text(
        '// struct OnlyComment {\n'
        'let s = "struct OnlyString"\n'
        '    * class Starred\n'
        'let x = 1 // enum Trailing\n'
        'public struct Real: Sendable {\n', encoding="utf-8")
    find = pt_review.find_declaration
    assert find(tmp_path, ["A.swift"], "OnlyComment") is None
    assert find(tmp_path, ["A.swift"], "OnlyString") is None
    assert find(tmp_path, ["A.swift"], "Starred") is None
    assert find(tmp_path, ["A.swift"], "Trailing") is None
    assert find(tmp_path, ["A.swift"], "Real") == ("A.swift", 5)


def test_declaration_skips_test_files(tmp_path):
    (tmp_path / "Tests").mkdir()
    (tmp_path / "Tests" / "T.swift").write_text("struct Foo {}\n", encoding="utf-8")
    assert pt_review.find_declaration(tmp_path, ["Tests/T.swift"], "Foo") is None


def test_declaration_line_in_fixture(tmp_path):
    proj = swift(tmp_path)
    hit = pt_review.find_declaration(proj, ["Sources/Kit/Notifications.swift"], "NotificationPreferences")
    assert hit == ("Sources/Kit/Notifications.swift", 12)


def test_python_fixture_unchanged(tmp_path, capsys):
    proj = basic(tmp_path)
    assert contract(proj) == 0
    assert "declaration" not in capsys.readouterr().out
    wb = proj / "src" / "minisheet" / "workbook.py"
    wb.write_text(wb.read_text(encoding="utf-8").replace(
        "def set(self, ref: str, raw: str) -> list[str]", "def set(self, raw: str, ref: str) -> set[str]"), encoding="utf-8")
    assert contract(proj) == 1
    assert "parameter order differs" in capsys.readouterr().out


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    (r / "base.py").write_text("x = 1\n", encoding="utf-8")
    git(r, "add", "base.py")
    git(r, "commit", "-q", "-m", "base")
    return r


def test_diff_uses_newest_checkpoint_sha(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "new.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "new.py")  # shadow commit holding new.py without moving HEAD
    tree = git(repo, "write-tree")
    sha = git(repo, "commit-tree", tree, "-p", base, "-m", "T1")
    git(repo, "update-ref", "refs/superlite/r/T1", sha)
    git(repo, "reset", "-q")
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "checkpoints.json").write_text(
        json.dumps({"entries": [{"task": "T0", "sha": base}, {"task": "T1", "sha": sha}]}), encoding="utf-8")
    assert pt_review.diff_head(repo) == sha
    assert "new.py" in pt_review.git_diff_stat(repo, base)
    assert "new.py" in pt_review.source_excerpts(repo, base, ["new.py"])


def test_diff_without_checkpoints_uses_working_tree(repo):
    base = git(repo, "rev-parse", "HEAD")
    assert pt_review.diff_head(repo) is None
    (repo / "base.py").write_text("x = 2\n", encoding="utf-8")
    assert "base.py" in pt_review.git_diff_stat(repo, base)


@pytest.mark.parametrize("entries", [[{"sha": None}], [{"sha": "--output=x"}], [{"sha": 5}], "abc", {"a": 1}, [], [{}]])
def test_diff_head_malformed_entries_is_none(tmp_path, entries):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "checkpoints.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    assert pt_review.diff_head(tmp_path) is None


def test_diff_head_accepts_short_ids(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "checkpoints.json").write_text(json.dumps({"entries": [{"sha": "a1"}, {"sha": "b2"}]}), encoding="utf-8")
    assert pt_review.diff_head(tmp_path) == "b2"
