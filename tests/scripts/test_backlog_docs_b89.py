from test_plan_tools import ROOT

BACKLOG = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")
CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")

MAIN = {
    "2. ": "An urgent issue while batches are open: `plan --issues N --add` plans it as more batches next to them (running ones too), keeping every batch, the round's ship approval, the source and the cap; the triage brief lists the open batches' files, plan prints one `overlap: <new> shares <files> with <B> (<state>)` line per shared batch, and `start` holds a batch that shares a file with a running one until that one ships; with no batch open `--add` plans like `--issues` alone, and a pinned plan refused by open batches names `--add`.",
    "4. ": "`start --note FILE` stores FILE's text (at most 2000 characters; an empty file clears it) as a standing note: every lead brief written from then on carries it and its lead copies it into its workers' briefs; `status` shows it in a `note:` line, and start names each running lead that started before it.",
    "7. ": "Skip takes an issue out of a planned or parked batch (a running or needs_decision one refuses); a parked batch left empty is dropped, its lead stopped and its worktree kept on disk.",
}
CMDS = {
    "2. ": "An urgent issue while batches run: `\"$SL\" backlog plan --issues N --add` plans it next to them and keeps every batch and the ship approval; an `overlap:` line names a file it shares with an open batch (a batch sharing one with a running batch starts after that one ships).",
    "4. ": "A rule for every lead: `\"$SL\" backlog start --note FILE` puts FILE's text into every lead brief from then on (an empty file clears it); start names the leads already running, which you tell yourself.",
    "7. ": "Skip also takes an issue out of a parked batch (an emptied one is dropped, its lead stopped, its worktree kept).",
}
BULLET = "- Your brief lists the files your batch may touch and the files other open batches own. A file your issues need that no open batch lists (a shared root doc such as CLAUDE.md, AGENTS.md or README.md too) is yours: edit it and name it in notes.md; one another open batch lists goes into notes.md as a follow-up, never dropped. A standing note from main in your brief binds you and goes into every brief and task message you give a worker."


def section(text, a, b):
    return text.split(a, 1)[1].split(b, 1)[0]


def line(text, prefix):
    return next(x for x in text.splitlines() if x.startswith(prefix))


def test_main_steps_name_add_note_skip():
    main = section(BACKLOG, "## Main", "## Lead")
    for p, s in MAIN.items():
        assert line(main, p).endswith(" " + s), p
    assert BULLET in section(BACKLOG, "## Lead", "## Permissions")


def test_command_steps_name_add_note_skip():
    for p, s in CMDS.items():
        assert line(CMD, p).endswith(" " + s), p
