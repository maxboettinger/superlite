"""#1152: main's two backlog files name plan's listing lines (#1148) and its two empty-plan lines, as plan prints them."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
DOCS = (ROOT / "commands" / "backlog.md", ROOT / "skills" / "subagent-driven-development" / "backlog-main.md")
LAG = "listing lag: #N read by number (not in the open-issue list yet)"
TAIL = "an issue filed in the last minutes may be missing: sl backlog plan --issues <n> --add plans it"
EMPTY = "nothing to plan: no open issue to triage"
NO_BATCH = "nothing to plan: the proposal holds no batch; sl backlog skip <issue> keeps an issue out of every later plan"
TRIAGE = "triage worker DONE: <summary>"


def _step2(path: Path) -> str:
    return next(ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("2. "))


def test_code_prints_the_documented_lines():
    src = (SCRIPTS / "backlog.py").read_text(encoding="utf-8")
    assert 'f"listing lag: #{n} read by number (not in the open-issue list yet)"' in src
    assert f'LAG_TAIL = "{TAIL}"' in src
    assert 'f"listing: stopped reading by number at #{n} ({why}); {LAG_TAIL}"' in src
    assert 'by number and stopped at the {limit}-read cap; {LAG_TAIL}"' in src
    for line in (EMPTY, NO_BATCH):
        assert f'"{line}"' in src, line


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_step2_names_listing_lines(doc):
    s = _step2(doc)
    assert f"`{LAG}`" in s
    assert "`listing:`" in s
    assert TAIL in s


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_step2_names_empty_plan_lines(doc):
    s = _step2(doc)
    assert f"`{EMPTY}`" in s
    assert f"`{NO_BATCH}`" in s
    assert f"`{TRIAGE}`" in s
    assert "`BLOCKED: proposal rejected`" in s


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_step2_tells_empty_backlog_from_listing_lag(doc):
    """Main reads only these files: the step says which line means an empty backlog and which a lagging listing."""
    s = _step2(doc)
    i = s.index(f"`{EMPTY}`")
    tail = s[i:i + 400]
    assert "the backlog is empty" in tail
    assert "unless a `listing:` line" in tail
