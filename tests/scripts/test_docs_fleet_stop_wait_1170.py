"""#1170: docs/fleet.md and the skill's fleet.md state the B343 rules where `fleet stop` and `fleet wait` are described: `fleet stop --all` and an id-less `fleet wait` keep to the --plan run of a shared session fleet while `fleet off` stops every run's workers (#1164), and `fleet wait` skips a stop record from before the send and holds a task-notification turn's stop for 3 s (#1165)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
SKILL = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

DOCS_STOP = ("- `fleet stop W1` or `fleet stop --all` closes workers and drops each worker's `worker-<Wn>` tree unless a live process marks it busy. "
             "`--all` stops only the `--plan` run's workers, also in a session fleet that several runs share; explicit ids stop a worker of any run (#1164). "
             "A worker belongs to the run its record names: a remote worker's `<run>/remote/<wid>`, else its launch's `SUPERLITE_FLEET_PARENT_DIR` (a lead belongs to its parent run) "
             "or `SUPERLITE_STATE_DIR`, else its `state_dir`; a record that names none counts for every run. "
             "The workspace closes once no local worker of any run is live, so `--all` leaves it open while another run's workers still run.")
DOCS_OFF = "- `fleet off` stops the workers of every run the session fleet serves, not only the `--plan` run's (#1164), and turns fleet mode off."
DOCS_WAIT = ("Without worker ids `fleet wait` waits only for the `--plan` run's busy workers, also in a session fleet that several runs share; explicit ids reach a worker of any run (#1164). "
             "A stop record older than the latest message sent to the worker answers an earlier turn: when the worker's transcript holds a sender message stamped after the stop's `t` "
             "(both on the worker's clock; a whole-second `t`, the stop hook's `date +%s000` fallback, counts as `t` + 999 ms), `fleet wait` skips that stop and keeps waiting. "
             "A stop that ended a task-notification turn is held for 3 s (`NOTE_MS`) before it counts as the reply, so a send queued behind the notification can still land (#1165). "
             "`fleet status` (`reported`) and `fleet report` read a stop record by the same rule.")
SKILL_WAIT = ("In a session fleet that several runs share, a wait without worker ids takes only the `--plan` run's busy workers; explicit ids reach any run's (#1164). "
              "A stop record older than the latest message sent to the worker answers an earlier turn: `fleet wait` skips it and keeps waiting, "
              "and it holds a stop that ended a task-notification turn for 3 s before it counts it as the reply, so a queued send can still land (#1165).")
SKILL_STOP = "`fleet stop --all` stops only the `--plan` run's workers, also in a session fleet that several runs share; `fleet off` stops every run's workers (#1164)."


def _line(text, prefix):
    hits = [ln for ln in text.splitlines() if ln.startswith(prefix)]
    assert len(hits) == 1, prefix
    return hits[0]


def test_docs_stop_line_keeps_the_run():
    assert _line(DOCS, "- `fleet stop W1` or `fleet stop --all` closes workers") == DOCS_STOP
    assert "(`--all` also closes the workspace)" not in DOCS


def test_docs_off_line_takes_every_run():
    assert _line(DOCS, "- `fleet off` stops") == DOCS_OFF + " It writes its state first and closes the workspace last, so it is safe to run from inside the fleet's own workspace."


def test_docs_wait_line_names_run_and_stale_stop():
    assert _line(DOCS, "- `fleet wait [--timeout 540000]").endswith(" " + DOCS_WAIT)
    assert DOCS.count(DOCS_WAIT) == 1


def test_skill_wave_wait_names_run_and_stale_stop():
    para = _line(SKILL, "Wait once per wave:")
    assert para.endswith("so a lead's workers and main's are waited for apart. " + SKILL_WAIT)
    assert SKILL.count(SKILL_WAIT) == 1


def test_skill_stop_names_run_and_off():
    para = _line(SKILL, "`\"$SL\" fleet status` lists workers")
    assert para.endswith("runs before `trees clean` (no-op without fleet mode). " + SKILL_STOP)
    assert SKILL.count(SKILL_STOP) == 1


def test_documented_rules_match_the_code():
    fleet, io = (SCRIPTS / "fleet.py").read_text(encoding="utf-8"), (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8")
    assert "every or fio.of_run(sd, v)] if all_" in fleet  # --all keeps to the run, every takes all runs
    assert "stop(sd, all_=True, every=True, keep_workspace=True)" in fleet  # fleet off
    assert "if v.get(\"state\") == \"busy\" and of_run(sd, v)]" in io  # an id-less wait keeps to the run
    assert "return r is None or r.resolve() == Path(sd).resolve()" in io  # a record naming no run counts for every run
    assert 'env.get("SUPERLITE_FLEET_PARENT_DIR") or env.get("SUPERLITE_STATE_DIR") or w.get("state_dir")' in io
    assert "NOTE_MS = 3000" in io
    assert "t_ms + 999 if t_ms % 1000 == 0" in io
    assert "fio.stop_turn(" in fleet and "_ended_stop(sd, x, w)" in fleet  # fleet status and fleet report
