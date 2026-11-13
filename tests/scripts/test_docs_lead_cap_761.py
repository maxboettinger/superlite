"""backlog-main.md, docs/tools.md and docs/config.md name the per-round cap read and the new status texts (#761)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = (ROOT / "skills" / "subagent-driven-development" / "backlog-main.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
CONFIG = (ROOT / "docs" / "config.md").read_text(encoding="utf-8")


def step(n):
    return next(l for l in MAIN.splitlines() if l.startswith(f"{n}. "))


def row(name):
    return next(l for l in TOOLS.splitlines() if l.startswith(f"| `{name}` |"))


def test_main_step4_names_cap():
    s = step(4)
    for w in ("[--cap N]", "`cap:`", "`room`", "`lead_units`", "`leads_per_repo`", "`leads_per_machine`", "`lead_weekly_max`", "fixed cap 2"):
        assert w in s, w
    assert "[--cap 2]" not in MAIN


def test_main_step5_rereads_cap():
    assert "before each start round" in step(5)


def test_main_status_texts():
    assert "`start, or after Bx`" in step(1)
    assert "`B has no open question`" in step(3)


def test_main_step2_depends_lines():
    s = step(2)
    assert "`depends: B no longer waits for D: no shared file and no reason`" in s
    assert "`B waits for D: <reason>`" in s


def test_tools_rows():
    r = row("backlog")
    for w in ("`cap:`", "`room`", "`lead_units`", "`leads_per_repo`", "`leads_per_machine`", "`lead_weekly_max`", "start, or after B", "B has no open question"):
        assert w in r, w
    r = row("backlog_run")
    assert "[--cap N]" in r and "--cap 2" not in r


def test_config_weekly_max_scope():
    sec = CONFIG.split("\n## Lead cap\n")[1].split("\n## ")[0]
    assert "worker" in next(l for l in sec.splitlines() if l.startswith("- `lead_weekly_max`"))


def test_tools_backlog_run_row_punctuation():
    r = row("backlog_run")
    assert "rest.; without" not in r
    assert "for the rest. Without `--cap` start reads the cap: line's limit" in r
