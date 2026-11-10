"""B72 (#426, #429): writing-plans states the Probe one-text-argument rule; SDD SKILL.md names orchestrator takeover; the package reviewer names the run_tests next: cue."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WP = (ROOT / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
SDD = (ROOT / "skills" / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")
PR = (ROOT / "agents" / "package-reviewer.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

PROBE = "for example `call=minisheet.Workbook.get · run=python -m minisheet · serve=minisheet.server.create_server`. Use `call=` for libraries, `run=` for CLIs, `serve=` for servers. `call=` must name a Produces of this plan with exactly one required parameter, because each probe passes one text argument (a `str`): a method's `self` does not count, every other parameter needs a default, and a method's class must build with no arguments. Anything else fails lint with `PROBE: call=<target> takes N required parameters; probes pass one text argument` (`Workbook.set(ref, raw)` takes two) or `PROBE: call=<target> is not a Produces of this plan`. A package without such a function leaves `call=` out: `run=` or `serve=` when it has a CLI or server, else `**Probe entry:** none (<why>)`, and its Review Focus cases become named tests in the owning task. No agent writes adapters."
TAKEOVER = " Resuming another session's run: `\"$SL\" orchestrator takeover --plan $PLAN` first."
FROZEN = "Dispatched tasks are frozen: keep blocks byte-identical, else lint says `FROZEN:` (restore them). `MISSED TARGET:` warns"
STOP = "Ask only for an irreversible, destructive, security-sensitive or outward step (merge, push, publish), or a plan so broken all paths are guesses."
NEXT = "- The run prints a `next:` cue and, as its last line, that `wait:` line; a turn ended before the wait reports reaches the coordinator with no test result."


def test_writing_plans_states_the_probe_rule():
    assert PROBE in WP
    assert "call=minisheet.Workbook.set" not in WP
    assert "Workbook.get(ref: str) -> Value" in WP


def test_probe_messages_match_the_code():
    lint = (SCRIPTS / "plan_tools.py").read_text(encoding="utf-8")
    assert 'f"PROBE: call={target} takes {counts[0]} required parameters; probes pass one text argument"' in lint
    assert 'f"PROBE: call={target} is not a Produces of this plan"' in lint
    pt = (SCRIPTS / "pt_review.py").read_text(encoding="utf-8")
    assert "obj = getattr(parent(), obj.__name__)" in pt and "return obj(text)" in pt


def test_sdd_names_takeover_and_keeps_its_cap():
    line = next(ln for ln in SDD.splitlines() if ln.startswith("- Run root:"))
    assert line.endswith("in `.git/info/exclude` itself." + TAKEOVER)
    assert FROZEN in SDD and STOP in SDD.splitlines()
    assert "a real change is a follow-up" not in SDD and "names the task to unblock first" not in SDD
    budget = next(ln for ln in SDD.splitlines() if ln.startswith("`lint` and `dispatch` print `budget:` lines"))
    assert budget.endswith("then `commit_task` and finish.")
    assert len(SDD) <= 11700
    assert '"takeover"' in (SCRIPTS / "orchestrator.py").read_text(encoding="utf-8")


def test_package_reviewer_names_the_next_cue():
    lines = PR.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("- Focused tests, in the background:"))
    assert lines[i + 1] == NEXT
    assert 'WAIT_CUE = "next: ' in (SCRIPTS / "run_tests.py").read_text(encoding="utf-8")
