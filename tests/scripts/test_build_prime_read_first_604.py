"""The prime's `## Read first` section: a plan header line and test-cmd.json `read_first` (#604)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS
from test_slim_prime import make

sys.path.insert(0, str(SCRIPTS))
import build_prime  # noqa: E402

LEAD = "## Read first\n\nRead each of these files in full before your first task; they are not in this prime.\n\n"


def cfg(root, **extra):
    (root / ".superlite").mkdir(exist_ok=True)
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "go", "test": "make test", **extra}), encoding="utf-8")


def home(monkeypatch, tmp_path):
    h = tmp_path / "home"
    (h / "notes").mkdir(parents=True)
    (h / "notes" / "x.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    return h


def touch(root, *names):
    for n in names:
        (root / n).parent.mkdir(parents=True, exist_ok=True)
        (root / n).write_text("x", encoding="utf-8")


def test_read_first_header_and_test_cmd(tmp_path, monkeypatch, capsys):
    h = home(monkeypatch, tmp_path)
    touch(tmp_path, "docs/ui-guide.md", "docs/style.md")
    cfg(tmp_path, read_first=["docs/style.md", "docs/ui-guide.md"])
    plan = "# T\n**Read first:** docs/ui-guide.md, `~/notes/x.md`\n**Spec:** s\n\n## Tasks\n"
    got = build_prime.read_first_section(plan, tmp_path)
    r = tmp_path.as_posix()
    assert got == LEAD + f"- {r}/docs/ui-guide.md\n- {Path('~/notes/x.md').expanduser()}\n- {r}/docs/style.md"
    assert got.startswith("## Read first") and capsys.readouterr().err == ""


def test_read_first_none_is_empty(tmp_path):
    cfg(tmp_path)
    assert build_prime.read_first_section("# T\n**Spec:** s\n", tmp_path) == ""


def test_read_first_bad_type_warns(tmp_path, capsys):
    cfg(tmp_path, read_first="docs/a.md")
    assert build_prime.read_first_section("# T\n", tmp_path) == ""
    assert 'test-cmd.json "read_first" must be a list of paths; ignored' in capsys.readouterr().err


def test_read_first_missing_file_listed_with_warning(tmp_path, capsys):
    got = build_prime.read_first_section("# T\n**Read first:** docs/gone.md\n", tmp_path)
    p = f"{tmp_path.as_posix()}/docs/gone.md"
    assert got.endswith(f"- {p}")
    assert f"build_prime: read first: {p} not found" in capsys.readouterr().err


def test_read_first_only_in_header_block(tmp_path):
    plan = "# T\n**Spec:** s\n\n## Tasks\n**Read first:** docs/a.md\n"
    assert build_prime.read_first_section(plan, tmp_path) == ""


def _plans(tmp_path):
    p = make(tmp_path)
    p.write_text(p.read_text(encoding="utf-8").replace("**Spec:** SPEC.md\n", "**Spec:** SPEC.md\n**Read first:** docs/guide.md\n", 1), encoding="utf-8")
    return p


def _kinds(plan):
    import routing
    old = routing.read_tiers
    routing.read_tiers = lambda _p: {t: "haiku" for t in ("T1", "T2", "T3", "T4")}
    try:
        return [build_prime.build_slim(str(plan)), build_prime.build(str(plan), None, []), build_prime.build_mini(str(plan), "haiku")]
    finally:
        routing.read_tiers = old


def test_slim_full_and_mini_carry_section(tmp_path):
    plan = _plans(tmp_path)
    for data in _kinds(plan):
        text = data.decode("utf-8")
        assert text.count("## Read first") == 1
        assert text.index("Rules:") < text.index("## Read first") < text.index("docs/guide.md")
        nxt = [text.find(h) for h in ("## Background", "## Plan", "## Constraints")]
        assert text.index("## Read first") < min(i for i in nxt if i >= 0)


def test_prime_without_read_first_unchanged(tmp_path):
    for data in _kinds(make(tmp_path)):
        assert b"## Read first" not in data
