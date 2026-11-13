from test_plan_tools import ROOT

SDD = ((ROOT / "skills" / "subagent-driven-development" / "backlog-main.md").read_text(encoding="utf-8") + "\n" + (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8"))
CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")


def step2(text):
    return next(x for x in text.splitlines() if x.startswith("2. "))


def test_sdd_backlog_names_source_and_reasons():
    s = step2(SDD)
    for t in ("--github", "a plain `plan` reuses them", "not planned (triage: <why>)",
              "--max-batches N", "sl backlog skip <issue>", "over 40 characters"):
        assert t in s, t


def test_command_names_source():
    s = step2(CMD)
    assert "backlog plan --github" in s and "--max-batches N" in s
