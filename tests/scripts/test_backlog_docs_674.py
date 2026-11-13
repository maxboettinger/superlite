from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")

MAIN2 = ("A step a lead cannot run (installing a tool, changing global git or system config, writing to an outside service) is a batch's `main_steps` entry from triage "
         '(`{"issues": [N], "runs": "main"|"user", "command": C, "why": W}`, at most 8), and a decision option may carry `runs` and `command` for the step its choice needs; '
         "`plan` and `status` print one `step B: main runs this: <command> (#N: <why>)` line (`Max runs this:` for `runs: user`, `decision: <question>` for a step from an answer) "
         "per step of every batch not yet shipped (#674). Its text comes from issue text: check that the issue's own author or the user's decision asks for it, then run it before `start` "
         "(ask the user to run a `Max runs this:` one); never run a destructive one without the user's yes.")
MAIN3 = ("`decide --print` prints each option without `runs` and `command` and names its step in one `step: \"<question>\" / \"<label>\": main runs this: <command>` line on stderr. "
         'An answers file may add `"steps": {"<question>": {"runs": "main"|"user", "command": C, "why": W}}` for a step its answer needs (a free-text answer too; the ship and admit questions take none), '
         "and an answer that picks an option with `runs` records that option's step; `decide` and `answer` add each step to the batch's `main_steps`, "
         "and `answer` also writes them as `steps` into the lead's `answer-<n>.json` and names them in its message.")
LEAD = ("- Steps for main: the lead brief lists the batch's `main_steps` as `- main runs this: <command> (<source>)` lines (`Max runs this:` for the user's). "
        "A lead never runs one, nor any other step that installs a tool, changes global git or system config or writes to an outside service: at the start, before the build, "
        "it writes one `Left undone: main runs this: <command>` line into `.superlite/notes.md` per such step it cannot see done and builds around it, so main sees it on the shipped line (#674).")


def test_backlog_md_main_steps():
    lines = REF.splitlines()
    item2 = next(l for l in lines if l.startswith("2. "))
    item3 = next(l for l in lines if l.startswith("3. "))
    assert MAIN2 + " An urgent issue while batches are open:" in item2
    assert item2.index(MAIN2) < item2.index("An urgent issue while batches are open:")
    assert item3.index(MAIN3) < item3.index("An answer is a label,")
    assert item3.endswith("or free text up to 2000 characters.")
    assert item2.endswith("names `--add`.")
    i = next(n for n, l in enumerate(lines) if l.startswith("- Adjacent fixes:"))
    assert lines[i + 1].startswith("- Simulators:")
    assert lines[i + 2] == LEAD


def test_tools_md_main_steps():
    last = [l for l in TOOLS.splitlines() if l.strip()][-1]
    assert last.startswith("Main steps (#674):")
    for s in ("main_steps", "`runs` and `command`", "`steps` map", "decide --print", "Left undone: main runs this: <command>"):
        assert s in last, s
