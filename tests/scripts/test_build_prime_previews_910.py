"""#910: the prime's `Previews:` line for a linked worktree whose workers get the xcode server."""
import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS
from test_slim_prime import make
from test_build_prime_mini import mini

sys.path.insert(0, str(SCRIPTS))
import build_prime  # noqa: E402
import fleet_mcp  # noqa: E402


def LINE(m):
    return (f"- Previews: RenderPreview cannot show this run's views: it renders the workspace Xcode has open, the main checkout {m}, "
            "not this linked worktree. Never list or run it as a step and never report a preview as unrendered; "
            "the checker renders this run's previews into .superlite/render/ (plan section Running-app checks, reach: preview).")


def cfg(tmp_path, **d):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(d), encoding="utf-8")


def fake_on(monkeypatch):
    monkeypatch.setattr(fleet_mcp, "worktree_previews", lambda p: Path("/w/main"))


def after_fg(text):
    lines = text.splitlines()
    return lines, [i for i, x in enumerate(lines) if x.startswith("- Run the verify command")][0]


def test_preview_line_text(monkeypatch):
    fake_on(monkeypatch)
    assert build_prime.preview_line("/w/wt") == LINE("/w/main")
    monkeypatch.setattr(fleet_mcp, "worktree_previews", lambda p: None)
    assert build_prime.preview_line("/w/wt") == ""


def test_line_follows_fg_in_every_kind(tmp_path, monkeypatch):
    fake_on(monkeypatch)
    cfg(tmp_path, language="python", test="pytest")
    p = make(tmp_path)
    monkeypatch.chdir(tmp_path)
    full = build_prime.build(str(p), None, None).decode()
    for text in (build_prime.build_slim(str(p)).decode(), full, mini(tmp_path)):
        lines, i = after_fg(text)
        assert lines.count(LINE("/w/main")) == 1
        assert lines[i + 1] == LINE("/w/main")


def test_after_verdict_line(tmp_path, monkeypatch):
    fake_on(monkeypatch)
    cfg(tmp_path, language="swift", test="maxapp test")
    lines, i = after_fg(build_prime.build_slim(str(make(tmp_path))).decode())
    assert lines[i + 1].startswith("- Verdict:") and lines[i + 2] == LINE("/w/main")


def test_main_checkout_prime_unchanged(tmp_path, monkeypatch):
    cfg(tmp_path, language="python", test="pytest")
    p = make(tmp_path)
    monkeypatch.setattr(fleet_mcp, "worktree_previews", lambda q: None)
    a = build_prime.build_slim(str(p))
    monkeypatch.setattr(build_prime, "preview_line", lambda root: "")
    assert build_prime.build_slim(str(p)) == a and b"Previews:" not in a


def test_detector_error_adds_nothing(tmp_path, monkeypatch):
    def boom(p):
        raise RuntimeError("x")
    monkeypatch.setattr(fleet_mcp, "worktree_previews", boom)
    assert build_prime.preview_line("/w/wt") == ""
    out = build_prime.build_slim(str(make(tmp_path))).decode()
    assert "Previews:" not in out and "# superlite prime" in out
