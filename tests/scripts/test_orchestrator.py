"""Who orchestrates: the human/AI gate on lint --stable, dispatch, wave0 and build_prime; finish line; bench prompts."""
from __future__ import annotations

import json
from pathlib import Path

from test_plan_tools import SCRIPTS, run
from test_routing import mech_plan

ORCH = SCRIPTS / "orchestrator.py"
REPO = SCRIPTS.parents[2]
LINE = "Orchestrator: AI, do not ask me to choose or to approve."
NO_REPLY = ("BLOCKED: no human approval reply since the review plan was written; show the plan, ask the human to reply approve, "
            "end your turn")
BLOCK = "BLOCKED: human orchestrator selected, show the plan, ask for approval, then run sl orchestrator approve"


def reply(tmp_path, review, approves=True, offset_ms=5000, text="approve"):
    """One line of .superlite/human-replies.jsonl as the UserPromptSubmit hook writes it (t relative to the review file's mtime)."""
    t = int(Path(review).stat().st_mtime * 1000) + offset_ms
    f = tmp_path / ".superlite" / "human-replies.jsonl"
    f.parent.mkdir(exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": t, "approves": approves, "text": text}) + "\n")


def approve_human(tmp_path, by="human", review=None):
    """A real approval: a review plan, a fresh approving human reply, then approve --review."""
    f = review or review_file(tmp_path)
    reply(tmp_path, f)
    return orch(tmp_path, "approve", "--by", by, "--review", f)


def orch(tmp_path, *args):
    return run(ORCH, *args, "--plan", tmp_path / "plan.md", cwd=tmp_path)


def gated(tmp_path, p):
    """The four gated tools, each as (name, process)."""
    sl = tmp_path / ".superlite"
    return {
        "lint --stable": run(SCRIPTS / "plan_tools.py", "lint", "--stable", "--plan", p, cwd=tmp_path),
        "dispatch": run(SCRIPTS / "dispatch.py", "--plan", p, "--pool", sl / "pool.json", "--ledger", sl / "progress.md", cwd=tmp_path),
        "wave0": run(SCRIPTS / "wave0.py", "--plan", p, cwd=tmp_path),
        "build_prime": run(SCRIPTS / "build_prime.py", "--plan", p, "--out", sl / "prime.md", cwd=tmp_path),
    }


def test_each_gated_tool_is_blocked_in_human_mode_and_runs_after_approve(tmp_path):
    p = mech_plan(tmp_path, 2)
    assert "human" in orch(tmp_path, "set", "human").out
    for name, cp in gated(tmp_path, p).items():
        assert cp.returncode == 4, (name, cp.both)
        assert BLOCK in cp.err and len(cp.err.strip().splitlines()) == 1, name
    assert not (tmp_path / ".superlite" / "stable.json").exists() and not (tmp_path / ".superlite" / "briefs").exists()
    ap = approve_human(tmp_path, "carol")
    assert ap.returncode == 0 and "human, approved" in ap.out and "carol" in ap.out
    for name, cp in gated(tmp_path, p).items():
        assert cp.returncode in (0, 1) and BLOCK not in cp.both, (name, cp.both)  # lint may exit 1 for FIX tasks, never 4
    assert (tmp_path / ".superlite" / "stable.json").exists()


def test_schedule_prune_and_plain_lint_stay_allowed_in_human_mode(tmp_path):
    p = mech_plan(tmp_path, 2)
    orch(tmp_path, "set", "human")
    for args in (("schedule", "--plan", p, "--insert"), ("prune", "--plan", p), ("lint", "--plan", p)):
        cp = run(SCRIPTS / "plan_tools.py", *args, cwd=tmp_path)
        assert BLOCK not in cp.both and cp.returncode != 4, (args, cp.both)
    assert "%% schedule" in p.read_text(encoding="utf-8")


def test_ai_mode_and_no_file_are_ungated(tmp_path):
    p = mech_plan(tmp_path, 2)
    for name, cp in gated(tmp_path, p).items():  # no orchestrator.json
        assert BLOCK not in cp.both, (name, cp.both)
    orch(tmp_path, "set", "ai")
    st = json.loads((tmp_path / ".superlite" / "orchestrator.json").read_text(encoding="utf-8"))
    assert st["mode"] == "ai" and st["approved"] is True and st["by"] == "user" and st["time"]
    for name, cp in gated(tmp_path, p).items():
        assert BLOCK not in cp.both, (name, cp.both)


def test_approve_needs_human_mode(tmp_path):
    cp = orch(tmp_path, "approve")
    assert cp.returncode == 2 and "human mode only" in cp.err
    orch(tmp_path, "set", "ai")
    assert orch(tmp_path, "approve").returncode == 2


def test_status_lines(tmp_path):
    assert "not set (ungated)" in orch(tmp_path, "status").out
    orch(tmp_path, "set", "human")
    assert "human, awaiting approval" in orch(tmp_path, "status").out
    approve_human(tmp_path)
    assert "human, approved" in orch(tmp_path, "status").out
    orch(tmp_path, "set", "ai")
    assert orch(tmp_path, "status").out.startswith("orchestrator: AI")


def test_set_ai_can_record_the_headless_default_as_a_ruling(tmp_path):
    orch(tmp_path, "set", "ai", "--by", "coordinator", "--ruling", "orchestrator defaulted to AI - headless run, no human can answer - cost if wrong: none")
    text = (tmp_path / ".superlite" / "progress.md").read_text(encoding="utf-8")
    assert text.strip() == "Ruling: orchestrator defaulted to AI - headless run, no human can answer - cost if wrong: none"


def finish(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    return run(SCRIPTS / "finish.py", "--ledger", sl / "progress.md", "--log", sl / "i.jsonl", cwd=tmp_path).out


def test_finish_reports_the_mode_and_the_approval_time(tmp_path):
    assert "orchestrator: not set (ungated)" in finish(tmp_path)
    orch(tmp_path, "set", "human")
    assert "orchestrator: human, awaiting approval" in finish(tmp_path)
    approve_human(tmp_path, "dana")
    out = finish(tmp_path)
    st = json.loads((tmp_path / ".superlite" / "orchestrator.json").read_text(encoding="utf-8"))
    assert f"orchestrator: human, approved {st['approved_time']} by dana" in out
    orch(tmp_path, "set", "ai")
    assert "orchestrator: AI" in finish(tmp_path)


def bench_prompts():
    b = REPO / "bench"
    return sorted([*b.glob("prompt*.md"), *b.glob("tasks/*/prompt*.md")])


def test_every_bench_prompt_says_the_orchestrator_is_ai():
    files = bench_prompts()
    assert len(files) >= 10
    missing = [str(f.relative_to(REPO)) for f in files if LINE not in f.read_text(encoding="utf-8")]
    assert not missing, missing


def test_skill_size_caps_and_the_new_names():
    skills = REPO / "skills"
    assert len((skills / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")) <= 2000
    assert len((skills / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")) <= SDD_CAP
    brain = (skills / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
    assert "Human orchestrator: I approve the plan before it runs" in brain and "AI orchestrator: asks only major questions while planning, then hands off" in brain
    assert brain.count("AskUserQuestion") >= 1 and "ONE `AskUserQuestion` call" in brain
    plans = (skills / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
    assert "**Human orchestrator**" in plans and "**AI orchestrator**" in plans and "A human approves" not in plans
    assert "hands off: the user pre-approved" not in plans  # a chosen AI orchestrator still asks major questions while planning


# ---------------------------------------------------------------- review plan (human orchestrator, phase 1)

import hashlib  # noqa: E402

REVIEW = REPO / "skills" / "writing-plans" / "review-plan.md"


def review_file(tmp_path, name="plan.review.md"):
    f = tmp_path / "docs" / "plans" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# Review plan\n\n## Summary\nA word counter.\n", encoding="utf-8")
    return f


def test_approve_review_records_path_and_sha256(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    reply(tmp_path, f)
    cp = orch(tmp_path, "approve", "--by", "erin", "--review", f)
    assert cp.returncode == 0, cp.both
    st = json.loads((tmp_path / ".superlite" / "orchestrator.json").read_text(encoding="utf-8"))
    assert st["review_path"] == str(f).replace("\\", "/") and st["review_sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert st["approved"] is True and st["approved_by"] == "erin"
    assert f"review plan {st['review_path']}" in cp.out


def test_approve_review_with_a_missing_file_fails_and_does_not_approve(tmp_path):
    orch(tmp_path, "set", "human")
    cp = orch(tmp_path, "approve", "--review", tmp_path / "nope.review.md")
    assert cp.returncode == 2 and "review plan not found" in cp.err
    st = json.loads((tmp_path / ".superlite" / "orchestrator.json").read_text(encoding="utf-8"))
    assert st["approved"] is False and "review_path" not in st
    assert "awaiting approval" in orch(tmp_path, "status").out


def state(tmp_path):
    return json.loads((tmp_path / ".superlite" / "orchestrator.json").read_text(encoding="utf-8"))


def test_approve_refuses_without_review(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    reply(tmp_path, f)  # even with a fresh approving reply
    cp = orch(tmp_path, "approve", "--by", "frank")
    assert cp.returncode == 2 and "write the review plan first" in cp.err
    assert state(tmp_path)["approved"] is False


def test_approve_refuses_without_any_human_reply(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    cp = orch(tmp_path, "approve", "--review", f)
    assert cp.returncode == 3 and cp.err.strip() == NO_REPLY
    assert state(tmp_path)["approved"] is False and "review_path" not in state(tmp_path)


def test_approve_refuses_a_stale_reply_older_than_the_review_plan(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    reply(tmp_path, f, offset_ms=-60_000)  # the human said approve before the plan was (re)written
    cp = orch(tmp_path, "approve", "--review", f)
    assert cp.returncode == 3 and "no human approval reply since the review plan was written" in cp.err
    assert "no qualifying human reply yet" in orch(tmp_path, "status", "--review", f).out


def test_approve_refuses_a_non_approving_reply(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    reply(tmp_path, f, approves=False, text="change the storage to a database")
    cp = orch(tmp_path, "approve", "--review", f)
    assert cp.returncode == 3 and state(tmp_path)["approved"] is False


def test_approve_accepts_a_fresh_approving_reply_after_a_changing_one(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    reply(tmp_path, f, approves=False, offset_ms=1000, text="use files")
    reply(tmp_path, f, approves=True, offset_ms=9000, text="approve")
    cp = orch(tmp_path, "approve", "--by", "gina", "--review", f)
    assert cp.returncode == 0, cp.both
    assert state(tmp_path)["approved"] is True and state(tmp_path)["approved_by"] == "gina"


def test_status_says_whether_an_approving_reply_exists(tmp_path):
    orch(tmp_path, "set", "human")
    assert "no approving human reply yet" in orch(tmp_path, "status").out
    f = review_file(tmp_path)
    assert "no qualifying human reply yet" in orch(tmp_path, "status", "--review", f).out
    reply(tmp_path, f)
    out = orch(tmp_path, "status", "--review", f).out
    assert "awaiting approval" in out and "approving reply at" in out


def test_ai_mode_needs_no_reply_and_no_approve(tmp_path):
    p = mech_plan(tmp_path, 2)
    orch(tmp_path, "set", "ai")
    for name, cp in gated(tmp_path, p).items():
        assert BLOCK not in cp.both, (name, cp.both)
    assert orch(tmp_path, "approve").returncode == 2  # approve is for human mode only


def test_status_and_finish_show_the_review_plan_path(tmp_path):
    orch(tmp_path, "set", "human")
    f = review_file(tmp_path)
    reply(tmp_path, f)
    orch(tmp_path, "approve", "--review", f)
    path = str(f).replace("\\", "/")
    assert f"review plan {path}" in orch(tmp_path, "status").out
    assert f"review plan {path}" in finish(tmp_path)
    p = mech_plan(tmp_path, 2)
    assert BLOCK not in run(SCRIPTS / "plan_tools.py", "lint", "--stable", "--plan", p, cwd=tmp_path).both  # the gate opened


REQUIRED_SECTIONS = ["## Summary", "## What you will get", "## What will be built", "## How it fits together", "## How it gets built",
                     "## Decisions you can change", "## Risks", "## Out of scope", "## How we will know it works", "## Rough time and cost"]


def test_review_plan_template_names_every_required_section_and_has_two_diagrams():
    text = REVIEW.read_text(encoding="utf-8")
    for h in REQUIRED_SECTIONS:
        assert h in text, h
    assert text.count("```mermaid") >= 2  # the example carries both diagrams
    for word in ("Size (S/M/L)", "at most 12 nodes", "rough until", "Do not", "Do\n", "five-line summary", "sha256", "**Review plan:**"):
        assert word in text, word


def test_skills_mention_both_phases_and_keep_their_caps():
    skills = REPO / "skills"
    plans = (skills / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
    brain = (skills / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
    sdd = (skills / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    for text in (plans, brain):
        assert ".review.md" in text and "review-plan.md" in text and "approve --review" in text
    assert "**Review plan:**" in plans and "machine plan" in plans and "machine plan" in brain
    assert "approve --review PATH" in sdd and "review plan" in sdd
    assert len((skills / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")) <= 2000 and len(sdd) <= SDD_CAP
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "review plan" in readme.lower() and "You approve first" in readme


def test_texts_state_the_hard_rule_plain_text_approval_and_the_small_form():
    skills = REPO / "skills"
    plans = (skills / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
    brain = (skills / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
    sdd = (skills / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")
    ref = (skills / "subagent-driven-development" / "orchestrator.md").read_text(encoding="utf-8")
    review = REVIEW.read_text(encoding="utf-8")
    for text in (plans, brain):
        assert "not AskUserQuestion" in text and "END THE TURN" in text
        assert "Reply approve to start, or tell me what to change" in text
    assert "Nothing is built, dispatched or written except this file" in plans and "small requests too" in plans
    assert "even a small request" in brain and "approved review plan" in (skills / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")
    assert "before the human's approving reply" in sdd and "plain text" in sdd
    assert "human-replies.jsonl" in ref and "exit 3" in ref and "The hard rule (human mode)" in ref
    assert "## One-page form (small requests)" in review and "Reply approve to start" in review
    assert "the orchestrator-choice" not in brain  # the choice itself stays an AskUserQuestion batch
    assert "ONE `AskUserQuestion` call" in brain and "Human orchestrator: I approve the plan before it runs" in brain


def test_readme_has_the_human_mode_sentence():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "nothing is built, dispatched or written (except the review plan) until you reply approve" in readme


SDD_SKILL = REPO / "skills" / "subagent-driven-development" / "SKILL.md"
SDD_CAP = 12990  # the one size cap of the SDD SKILL.md (#555); other tests pin phrases, never its size

# Every phrase another test in tests/scripts/ pins in the SDD SKILL.md, so a trim fails here first (#555).
# A test that pins a new SKILL.md phrase adds it here too.
SDD_PINNED = (
    # test_agent_mcp_tools.py
    "approved before dispatch",
    "background agents",
    "inherit the session's MCP tools",
    # test_docs_b10.py
    "`WAIT FOR T0:`",
    "hold Tn --reason R",
    "`<plan>.build-report.md`",
    # test_docs_b102.py
    "`description`",
    "sl:<repo>-<worktree>-<id>",
    "fleet name",
    # test_docs_b32_sdd.py
    "`unstable=Tn <reason>; rerun sl lint --stable`",
    "then run the printed `wait:` line in the foreground (never as a background command) and end the turn only after it reports)",
    "prints `Tn <sha>`, `Tn FAILED` or `Tn: no change since its last checkpoint <sha>` (one task: the SHA)",
    "`depends on unstable <ids>`",
    "once those ids are committed",
    # test_docs_b72_skills.py
    "Dispatched tasks are frozen: keep blocks byte-identical, else lint says `FROZEN:` (restore them). `MISSED TARGET:` warns",
    "Ask only for an irreversible, destructive, security-sensitive or outward step (merge, push, publish), or a plan so broken all paths are guesses.",
    # test_docs_b95_sdd.py
    "--for-review",
    "--package",
    "review: Tn",
    "--full",
    "review:",
    "--dismiss",
    # test_docs_b98_sdd.py
    "uses that run's summary",
    "  G[all tasks reviewed + committed] --> ST[run_tests --full, wait]\n  ST --> PK[packet from its summary]\n",
    "- Every test run is `run_tests ... --background`; wait in Final review 2 and 5.",
    # test_docs_contract.py
    "run_tests --fast PATHS --task Tn --background",
    "--also F --ruling \"...\"",
    "trees clean",
    "zsh",
    "Read <abs>/.superlite/prime.md",
    "reply READY",
    "never paste",
    "**Wave0:** none",
    "/scripts/sl",
    "\"$SL\" fleet on",
    "before the first dispatch",
    "`fleet.md`",
    "in-process",
    # test_fleet_hard_stop.py
    "report BLOCKED",
    "never in-process",
    # test_fleet_roles_skill.py
    "Fleet mode (user asks): `\"$SL\" fleet on` before the first dispatch, then `fleet.md`: every role a worker, never in-process; missing or BLOCKED: report BLOCKED.",
    # test_fleet_wait_report_b91.py
    "fast path too",
    # test_implementer_red_prime_b65.py
    "status DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED, files, test result, `Red run:` line, open questions\"",
    # test_isolation_wording.py
    "ROOT=<abs run root>",
    "Run root: a worktree",
    "worktree ensure",
    "`**Worktree:** none`",
    # test_adapter_and_packet.py
    # B112 (#549, #559, #562, #567)
    '"$SL" incident add --agent coordinator --file <task file> --line 0 --context "BLOCKED Tn: <why>"',
    '"$SL" plan_tools packet --inline --spec <spec.md> --base <start-sha>',
    "UI screenshots (`.png`, `.jpg`, `.jpeg`) go in `.superlite/render/` first",
    '"$SL" fleet spawn --role final-reviewer --plan $PLAN',
    "--label FR<round> --plan $PLAN",
    # main follow-up (#556)
    "verify command (batch: one per member, each with its own `--task Tn` and PATHS, run on its own: `<abs sl> run_tests --fast PATHS --task Tn --background`",
    # main follow-up (#558)
    "Write `.superlite/render/index.md` too, one `- <file>: <caption>` line per current screenshot",
    # B117 (#574)
    "`WARNING: TESTS: no test command resolves`",
    "`\"$SL\" testcmd --propose`",
    "`**Tests:** fast cmd=`",
    "before DONE remove what you created (simulators, build folders, temp files)",
    "`-derivedDataPath` folders in your session scratchpad",
    "`--module-cache-hours 24`",
    "refuse below 20 GB free (warn below 50)",
)


def sdd_text() -> str:
    return SDD_SKILL.read_text(encoding="utf-8")


def test_sdd_skill_cap_and_every_pinned_phrase():
    sdd = sdd_text()
    assert len(sdd) <= SDD_CAP, len(sdd)
    missing = [p for p in SDD_PINNED if p not in sdd]
    assert not missing, missing


def test_sdd_final_review_names_fleet_reviewer_inline_packet_and_render():
    final = sdd_text().split("## Final review", 1)[1].split("## Measure and budget", 1)[0]
    step2 = next(ln for ln in final.splitlines() if ln.startswith("2. "))
    step3 = next(ln for ln in final.splitlines() if ln.startswith("3. "))
    assert '"$SL" plan_tools packet --inline --spec <spec.md> --base <start-sha>`, no `--plan`' in step2
    assert "(inline: `--inline --spec" not in step2
    assert "`.superlite/render/`" in step2 and "`## Render evidence`" in step2
    assert "Fleet on (inline builds too)" in step3 and "Fleet off: Agent `superlite:final-reviewer`" in step3
    assert step3.index("fleet spawn --role final-reviewer") < step3.index("fleet send Wn --brief") < step3.index("Fleet off")
    assert "Start `superlite:final-reviewer` then" not in step3


def test_sdd_incident_line_is_a_full_call():
    line = next(ln for ln in sdd_text().splitlines() if ln.startswith("- Incidents:"))
    assert "`--file`, `--line`, `--context` required" in line and "`incident add --help` lists the kinds" in line


def test_sdd_incident_example_runs(tmp_path):
    log = tmp_path / "incidents.jsonl"
    cp = run(SCRIPTS / "incident.py", "add", "--agent", "coordinator", "--file", "src/a.py", "--line", "0",
             "--context", "BLOCKED T3: no fixture", "--log", log)
    assert cp.returncode == 0, cp.both
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert (entry["agent"], entry["file"], entry["line"], entry["context"]) == ("coordinator", "src/a.py", 0, "BLOCKED T3: no fixture")


def test_fleet_md_inline_names_the_reviewer_worker():
    t = (REPO / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    assert "An inline build without a taskgraph starts no implementer worker (tell the user); its final reviewer is still a worker (`SKILL.md` Final review 3)." in t
    assert "starts no worker: tell the user" not in t


def test_no_other_test_holds_the_sdd_cap():
    here = Path(__file__).resolve().parent
    stale = [p.name for p in sorted(here.glob("test_*.py")) if p.name != Path(__file__).name and "<= 11700" in p.read_text(encoding="utf-8")]
    assert not stale, stale
