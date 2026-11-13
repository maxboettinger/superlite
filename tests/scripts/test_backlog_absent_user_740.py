"""#740: the fresh-session rule for backlog main names the case of an absent user."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMAND = ROOT / "commands" / "backlog.md"
MAIN = ROOT / "skills" / "subagent-driven-development" / "backlog-main.md"

CMD_AWAY = (
    "When the user is away or pre-approved the run (unattended, overnight, \"decide yourself\"), "
    "do not stop: a session cannot clear itself, and ending the turn stalls the backlog. "
    "Go on in this session, accept the re-injected skills after each compaction, "
    "name it in one `Ruling: going on in a session that already loaded <skill>` line "
    "and load no further superlite skill."
)
MAIN_AWAY = (
    "A user who is away or pre-approved the run (unattended, overnight, \"decide yourself\") "
    "gets no such stop: a session cannot clear itself, so main goes on in this session, "
    "accepts the re-injected skills after each compaction, names it in one "
    "`Ruling: going on in a session that already loaded <skill>` line "
    "and loads no further superlite skill."
)


def _para(text: str, head: str) -> str:
    return next(p for p in text.split("\n\n") if p.startswith(head))


def test_command_names_the_absent_user_case_in_the_fresh_session_paragraph():
    para = _para(COMMAND.read_text(encoding="utf-8"), "Start in a fresh session.")
    assert CMD_AWAY in para
    assert para.index("and end your turn.") < para.index(CMD_AWAY)


def test_main_rules_name_the_absent_user_case_beside_the_fresh_session_rule():
    lines = MAIN.read_text(encoding="utf-8").splitlines()
    line = next(l for l in lines if l.startswith("Start main in a fresh session:"))
    assert line.endswith(MAIN_AWAY)
