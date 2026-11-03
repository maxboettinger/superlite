"""Tests for pt_review packet: claimed fixes whose file is unchanged since base."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_claimed", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_claimed"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** a.py\n\n## Review Focus\n- none\n"


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "T")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / ".gitignore").write_text(".superlite/\npacket.md\nplan.md\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def entry(res: str = "fixed", line: int = 3, file: str = "a.py") -> dict:
    return {"kind": "exception", "file": file, "line": line, "context": "x", "resolution": res,
            "agent": "package-reviewer"}


def packet(repo: Path, entries: list[dict], base: str | None = None) -> str:
    (repo / ".superlite" / "incidents.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    base = base or git(repo, "rev-parse", "HEAD")
    r = subprocess.run([sys.executable, str(SCRIPT), "packet", "--plan", str(repo / "plan.md"),
                        "--root", str(repo), "--out", str(repo / "packet.md"), "--base", base],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return (repo / "packet.md").read_text(encoding="utf-8")


def test_claimed_fix_unchanged_file_listed(repo):
    s = packet(repo, [entry()])
    assert "claimed fixed by package-reviewer" in s and "REVIEW REQUIRED" in s


def test_claimed_fix_changed_file_not_listed(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("x = 1\ny = 2\nz = 4\n", encoding="utf-8")
    s = packet(repo, [entry()], base)
    assert "claimed fixed by" not in s and "FAST PATH" in s


def test_claimed_fix_newest_entry_wins(repo):
    s = packet(repo, [entry("fixed"), entry("")])
    assert "claimed fixed by" not in s


def test_claimed_fix_deleted_file_counts_changed(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "a.py").unlink()
    assert "a.py" in pt.changed_since(repo, base)
    assert "claimed fixed by" not in packet(repo, [entry()], base)


def test_changed_since_includes_untracked(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("changed\n", encoding="utf-8")
    (repo / "new.py").write_text("n\n", encoding="utf-8")
    assert pt.changed_since(repo, base) == {"a.py", "new.py"}


def test_bad_base_renders_and_skips_claimed(repo):
    assert pt.changed_since(repo, "0" * 40) is None
    s = packet(repo, [entry()], "0" * 40)
    assert "claimed fixed by" not in s and "# Review packet" in s


def test_claimed_fix_items_direct():
    es = [entry()]
    (it,) = pt.claimed_fix_items(es, {"b.py"})
    assert it.section == "claimed"
    assert it.title == "a.py:3  claimed fixed by package-reviewer, file unchanged since base"
    assert pt.claimed_fix_items(es, {"a.py"}) == []


def test_claimed_fix_absolute_and_dotslash_paths(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("changed\n", encoding="utf-8")
    ch = pt.changed_since(repo, base)
    assert pt.claimed_fix_items([entry(file=str(repo / "a.py"))], ch, repo) == []
    assert pt.claimed_fix_items([entry(file="./a.py")], ch, repo) == []
    assert pt.claimed_fix_items([entry(file="a\\b.py")], ch, repo)[0].file == "a/b.py"


def test_changed_since_rename_lists_both_paths(repo):
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "mv", "a.py", "b.py")
    assert pt.changed_since(repo, base) == {"a.py", "b.py"}


def test_changed_since_relative_to_subdir_root(repo):
    (repo / "sub").mkdir()
    (repo / "sub" / "c.py").write_text("c\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "sub")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "sub" / "c.py").write_text("d\n", encoding="utf-8")
    (repo / "a.py").write_text("zz\n", encoding="utf-8")
    assert pt.changed_since(repo / "sub", base) == {"c.py"}


def test_claimed_rank_never_raises_against_probe_rank():
    it = pt.claimed_fix_items([entry(file="x", line=5)], set())[0]
    assert sorted([it.rank, (3, "x", "f", 1)])


def _fail_diff(monkeypatch):
    real = subprocess.run

    def fake(cmd, *a, **k):
        if "diff" in cmd:
            raise subprocess.TimeoutExpired(cmd, 1)
        return real(cmd, *a, **k)
    monkeypatch.setattr(pt.subprocess, "run", fake)


def test_changed_since_none_on_diff_failure(repo, monkeypatch):
    base = git(repo, "rev-parse", "HEAD")
    _fail_diff(monkeypatch)
    assert pt.changed_since(repo, base) is None


def _run_packet(repo, monkeypatch, fake):
    (repo / ".superlite" / "incidents.jsonl").write_text(json.dumps(entry()) + "\n", encoding="utf-8")
    monkeypatch.setattr(pt.subprocess, "run", fake)
    pt.main(["packet", "--plan", str(repo / "plan.md"), "--root", str(repo),
             "--out", str(repo / "packet.md"), "--base", "HEAD"])
    return (repo / "packet.md").read_text(encoding="utf-8")


def test_packet_skips_claimed_when_diff_fails(repo, monkeypatch):
    real = subprocess.run

    def fake(cmd, *a, **k):
        if "diff" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        return real(cmd, *a, **k)
    assert "claimed fixed by" not in _run_packet(repo, monkeypatch, fake)


def test_packet_survives_rev_parse_failure(repo, monkeypatch):
    real = subprocess.run

    def fake(cmd, *a, **k):
        if "rev-parse" in cmd:
            raise FileNotFoundError("git")
        return real(cmd, *a, **k)
    s = _run_packet(repo, monkeypatch, fake)
    assert "claimed fixed by" not in s and "# Review packet" in s


def test_rel_strips_symlinked_root(repo, tmp_path_factory):
    link = tmp_path_factory.mktemp("lnk") / "link"
    link.symlink_to(repo, target_is_directory=True)
    assert pt._rel(str(link / "a.py"), link) == "a.py"
    assert pt.claimed_fix_items([entry(file=str(link / "a.py"))], {"a.py"}, link) == []
