"""#847: the SDD task message, the implementer text and docs/tools.md name run_tests --affected."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_sdd_step3_names_affected():
    text = read("skills/subagent-driven-development/SKILL.md")
    assert "`<abs sl> run_tests --fast PATHS --task Tn --background` (or `--affected` for `--fast PATHS`), then run" in text
    assert "(mini prime cuts lines)" not in text
    assert len(text) <= 13300


def test_implementer_names_affected():
    line = next(ln for ln in read("agents/implementer.md").splitlines() if ln.startswith("- TDD."))
    assert ("`<abs sl> run_tests --fast PATHS --task Tn --background` (or `<abs sl> run_tests --affected --task Tn --background`: "
            "run_tests picks the tests your change touches; when no test covers it, it exits 2 naming the files, so write that test), "
            "then run the `wait:` line it prints") in line


def test_tools_row_names_affected():
    row = next(ln for ln in read("docs/tools.md").splitlines() if ln.startswith("| `run_tests`"))
    for phrase in ("`--affected [--base REV] [--files F ...]` (#847)", "`testcmd.select_affected`", "`.superlite/test-map.json`",
                   "nothing selected exits 2 naming the untested files; `--fast` paths stay relative to the run root"):
        assert phrase in row, phrase
