from test_plan_tools import ROOT

CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def row(name):
    return next(x for x in TOOLS.splitlines() if x.startswith(f"| `{name}` |"))


def test_docs_name_the_main_side_merge():
    ref = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")
    fleet = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    assert '"$SL" backlog ship B merge --from-main' in CMD
    assert '"$SL" backlog ship B merge --from-main' in ref
    assert "merge denied: main runs sl backlog ship B merge --from-main" in ref
    assert "ship B merge --from-main" in fleet
    assert "`merge --from-main`" in row("backlog_ship") and "rebase aborted" in row("backlog_ship")
    assert CMD.index("merge --from-main") < CMD.index("backlog ship B done")


def test_command_names_skip_and_park_with_their_reasons():
    for s in ('"$SL" backlog skip <issue>', "waits on outside work, such as another open PR",
              '"$SL" backlog park B --reason R', "needs a human design decision"):
        assert s in CMD, s


def test_command_names_several_ids_done_and_the_reprompt():
    for s in ('"$SL" backlog start B7 B10', "the others still start", '"$SL" backlog ship B done --pr N',
              "maxapp ship -C <worktree>", "no status in stop text"):
        assert s in CMD, s
    assert CMD.index("backlog start B7 B10") < CMD.index("backlog ship B done") < CMD.index("Repeat 4 and 5")


def test_tools_rows_name_the_new_forms():
    assert all(s in row("backlog") for s in ("`skip <issue>`", "`park B --reason R`", "another open PR", "human design decision"))
    assert all(s in row("backlog_run") for s in ("`backlog start [B ...]", "`start B7 B10`", "the others still start", "no status in stop text"))
    assert all(s in row("backlog_ship") for s in ("`done --pr N [--version X]`", "(main only)", "shipped by hand", "releases the ship lock"))
