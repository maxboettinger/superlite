"""metrics.py reads the final status from SubagentHandback (#90: first_time_pass was null in every history row).

Claude Code delivers a subagent's report as a `SubagentHandback` tool call (`input.message`), not as assistant
text; plain text after it (background-task notices) is not delivered. The transcripts below copy the entry shape
of a real 2026-11 run: prime READY after a handback-enforce nudge, coordinator task messages, api-request-blob
replays of earlier turns, a BLOCKED report and a retry in the same agent, trailing text after the last report."""
from __future__ import annotations

import json

from test_plan_tools import SCRIPTS, run

METRICS = SCRIPTS / "metrics.py"
SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"
USAGE = {"input_tokens": 10, "output_tokens": 50, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200}
COORD = "The coordinator sent a message while you were working:\n"
ENFORCE = ("[handback-send-enforce] Your report has not been delivered. Call SubagentHandback({message: <your full report>}) "
           "now; the call ends your run.")
REMINDER = ("<system-reminder>\nYour final report is delivered through SubagentHandback: when your work is complete, call "
            "SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step.\n</system-reminder>")
NOTICE = "[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated background-task event, NOT a message from the user."


class Transcript:
    def __init__(self, model):
        self.model, self.lines, self.n = model, [], 0

    def _ts(self):
        s = len(self.lines) * 5
        return f"2026-11-03T16:{50 + s // 60:02d}:{s % 60:02d}.000Z"

    def user(self, text):
        self.lines.append({"type": "user", "timestamp": self._ts(), "message": {"role": "user", "content": text}})
        return self

    def _assistant(self, block):
        self.n += 1
        self.lines.append({"type": "assistant", "timestamp": self._ts(),
                           "message": {"role": "assistant", "id": f"msg{self.n}", "model": self.model, "usage": USAGE, "content": [block]}})

    def text(self, text):
        self._assistant({"type": "text", "text": text})
        return self

    def tool(self, name, inp=None):
        self._assistant({"type": "tool_use", "id": f"tu{self.n + 1}", "name": name, "input": inp or {"command": "x"}})
        self.lines.append({"type": "user", "timestamp": self._ts(),
                           "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"tu{self.n}", "content": "ok"}]}})
        return self

    def handback(self, message):
        return self.tool("SubagentHandback", {"message": message})

    def blob(self, message):
        """A request log entry that replays an earlier handback; not an assistant turn."""
        self.lines.append({"type": "api-request-blob", "message": {"content": [
            {"type": "tool_use", "id": "replay", "name": "SubagentHandback", "input": {"message": message}}]}})
        return self

    def write(self, path):
        path.write_text("\n".join(json.dumps(x) for x in self.lines) + "\n", encoding="utf-8")
        return path


def sonnet_t1(path):
    done = ("Status: DONE\n\nFiles changed:\n- Sources/DesignSystem/ChartValueFormat.swift\n\n"
            "Test: `Scripts/test.sh -only-testing:DesignSystemTests` gave `Test run with 121 tests in 24 suites passed`.")
    return (Transcript(SONNET).user("Read /work/app/.superlite/prime.md, then reply READY").user(REMINDER)
            .text("READY").user(ENFORCE).handback("READY")
            .user(COORD + "Task T1 value format and chart tokens.\n\nSUPERLITE=/work/superlite\nPLAN=/work/app/docs/plans/plan.md")
            .blob("READY").tool("Read").tool("Edit").tool("Bash")
            .text("The suite passed on the first run.").handback(done).write(path))


def haiku_t6(path):
    blocked = ("T6 area keywords. Status: BLOCKED (red step not observed; implementation not started).\n"
               "Test command: run twice; both exit 65 with build errors in another owner's file (T9 in progress).")
    concerns = ("T6 area keywords. Status: DONE_WITH_CONCERNS.\nRed: before the implementation, 6 areaKeywords cases failed.\n"
                "Green: Test run with 100 tests in 13 suites passed.\nConcern: the patterns compile on each call.")
    return (Transcript(HAIKU).user("Read /work/app/.superlite/prime-haiku.md, then reply READY").user(REMINDER)
            .text("READY").user(ENFORCE).handback("Status: DONE (prime only, no task assigned yet).\nFiles changed: none.")
            .user(COORD + "Task T6 area keywords (full task block below).\n\nSUPERLITE=/work/superlite")
            .tool("Edit").tool("Bash").handback(blocked)
            .user(COORD + "T6 retry: the blocker was T9's half-written file. Continue T6 exactly as specified.")
            .blob(blocked).tool("Bash").text("Red confirmed: 6 cases fail. Now the implementation.").tool("Edit").tool("Bash")
            .handback(concerns)
            .user(NOTICE).text("The background wait from the T6 retry has finished, and nothing else is pending. "
                               "T6 was already delivered with DONE_WITH_CONCERNS, so no further action is needed.")
            .write(path))


def setup(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    a, b = sonnet_t1(tmp_path / "a.jsonl"), haiku_t6(tmp_path / "b.jsonl")
    t = 1_793_724_780_000
    rows = [{"ev": "launch", "t": t, "agent_id": "a1", "type": "superlite:implementer", "model": SONNET, "desc": "Implementer for T1"},
            {"ev": "launch", "t": t + 1, "agent_id": "b1", "type": "superlite:implementer-haiku", "model": HAIKU, "desc": "Haiku implementer for T6"},
            {"ev": "stop", "t": t + 3_000, "agent_id": "a1", "type": "superlite:implementer", "transcript": str(a), "last": "READY"},
            {"ev": "stop", "t": t + 5_000, "agent_id": "b1", "type": "superlite:implementer-haiku", "transcript": str(b), "last": "READY"},
            {"ev": "stop", "t": t + 125_000, "agent_id": "a1", "type": "superlite:implementer", "transcript": str(a), "last": ""},
            {"ev": "stop", "t": t + 290_000, "agent_id": "b1", "type": "superlite:implementer-haiku", "transcript": str(b),
             "last": "The background wait from the T6 retry has finished, and nothing else is pending."}]
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return sl


def records(tmp_path):
    sl = setup(tmp_path)
    cp = run(METRICS, "--dir", sl, "--json", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return {r["task"]: r for r in json.loads(cp.out)}


def test_status_comes_from_the_handback_report(tmp_path):
    r = records(tmp_path)
    assert r["T1"]["status"] == "DONE" and r["T1"]["first_time_pass"] is True


def test_text_after_the_last_handback_does_not_hide_the_report(tmp_path):
    r = records(tmp_path)
    assert r["T6"]["status"] == "DONE_WITH_CONCERNS"


def test_an_earlier_blocked_report_in_the_same_task_is_not_a_first_time_pass(tmp_path):
    r = records(tmp_path)
    assert r["T6"]["first_time_pass"] is False


def test_an_unlabelled_status_on_the_first_line_counts(tmp_path):
    """About a quarter of real reports start `T4 gallery: DONE` or `T19: DONE_WITH_CONCERNS`, without `Status:`."""
    sl = tmp_path / ".superlite"
    sl.mkdir()
    rows = []
    for aid, tid, report in (("c1", "T4", "T4 gallery: DONE\nFiles changed: Sources/Gallery/ComponentGallery.swift"),
                             ("d1", "T19", "T19: DONE_WITH_CONCERNS\n\nFiles changed (all under /work/app):\n- Sources/PunchCard.swift"),
                             ("e1", "T20", "READY. I read prime.md and have no task yet.\nNothing is DONE yet.")):
        path = (Transcript(HAIKU).user("Read /work/app/.superlite/prime-haiku.md, then reply READY").user(ENFORCE).handback("READY")
                .user(COORD + f"Task {tid} (full task block below).").tool("Edit").handback(report).write(tmp_path / f"{aid}.jsonl"))
        rows += [{"ev": "launch", "t": 1, "agent_id": aid, "type": "superlite:implementer-haiku", "model": HAIKU, "desc": f"Haiku implementer for {tid}"},
                 {"ev": "stop", "t": 2, "agent_id": aid, "type": "superlite:implementer-haiku", "transcript": str(path), "last": ""}]
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cp = run(METRICS, "--dir", sl, "--json", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    r = {x["task"]: x for x in json.loads(cp.out)}
    assert (r["T4"]["status"], r["T4"]["first_time_pass"]) == ("DONE", True)
    assert (r["T19"]["status"], r["T19"]["first_time_pass"]) == ("DONE_WITH_CONCERNS", True)
    assert (r["T20"]["status"], r["T20"]["first_time_pass"]) == (None, None)  # a token past the first line is no status
