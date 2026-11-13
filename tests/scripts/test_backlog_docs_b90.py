from test_plan_tools import ROOT

BACKLOG = ((ROOT / "skills" / "subagent-driven-development" / "backlog-main.md").read_text(encoding="utf-8") + "\n" + (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8"))
CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")

NEW3 = "One ship approval covers every batch of one plan round: each `plan` (also `--reset`) asks it again and `plan --add` keeps it; `decide --print` lists it last, `Approve shipping (Recommended)` first. An approval the user's own prompt gave is recorded with `\"$SL\" backlog decide --approve-ship --source prompt`. An answers file needs `\"by\"`: `\"user\"` for AskUserQuestion answers, `\"main\"` for answers main ruled as AI orchestrator, or a `{question: \"user\"|\"main\"}` map; `decide` and `answer` record it, lead briefs list those under main's rulings, never as Max's, and the ship approval refuses `main`."
S5 = "A shipped line ends with ` followups=N` and ` undone=M` when the lead's notes hold `Follow-up:` or `Left undone:` lines; one `B follow-up: <text>` or `B left undone: <text>` line per item follows it, and `status` keeps both counts in the shipped row. `\"$SL\" backlog tell B --text T` (main only) messages a running batch's lead; a needs_decision batch takes `answer`. A plain `sl fleet status` in main lists main's own fleet and names the running leads in one `backlog:` line."
LEAD = "Note lines are `Ruling: ...`, `Follow-up: ...` (a follow-up issue; main files it) and `Left undone: ...` (a decided step you could not run, such as a denied remote or production command), `Unverified: <step> (#N)` and `Kind: design`; main's wait line carries follow-ups and left-undone items. The summary `.superlite/backlog/B.md` keeps each note line up to 400 characters, cuts a longer one at its last sentence end or whole word with the marker ` [cut: sl backlog ship <B> notes prints the full text]`, and `B.notes.md` beside it holds the full notes. The summary paragraph runs: head `B shipped: #N` or `B no-change: #N`, `PR:`, `Version:`, the generated `Decisions:` line (`(Max)` or `(main's ruling)`), `No change:` or `Kind: design, awaits plan approval`, then the note lines, `Unverified:` written `UNVERIFIED:`."
C3 = "The last question is the ship approval, `Approve shipping (Recommended)` first; it covers every batch of this plan round (each new `plan` asks again, `plan --add` keeps it). When the user's prompt already approved shipping, record that with `\"$SL\" backlog decide --approve-ship --source prompt` instead of asking. An answer you ruled yourself as AI orchestrator goes into the answers file with `\"by\": {\"<question>\": \"main\"}` (the default is `user`), so leads record it as your ruling, not the user's; the ship approval is never yours to rule."
C5 = "A `shipped` line may end with ` followups=N undone=M`: the `B follow-up:` and `B left undone:` lines after it go into your closing report; file a follow-up issue or run an undone step only after the user approves it. To message a running lead, run `\"$SL\" backlog tell B --text \"...\"`; `sl fleet status` in main lists only main's own workers and names the leads in a `backlog:` line."


def section(text, a, b):
    return text.split(a, 1)[1].split(b, 1)[0]


def line(text, prefix):
    return next(x for x in text.splitlines() if x.startswith(prefix))


def test_main_doc_b90():
    main = section(BACKLOG, "## Main", "## Lead")
    l3 = line(main, "3. ")
    assert NEW3 in l3
    assert "One ship approval covers all batches." not in l3
    assert S5 in line(main, "5. ")
    assert line(section(BACKLOG, "## Lead", "## Permissions"), "- Keep your notes in").endswith(" " + LEAD)


def test_command_doc_b90():
    l3 = line(CMD, "3. ")
    assert C3 in l3
    assert "The last question is the one ship approval." not in l3
    assert line(CMD, "5. ").endswith(" " + C5)
