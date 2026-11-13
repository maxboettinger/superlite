# tests/scripts/test_backlog_docs_716.py
"""commands/backlog.md and backlog-main.md name the `B building lead=Wn model=M plan=P` wait line (#716)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")
MAIN = (ROOT / "skills" / "subagent-driven-development" / "backlog-main.md").read_text(encoding="utf-8")
RUN = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "backlog_run.py").read_text(encoding="utf-8")

CMD_TEXT = ("`building` (`B building lead=Wn model=M plan=P`): a planning lead (run config `lead.build_model`) ended "
            "`Status: DONE planned: <plan>`, its plan linted and a build lead on model M took the batch over with plan P; "
            "nothing to do, run `wait` again (`run` goes on by itself);")
MAIN_TEXT = ("A planning lead (run config `lead.build_model`) that ends `Status: DONE planned: <plan>` with a plan that lints gives "
             "`B building lead=Wn model=M plan=P`: a build lead on model M took the batch over with plan P; nothing to do: "
             "`run` goes on, and a single `wait` returns on the line and is run again.")


def test_command_names_the_building_line():
    assert CMD_TEXT in CMD
    assert CMD.index("`shipped`: nothing to do") < CMD.index(CMD_TEXT) < CMD.index("`parked`: note the reason")


def test_main_rules_name_the_building_line():
    assert MAIN_TEXT in MAIN
    assert MAIN.index("one per lead that ends (shipped, parked, needs_decision, BLOCKED).") < MAIN.index(MAIN_TEXT)


def test_docs_match_the_printed_line():
    assert "out.append(f\"{bid} building lead={rec['id']} model={model} plan={plan}\")" in RUN
