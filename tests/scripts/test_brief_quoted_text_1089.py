"""The #1015 brief check reads quoted text and missing paths as text; research may name the outside paths the standing note lists (#1089)."""
import os, sys, types
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import findings  # noqa: E402
import fleet_io  # noqa: E402
import fleet_roles  # noqa: E402


def F(quote=None, fp=None, tier=1):
    d = {"id": "F-1", "file": "a.py", "line": 3, "problem": "p", "fix": "f", "tier": tier, "label": "R1"}
    return findings.finding_line({**d, **({"quote": quote} if quote else {}), **({"fp": fp} if fp else {})})


@pytest.fixture
def r(tmp_path, monkeypatch):
    tmp = tmp_path.resolve(); home = tmp / "home"; home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(fleet_roles, "SKILLS", tmp / "plug" / "skills")
    proj = tmp / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    other = home / "github" / "other"; (other / "src").mkdir(parents=True); (other / "src" / "a.py").write_text("a\n")
    (home / ".local" / "share").mkdir(parents=True)
    return types.SimpleNamespace(home=home, proj=proj, sd=sd, other=other)


def test_unquoted_blanks_the_standing_note_block():
    text = f"x\n{bb.NOTE_HEAD}\n    Read /o/a.md\n    and /o/b.md\ny\n"
    assert findings.unquoted(text) == "x\n\n\n\ny\n"


def test_unquoted_empties_a_finding_quote_span():
    assert findings.unquoted(F("x = '~/github/other' `y`", "ab12")) == "- F-1 a.py:3 - p - f (tier 1, from R1) quote: `` fp: ab12"
    assert findings.unquoted(F("see ~/github/other", tier=2)) == "- F-1 a.py:3 - p - f (tier 2, from R1) quote: ``"


def test_unquoted_leaves_other_text_alone():
    text = "Read ~/github/other/src/a.py\n```\n/o/x\n```\n"
    assert findings.unquoted(text) == text


def test_local_path_expands_and_joins():
    assert fleet_io.local_path("~/x/../y.md", "/p") == os.path.expanduser("~/y.md")
    assert fleet_io.local_path("../o/a.md", "/p/w") == "/p/o/a.md"
    assert fleet_io.local_path("//abs/x", "/p") == "/abs/x"


def test_existing_outside_path_is_still_named(r):
    assert fleet_io.brief_outside(f"Read {r.other}/src/a.py\n", r.proj, r.sd) == [f"{r.other}/src/a.py"]


def test_missing_paths_are_text(r):
    text = "Deploy to ~/app and ~/.local/share/app/db.sqlite on the host.\n"
    assert fleet_io.brief_outside(text, r.proj, r.sd) == []


def test_note_block_and_quote_pass(r):
    text = f"{bb.NOTE_HEAD}\n    Reference: {r.other}/src/a.py read-only\n\nFindings:\n{F(f'ROOT = {r.other!s}')}\n"
    assert fleet_io.brief_outside(text, r.proj, r.sd) == []


def test_research_may_name_paths_the_note_lists(r, monkeypatch):
    monkeypatch.setattr(bb, "research_reads", lambda sd: [str(r.other)], raising=False)
    text = f"Read {r.other}/src/a.py and {r.home}/github\n"
    assert fleet_io.brief_outside(text, r.proj, r.sd, role="research") == [f"{r.home}/github"]
    assert fleet_io.brief_outside(text, r.proj, r.sd, role="implementer") == [f"{r.other}/src/a.py", f"{r.home}/github"]


def test_brief_refusal_uses_the_text_rules(r):
    brief = r.sd / "briefs" / "fix.md"; brief.parent.mkdir()
    brief.write_text(f"{bb.NOTE_HEAD}\n    Reference: {r.other}/src/a.py\nDeploy to ~/app.\n")
    assert fleet_io.brief_refusal(r.sd, brief, "fixer") is None
    brief.write_text(f"Read {r.other}/src/a.py\n")
    assert fleet_io.brief_refusal(r.sd, brief, "fixer").startswith("error: brief ")
