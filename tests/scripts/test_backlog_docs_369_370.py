from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMD = (ROOT / "commands" / "backlog.md").read_text()
SKILL = ((ROOT / "skills" / "subagent-driven-development" / "backlog-main.md").read_text() + "\n" + (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text())
TOOLS = (ROOT / "docs" / "tools.md").read_text()
ROW = next(ln for ln in TOOLS.splitlines() if ln.startswith("| `backlog` |"))


def test_command_names_next_reset_and_word_cut():
    for s in ("its last line is `next: sl backlog plan`.",
              '`"$SL" backlog plan --reset` drops the planned and parked batches and plans every open issue again; shipped batches stay',
              "a plain `plan` names `--reset` in its `BLOCKED:` line",
              "A label the plan cut ends at a whole word; its full text leads the option's description."):
        assert s in CMD, s


def test_skill_main_section_names_next_reset_and_word_cut():
    main = SKILL[SKILL.index("## Main"):SKILL.index("## Lead")]
    for s in ("With no batch open its last line is `next: sl backlog plan`.",
              "An option label is cut at its last whole word, its full text moved to the front of its description.",
              "`--reset` drops the planned and parked batches and plans every open issue again (shipped batches stay)"):
        assert s in main, s


def test_tools_row_names_reset_word_cut_and_next():
    for s in ("`--reset` drops the planned and parked batches and plans every open issue again; shipped batches stay; refused while a batch is running or needs_decision",
              "a label cut at its last whole word with its full text moved to the front of its description,",
              "and `next: sl backlog plan` when no batch is open"):
        assert s in ROW, s
    assert ROW.endswith(" |")
