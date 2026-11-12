"""#594 follow-ups: the packet refuses while render edits are applied and shows the summary warning."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

WARN = "Package.swift declares platforms iOS, macOS; no destination built iOS"


def setup(tmp_path: Path, summary: dict | None = None, edits: dict | None = None) -> Path:
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (tmp_path / "plan.md").write_text("# Plan\n\n### T1 a\n**Owns:** a.py\n", encoding="utf-8")
    if summary is not None:
        (sl / "test-summary.json").write_text(json.dumps(summary), encoding="utf-8")
    if edits is not None:
        (sl / "render-edits.json").write_text(json.dumps(edits), encoding="utf-8")
    return sl


def packet(tmp_path: Path) -> int:
    return pt_review.main(["packet", "--plan", str(tmp_path / "plan.md"), "--root", str(tmp_path)])


def section4(text: str) -> str:
    return text.split("## 4. Test summary", 1)[1]


def test_packet_refuses_applied_render_edits(tmp_path, capsys):
    sl = setup(tmp_path, edits={"files": {"Sources/App/Demo.swift": {"original": "x"}}})
    assert packet(tmp_path) == 2
    assert ("BLOCKED: render edits still applied: Sources/App/Demo.swift; "
            "run sl render_edit restore first") in capsys.readouterr().out
    assert not (sl / "review-packet.md").exists()


def test_packet_after_restore_builds(tmp_path):
    sl = setup(tmp_path, edits={"files": {}})
    assert packet(tmp_path) == 0
    assert (sl / "review-packet.md").is_file()


def test_packet_shows_summary_warning(tmp_path):
    sl = setup(tmp_path, summary={"passed": 3, "failed": 0, "skipped": 0, "mode": "full", "warning": WARN})
    assert packet(tmp_path) == 0
    assert f"- WARNING: {WARN}" in section4((sl / "review-packet.md").read_text(encoding="utf-8"))


def test_no_warning_key_no_line(tmp_path):
    sl = setup(tmp_path, summary={"passed": 3, "failed": 0, "skipped": 0, "mode": "full"})
    assert packet(tmp_path) == 0
    assert "WARNING" not in section4((sl / "review-packet.md").read_text(encoding="utf-8"))
    for bad in ("", "  ", None, 0, False, []):
        rows, _n = pt_review._summary_rows({"passed": 1, "failed": 0, "warning": bad}, None, None)
        assert not any("WARNING" in r for r in rows)


def test_warning_on_newest_summary(tmp_path):
    rows, _n = pt_review._summary_rows({"passed": 1, "failed": 0, "mode": "fast", "warning": "w" * 400}, None, None)
    assert rows[-1] == "- WARNING: " + "w" * 400


HINT = "this worktree lacks 3 commits of main; run `git merge main` before trusting this red run"


def test_warning_with_hint_shown_whole(tmp_path):
    warn = "p" * 350 + "; " + HINT
    sl = setup(tmp_path, summary={"passed": 3, "failed": 0, "skipped": 0, "mode": "full", "warning": warn})
    assert packet(tmp_path) == 0
    assert f"- WARNING: {warn}" in section4((sl / "review-packet.md").read_text(encoding="utf-8"))


def test_warning_list_one_line_each(tmp_path):
    rows, _n = pt_review._summary_rows({"passed": 1, "failed": 0, "warning": ["a", "", "b"]}, None, None)
    assert [r for r in rows if "WARNING" in r] == ["- WARNING: a", "- WARNING: b"]


def test_warning_on_error_summary(tmp_path):
    sl = setup(tmp_path, summary={"error": "killed by signal 15", "warning": "behind main"})
    assert packet(tmp_path) == 0
    assert "- WARNING: behind main" in section4((sl / "review-packet.md").read_text(encoding="utf-8"))


def test_warning_over_cap_truncated(tmp_path):
    rows, _n = pt_review._summary_rows({"passed": 1, "failed": 0, "warning": "w" * 2500}, None, None)
    assert rows[-1] == "- WARNING: " + "w" * 2000 + " (truncated)"
