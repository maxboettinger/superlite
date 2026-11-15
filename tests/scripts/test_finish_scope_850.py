import sys

from test_run_scripts import run, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402


def finish_out(tmp_path, text):
    ledger = tmp_path / "progress.md"
    ledger.write_text(text, encoding="utf-8")
    return run("finish", "--ledger", ledger, "--log", tmp_path / "none.jsonl").stdout


def test_finish_prints_scope_section(tmp_path):
    out = finish_out(tmp_path, "Ruling: keep the CLI flag names\n"
                     "Ruling: [scope] drop CSV export - spec 4 conflicts - cost: one task\n"
                     "- **Ruling:** [SCOPE] rename parse() - clash - cost: re-run\n")
    assert "rulings: 3\n" in out
    assert ("scope rulings: 2\n- drop CSV export - spec 4 conflicts - cost: one task\n"
            "- rename parse() - clash - cost: re-run\n\n") in out
    assert "- [scope] drop CSV export - spec 4 conflicts - cost: one task" in out


def test_finish_no_scope_section(tmp_path):
    assert "scope rulings" not in finish_out(tmp_path, "Ruling: keep the CLI flag names\n")


def test_scope_rulings_examples():
    assert finish.scope_rulings(["keep the flags", "[scope] drop CSV export - spec 4 - one task",
                                 "[SCOPE]  rename parse()"]) == ["drop CSV export - spec 4 - one task", "rename parse()"]
    assert finish.scope_rulings(["keep [scope] as a word", "[scope]", "[scope]   "]) == []


def test_scope_section_after_rulings_block(tmp_path):
    lines = finish_out(tmp_path, "Ruling: a\nRuling: [scope] b\nhold T1: wait\n").splitlines()
    i = lines.index("scope rulings: 1")
    start = lines.index("rulings: 2")
    last = max(k for k, l in enumerate(lines[start:], start) if l.startswith("- ") and k < i)
    assert last < i
    for k, l in enumerate(lines):
        if l.startswith("held:") or l.startswith("tests"):
            assert k > i
