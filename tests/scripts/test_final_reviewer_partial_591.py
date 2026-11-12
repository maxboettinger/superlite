"""#591: a final reviewer's approval that left packet lines unread is labelled partial, and fleet wait shows it."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import fleet_io  # noqa: E402
import fleet_report  # noqa: E402

REVIEWER = (ROOT / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
PART = "Verdict: APPROVED (partial: lines 685-1212 not read)\nChecked: lines 685-1212: unverified\n"
JSON = '\n```json\n{"status": "APPROVED", "files": [], "tests": "", "findings": [], "summary": "x"}\n```\n'
READ = ("Read `.superlite/review-packet.md` whole, to its last line `End of packet (N lines)`: when one Read stops early, Read on with an offset; nothing else. "
        "Exceptions: what your brief names (first rule below), a file the packet marks `(truncated: ...; read <path> in full)` you may read in full, one Read per such file, "
        "to judge what the excerpt cut, a file the head's `Cut to fit the size cap:` line names as left out of section 8, one Read each (the file as it is now, not its diff), "
        "and every image the packet lists under `## Render evidence`, one Read each, also on the fast path, each with a `Checked:` line. "
        "Answer in one turn: no other searches or reads. The packet holds open incidents, probe failures, categories with no `verified` entry, contract mismatches, "
        "the test summary, cross-package seams, code excerpts, the diff stat and the plan's Review Focus. An inline build's packet adds the spec (section 0); "
        "a later round adds the earlier findings and their fixes (section 0b). Judge from it.")
PARTIAL = ("- Partial: an approval that did not read every packet line up to `End of packet` starts `Verdict: APPROVED (partial: lines A-B not read)` "
           "and lists those lines in a `Checked:` line as `unverified`; never a plain `Verdict: APPROVED` then.")
VERDICT_LINE = "`Verdict: APPROVED`, `Verdict: APPROVED (partial: lines A-B not read)` or `Verdict: CHANGES_REQUESTED`"


def test_partial_values():
    assert fleet_report.partial(PART) is True
    assert fleet_report.partial("Verdict: APPROVED\nChecked: head: read") is False
    assert fleet_report.partial("**Verdict:** APPROVED (partial: lines 9-20 not read)") is True
    assert fleet_report.parse(PART)["status"] == "APPROVED"


def _finish(monkeypatch, tmp_path, capsys, text):
    for name in ("_stop_worker", "_ready", "pane_label"):
        monkeypatch.setattr(fleet_io, name, lambda *a, **k: None)
    monkeypatch.setattr(fleet_io, "pane_title", lambda *a, **k: "t")
    fleet_io._finish(tmp_path, "W2", {"task": "final", "one_turn": True, "role": "final-reviewer"}, text, "transcript")
    return capsys.readouterr().out


def test_wait_line_appends_partial(monkeypatch, tmp_path, capsys):
    assert "APPROVED findings=0 partial " in _finish(monkeypatch, tmp_path, capsys, PART + JSON)


def test_plain_approval_has_no_partial(monkeypatch, tmp_path, capsys):
    out = _finish(monkeypatch, tmp_path, capsys, "Verdict: APPROVED\nChecked: head: read\n" + JSON)
    assert "APPROVED findings=0 " in out and " partial" not in out


def test_reviewer_texts_exact():
    lines = REVIEWER.splitlines()
    for want in (READ, PARTIAL, VERDICT_LINE):
        assert want in lines, want[:40]
    assert "no tools" not in REVIEWER
