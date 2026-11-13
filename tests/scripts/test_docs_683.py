"""Docs checks for the lean lead path and the wave wait (#683)."""
import re  # O(1)
from pathlib import Path  # O(1)

SDD = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development"  # O(1)


def _read(name):  # O(1)
    return (SDD / name).read_text(encoding="utf-8")  # O(n)


def _both():
    return _read("backlog-main.md") + "\n" + (SDD / "backlog.md").read_text(encoding="utf-8")


def _section(text, head):  # O(n)
    start = text.index(head)  # O(n)
    nxt = text.find("\n## ", start + len(head))  # O(n)
    return text[start:nxt if nxt >= 0 else len(text)]  # O(n)


def test_fleet_md_wave():  # O(n)
    text = _read("fleet.md")  # O(n)
    sec = _section(text, "## Waiting and acting")  # O(n)
    for needle in ("fleet wait --wave --timeout 540000 --plan $PLAN", "--tests <summary path>",
                   "first failure", "fleet wait --any", "background", "BUSY Wn"):  # O(1)
        assert needle in sec, needle  # O(n)
    low = next(p for p in sec.split("\n\n") if p.startswith("Low memory"))  # O(n)
    assert "fleet wait --wave" in low and "fleet wait --any" not in low  # O(n)


def test_polling_defect():  # O(n)
    for name in ("fleet.md", "SKILL.md", "backlog.md"):  # O(1)
        text = _read(name)  # O(n)
        assert "`sleep`" in text and "until grep" in text, name  # O(n)
        assert re.search(r"(?i)defect|loop polling", text), name  # O(n)
    assert "defect" in _read("fleet.md") and "defect" in _read("backlog.md")  # O(n)


def test_researcher_rule():  # O(n)
    fleet = next(l for l in _read("fleet.md").splitlines() if l.startswith("- Research:"))  # O(n)
    lead = _section(_read("backlog.md"), "## Lead")  # O(n)
    bullet = next(b for b in lead.splitlines() if "researcher" in b)  # O(n)
    for line in (fleet, bullet):  # O(1)
        assert "researcher" in line and "pointed brief" in line, line  # O(n)
        assert "only to rule" in line, line  # O(n)
        assert not ("verify" in line and "worker" in line), line  # O(n)


def test_backlog_lead_variant():  # O(n)
    text = _both()  # O(n)
    lead = _section(text, "## Lead")  # O(n)
    for needle in ("lead.text", "`lean`", "`default`", "--wave"):  # O(1)
        assert needle in lead, needle  # O(n)
    step4 = next(l for l in text.splitlines() if l.startswith("4. `\"$SL\" backlog start"))  # O(n)
    assert "--config NAME" in step4  # O(n)


def test_sdd_cap():  # O(n)
    assert len(_read("SKILL.md")) <= 13300  # O(n)


def test_skill_row_names_both_waits():  # O(n)
    row = next(l for l in _read("SKILL.md").splitlines() if l.startswith("| `sleep`/`until grep`"))  # O(n)
    assert "fleet wait --wave" in row and "run_tests --wait" in row  # O(1)
