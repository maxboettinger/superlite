#!/usr/bin/env python3
"""Herdr fleet CLI: workers are Claude Code sessions in Herdr panes, one per pane.

    fleet.py on [--accounts A,B] [--plan P] | off | status [--all]
    fleet.py spawn [--role R] [--tier T] --plan P | stop [IDS...] [--all]
    fleet.py spawn --for-dispatch --plan P    (one dispatch round: dispatch, spawn, send)
    fleet.py spawn --role lead --plan P [--brief F] [--label L] [--wait]: a lead for the plan P in P's own worktree, its own session, fleet and run (#906); --plan names the lead's plan, the spawning fleet is the current directory's run
    fleet.py spawn --for-review Tn [Tm ...] | --package X --plan P    (write the review brief, start a package-reviewer, send it)
    fleet.py report IDS... [--plan P]    (print a worker's last report, or a report by label; read-only)
    fleet.py collect WID [--plan P]    (collect a remote write worker's late snapshot from its saved report again; exit 0 collected, 3 still BLOCKED, 2 refused: #984)
    fleet.py send | keys | wait     (delegated to fleet_io)
    fleet.py run --layer headless|tui|evals     (delegated to fleet_layer)
    fleet.py restore [--plan P]     (after a Herdr restart: delegated to fleet_restore)
    fleet.py resume WID --text T [--plan P]     (continue a stopped one-turn worker's session: delegated to fleet_resume)

Roles: implementer (default), fixer, package-reviewer, final-reviewer, research, checker, writer (see fleet_roles). Exit 2 with
`error: ...` on stderr for an unknown role or tier.
MCP (#576): implementers, fixers and package reviewers get the servers their project names through a generated `--mcp-config`; a server that fails its check is left out with one stderr line.
Exit 3 with a `BLOCKED: ...` line on stdout when a worker cannot start. `--for-dispatch` prints one
`Wn Tn[,Tm] sent` line per worker, `BLOCKED: Tn[,Tm] not sent (<reason>)` for a line that got no worker
(the other lines still go out; exit 3), `QUEUED: Tn[,Tm] not sent (machine busy ...); ...` for a fresh line the machine
gate refused while a worker of the fleet is busy (no wait, no exit 3; the next round sends it, #916); the Wave 0 line
starts a haiku worker and sends it `briefs/wave0.md`.
Every subcommand but name first moves this session's fleet into its folder (#580).
`--plan P` (or `--plan=P`) is checked first, for every subcommand: a path that is neither file nor folder, or whose state folder cannot be
created, prints `error: --plan P: <reason>; ...` on stderr and exits 2, creating nothing (#372).
`spawn --brief F [--label L] [--wait [--timeout T]]` spawns, sends the brief and optionally waits in one call; a failed send stops the worker (`BLOCKED: Wn L not sent (...)`, exit 3) (#578).
A worker whose pane is still no shell after the retry is closed and started once more in a fresh pane (`NoShell`, #551).
`status` probes each ready or busy worker's agent: a gone one is marked dead (`W1 dead`, hidden after) with its fresh-spawn line, a busy one whose turn ended shows `reported` (#579).
`report W` reads a busy worker's ended but uncollected turn from its transcript, read-only (#579).
A start that fails with `not an available shell` (a freed pane) is retried once after SHELL_PAUSE_S (`start_on_shell`).
`spawn --for-dispatch` also stops the ready implementers an earlier dispatch dropped from pool.json (#424).
`spawn --for-dispatch` sends no task to a worker fleet.json marks busy, such as one still answering a `send --text` (dispatch leaves it out of the idle agents) (#553).
A stalled prime waits up to STALL_WAIT_MS for a late start, then is resent once; a start that stays slow is retried once on another account (#428).
`--for-dispatch` ends with one `review: Tn (<why>); run ... fleet spawn --for-review Tn --plan P` line per committed task that matches a review reason and has no review yet (#422).
A primed worker whose pane shows the folder trust dialog gets Down, Enter and the prime once more; one-turn roles and leads check the screen once after the start; a dialog that stays open is named in the BLOCKED line (#514).
`spawn --for-dispatch|--for-review|--package` accept the run folder as `--plan`: it becomes the plan file stable.json, pool.json or plan.md names, else exit 2 (#508).
While the run's fleet.json says off, `spawn` (both forms) starts nothing: `BLOCKED: fleet is off in <state dir>; run sl fleet on [--plan P] first ...`, exit 3 (#355).
`stop` sends no `/exit` to a lean worker (its pane close ends it) and keeps `/exit` for a lead (#930); a plain `status` in a linked worktree adds a `worktree:` line when that worktree's own fleet disagrees on on/off with the folder it read (#904).
`stop` drops the worker's tree `worker-<id>` unless a live process marks it busy (#614).
While the budget is paused (spend above the cap), every `spawn` that names a `--plan` refuses: `BLOCKED: fleet spawn: budget: paused: ...`, exit 3, before any pane.
`spawn` (not `--for-dispatch`, which dispatch gates itself) refuses on a nearly full disk: `BLOCKED: fleet spawn: disk: ...`, exit 3; below the warn level it warns on stderr (#614). A local spawn from a launchd session other than Aqua, in a project that drives a Mac app, prints one `fleet: warning: launchd session ...` stderr line (#798).
`sl fleet restore` re-launches every worker and lead of the run after a Herdr restart, each resuming its own Claude session; `status` names it after a worker found dead (#577).
`spawn --for-review|--package ... --note FILE` appends FILE to the generated review brief under `## Coordinator notes` (#604).
`spawn --role writer --brief F` needs an `Output: <file>` line in F: the writer may write only that file, inside the project or the run folder (#604).
A remote dispatch write worker gets its pool.json entry, busy on its task, and `--for-dispatch` re-adds a lost one and drops a taskless one first, so a task is never sent twice (#1057).
A worker whose spawner pins GH_CONFIG_DIR (a sealed golden lead) starts with the lead's `--settings <state>/gh-seal-settings.json` and `--plugin-dir <this checkout>` (#1049).
`spawn --brief F` (every role but lead) refuses with exit 2 before any pane when F lies outside the project, the run folder and the plugin skills folder, or when F (with the plan's Global constraints) or a review spawn's `--note` names an existing path outside the project, the run folder and the plugin skills folder outside fenced code blocks; system folders such as /dev and /usr do not count (#1015).
`spawn --brief F` (every role but lead) refuses with exit 2 before any pane when F names the worker's own report file (`<run>/fleet/reports/<label>.md` or `.json`): fleet wait overwrites it with the worker's reply (#1094).
A session's private state folder (`<superlite home>/sessions/<sid>.d/.superlite`) spawns its workers in the launch folder's git root (`$CLAUDE_PROJECT_DIR`, else the cwd; `state.project`), and its brief check judges paths against that project (#1088).
A machine the project's `.superlite/placement.json` excludes is never placed, and `fleet spawn --machine` naming it exits 2 (#1096).
"""

# Complexity notation:
# w = workers in the fleet, a = accounts, e = account entries, s = screen lines, p = panes of a tab, R = lines of one dispatch round
import argparse  # O(1)
import contextlib  # O(1)
import importlib  # O(1)
import io  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import signal  # O(1)
import sys  # O(1)
import threading  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import accounts as ac  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import fleet_waits  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import machine_load as ml  # noqa: E402 | O(1)
import pool  # noqa: E402 | O(1)
import routing  # noqa: E402 | O(1)
import run_config  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

TRUST = "Yes, I trust this folder"  # O(1)
SHELL_PAUSE_S = 3.0  # O(1)
SHELL_MSG = "not an available shell"  # O(1)
PASS_THROUGH = ("CLAUDE_CODE_PLUGIN_CACHE_DIR", "GH_CONFIG_DIR")  # O(1) GH_CONFIG_DIR: a sealed golden run's empty gh folder reaches the lead and its workers
GH_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")  # O(1)
GH_SEAL_FILE = "gh-seal-settings.json"  # O(1)
PLUGIN_ROOT = Path(__file__).resolve().parents[3]  # O(1) the checkout these scripts belong to


def gh_seal_env(base_env, gh_dir=None):  # O(1) the settings env of a sealed spawner: {} unless it pins GH_CONFIG_DIR; a token it carries is left out
    if not base_env.get("GH_CONFIG_DIR"):  # O(1)
        return {}  # O(1)
    return {**{k: "" for k in GH_TOKENS if not base_env.get(k)}, "GH_CONFIG_DIR": gh_dir or base_env["GH_CONFIG_DIR"]}  # O(1)


def write_gh_seal(sd, base_env):  # O(1) writes the seal settings file through a temp file; None when the spawner is not sealed
    env = gh_seal_env(base_env)  # O(1)
    if not env:  # O(1)
        return None  # O(1)
    p = Path(sd) / GH_SEAL_FILE  # O(1)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")  # O(1)
    tmp.write_text(json.dumps({"env": env}, indent=2) + "\n", encoding="utf-8")  # O(1)
    os.replace(tmp, p)  # O(1) a lead and its workers share the file: never torn
    return p  # O(1)


def plugin_dir(root=None):  # O(1) the plugin checkout a sealed spawner loads: root or PLUGIN_ROOT when it holds .claude-plugin/plugin.json, else None
    p = Path(root) if root is not None else PLUGIN_ROOT  # O(1)
    return p if (p / ".claude-plugin" / "plugin.json").is_file() else None  # O(1)
SLOW_MSG = "timed out waiting for app response"  # O(1)
STALL_WAIT_MS = 30000  # O(1) herdr's own prompt window is a fixed 5 s; a slow start gets this long to show working or blocked
LEAN_FLAGS = ("--strict-mcp-config", "--no-chrome", "--disable-slash-commands")  # O(1)
LEAN_DENY = ("Artifact", "ArtifactComments", "ArtifactData", "ListAgents", "ReadNotifications", "ReportFindings")  # O(1)
SCREEN_ROWS = 1000  # O(1) spawn reads the whole pane: the fullscreen TUI pins the prompt to the bottom, READY and the trust dialog sit above it


def _pause(s):  # tests swap it | O(s)
    time.sleep(s)  # O(s)


def _hc_call(name, *args):  # a herdr_client function an older double may lack: its result, None when missing or failing | O(1)
    fn = getattr(hc, name, None)  # O(1)
    if fn is None:  # O(1)
        return None  # O(1)
    try:  # O(1)
        return fn(*args)  # O(1)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def _store_session(sd, wid, name):  # the agent's Claude session id into its fleet.json record; never raises | O(w)
    try:  # O(1)
        sid = _hc_call("agent_session", name)  # O(1)
        if not sid:  # O(1)
            return  # O(1)
        with fs.locked(sd):  # O(1) plus wait
            data = fs.load(sd)  # O(w)
            if wid in data["workers"]:  # O(1)
                data["workers"][wid]["session"] = sid  # O(1)
                fs.save(sd, data)  # O(w)
    except Exception:  # noqa: BLE001 | O(1)
        pass  # O(1)


OUT_TOKEN = re.compile(r"(?<![^\s`'\"(\[{<=,>])(?:file://)?((?:/|~/|\.\./)[\w.@%+#~-][\w.@%+#~/-]*)")  # O(1)
SYSTEM_TOP = {"dev", "bin", "sbin", "usr", "etc", "System", "Library", "opt", "Applications", "proc", "sys"}  # O(1)


def main_checkout(project):  # the main checkout's root when PROJECT is a linked worktree, else None; reads .git files, no git process (#1067) | O(1)
    try:  # O(1)
        dot = Path(project) / ".git"  # O(1)
        if not dot.is_file():  # O(1)
            return None  # O(1)
        m = re.match(r"gitdir:\s*(\S.*)", dot.read_text(encoding="utf-8").strip())  # O(1)
        if not m:  # O(1)
            return None  # O(1)
        gitdir = (Path(project) / m.group(1)).resolve()  # O(1)
        cd = gitdir / "commondir"  # O(1)
        if not cd.is_file():  # a submodule gitdir has no commondir: not a linked worktree | O(1)
            return None  # O(1)
        common = (gitdir / cd.read_text(encoding="utf-8").strip()).resolve()  # O(1)
        return common.parent if common.name == ".git" and common.is_dir() else None  # O(1)
    except OSError:  # O(1)
        return None  # O(1)


def outside_paths(text, project, sd, skills=None):  # path tokens of TEXT that exist (or sit in an existing folder) outside project, sd and the skills folder, first-seen, deduplicated (#1015) | O(len + t)
    if skills is None:  # O(1)
        import fleet_roles  # noqa: E402 | O(1)
        skills = fleet_roles.SKILLS  # O(1)
    if state.private(sd):  # a private folder is judged against the launch project (#1088) | O(d)
        project = state.project(sd)  # O(d)
    bases = [Path(b).resolve() for b in (project, sd, skills)]  # O(1)
    root = main_checkout(project)  # the main checkout's root itself passes (#1067) | O(1)
    out = []  # O(1)
    keep, fence = [], None  # O(1)
    for line in text.splitlines(keepends=True):  # fenced code blocks (diffs, logs) are content, not input paths | O(len)
        s = line.strip()  # O(1)
        if fence is None:  # O(1)
            if s.startswith("```") or s.startswith("~~~"):  # O(1)
                fence = (s[0], len(s) - len(s.lstrip(s[0])))  # O(1)
            else:  # O(1)
                keep.append(line)  # O(1)
        elif s.startswith(fence[0] * fence[1]) and not s.strip(fence[0]):  # closing fence: same char, at least as long | O(1)
            fence = None  # O(1)
    text = "".join(keep)  # O(len)
    for m in OUT_TOKEN.finditer(text):  # O(t)
        tok = m.group(1).rstrip("./")  # O(len)
        if not tok or tok in out:  # O(t)
            continue  # O(1)
        p = os.path.expanduser(tok)  # O(len)
        if p.startswith("../"):  # O(1)
            p = os.path.join(str(project), p)  # O(len)
        p = os.path.normpath(p)  # O(len)
        if p.startswith("//"):  # O(1)
            p = "/" + p.lstrip("/")  # O(len)
        parts = p.split("/")  # O(len)
        if len(parts) > 1 and parts[1] in SYSTEM_TOP:  # O(1)
            continue  # O(1)
        parent = os.path.dirname(p)  # O(1)
        if not (os.path.exists(p) or (parent != "/" and os.path.isdir(parent))):  # O(1)
            continue  # O(1)
        real = Path(p).resolve()  # O(len)
        if root is not None and real == root:  # O(1)
            continue  # O(1)
        if any(real == b or b in real.parents for b in bases):  # O(1)
            continue  # O(1)
        out.append(tok)  # O(1)
    return out  # O(1)


def outside_error(what, where, paths, sd):  # the one-line refusal naming at most five outside paths (#1015) | O(1)
    named = ", ".join(paths[:5]) + (f" and {len(paths) - 5} more" if len(paths) > 5 else "")  # O(1)
    return (f"error: {what} {where} names paths outside the project, the run folder and the plugin skills folder: {named}; "  # O(1)
            f"a worker cannot read them: copy each file into {sd}/briefs/ and name the copy, or drop the path (#1015)")  # O(1)


def report_refusal(sd, brief, label, project):  # the refusal when BRIEF names the worker's own report file, which fleet wait overwrites (#1094), else None | O(file)
    rid = label.split(",")[0]  # O(1)
    rd = Path(sd).resolve() / "fleet" / "reports"  # O(1)
    reserved = {rd / f"{rid}.md", rd / f"{rid}.json"}  # O(1)
    text = Path(brief).read_text(encoding="utf-8")  # O(file)
    rx = r"(?:file://)?([^\s`'\"()\[\]{}<>,;:=]*fleet/reports/" + re.escape(rid) + r"\.(?:md|json))(?![\w-]|\.\w)"  # O(1)
    for m in re.finditer(rx, text):  # O(len) iterations
        tok = m.group(1)  # O(1)
        p = Path(os.path.expanduser(tok))  # O(1)
        cands = [p] if p.is_absolute() else [Path(project) / tok, Path(sd) / tok, Path(sd).parent / tok]  # O(1)
        if any(c.resolve() in reserved for c in cands):  # O(1)
            return (f"error: brief {Path(brief).resolve()} names {tok}: fleet wait saves the worker's reply as {rd}/{rid}.md and {rd}/{rid}.json "  # O(1)
                    f"and would overwrite a report the worker writes there; name another file, such as {rd}/{rid}-full.md (#1094)")  # O(1)
    return None  # O(1)


def writer_output(brief, root, sd):  # the one file a writer brief names on its `Output:` line, as an absolute path inside root or sd | O(file)
    text = Path(brief).read_text(encoding="utf-8")  # O(file)
    m = re.search(r"^\s*Output:\s*`?([^`\s]+)`?\s*$", text, re.M)  # O(file)
    if not m:  # O(1)
        raise ValueError(f"writer brief {Path(brief).resolve()} names no Output: <file> line")  # O(1)
    raw = m.group(1)  # O(1)
    out = Path(os.path.normpath(Path(raw) if os.path.isabs(raw) else Path(root) / raw))  # O(len)
    real = out.resolve()  # O(len)
    for base in (Path(root), Path(sd)):  # O(1)
        b = base.resolve()  # O(len)
        if real == b or b in real.parents:  # resolved containment only: a symlink cannot lead out | O(len)
            return real  # O(1)
    raise ValueError(f"writer output {out} is outside {root} and {sd}")  # O(1)


def start_on_shell(name, pane, argv):  # one start; a freed pane is not a shell yet: one pause, one more start | O(1)
    try:  # O(1)
        hc.start_agent(name, pane, argv)  # O(1)
        return ""  # O(1)
    except hc.HerdrError as e:  # O(1)
        if SHELL_MSG not in (getattr(e, "message", "") or ""):  # O(len)
            raise  # O(1)
    _pause(SHELL_PAUSE_S)  # O(1)
    try:  # O(1)
        hc.start_agent(name, pane, argv)  # O(1)
    except hc.HerdrError as e:  # O(1)
        e.retried = "; retried once"  # O(1)
        raise  # O(1)
    return "; retried once"  # O(1)


def worker_env(sd, wid, agent, config_dir, base_env):  # O(1)
    env = {"SUPERLITE_FLEET_WORKER": wid, "SUPERLITE_FLEET_AGENT": agent,  # O(1)
           "SUPERLITE_STATE_DIR": str(Path(sd).resolve()), "SUPERLITE_FINAL_REVIEW": "off"}
    if not ac.is_default_dir(config_dir, base_env):  # the default dir is chosen by leaving the variable unset | O(1)
        env["CLAUDE_CONFIG_DIR"] = config_dir  # O(1)
    for k in PASS_THROUGH:  # O(1)
        if base_env.get(k):  # O(1)
            env[k] = base_env[k]  # O(1)
    return env  # O(1)


class NoShell(Exception):  # a start whose pane stayed no shell after the pause: the caller starts once more in a fresh pane | O(1)
    def __init__(self, wid, account, why):  # O(1)
        super().__init__(why)  # O(1)
        self.wid, self.account, self.why = wid, account, why  # O(1)


class _Slow(Exception):  # O(1)
    """A start that stayed slow on the first try: `spawn` runs it once more on another account."""

    def __init__(self, wid, account, why):  # O(1)
        super().__init__(why)  # O(1)
        self.wid, self.account, self.why = wid, account, why  # O(1)


class _SignedOut(_Slow):  # O(1)
    """A start that stands on Claude Code's sign-in screen: the account is marked, `spawn` runs it once more on another account."""


SIGNED_OUT_TTL_MS = 900000  # O(1) a signed-out account stays out of `choose_account` this long
SIGNED_OUT_WHY = "signed out: Claude Code sign-in screen"  # O(1)


def mark_signed_out(sd, account):  # O(w)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        data["signed_out"] = {**(data.get("signed_out") or {}), account: int(time.time() * 1000)}  # O(a)
        fs.save(sd, data)  # O(w)


def signed_out_accounts(sd, now_ms=None):  # accounts marked within SIGNED_OUT_TTL_MS | O(w)
    now = int(time.time() * 1000) if now_ms is None else now_ms  # O(1)
    return {a for a, t in (fs.load(sd).get("signed_out") or {}).items() if isinstance(t, (int, float)) and now - t < SIGNED_OUT_TTL_MS}  # O(a)


def _slow(e):  # O(len)
    return e.code in ("agent_prompt_stalled", "timeout") or SLOW_MSG in (getattr(e, "message", "") or "")  # O(len)


def _late_prime(name):  # O(1) plus herdr wait: the state of a prime that started after herdr's stall window, else None
    try:  # O(1)
        st = hc.wait_state(name, ["working", "blocked"], STALL_WAIT_MS)  # O(1)
    except hc.HerdrError as e:  # O(s)
        if e.code != "timeout":  # O(1)
            raise  # O(1)
        return "idle" if _is_ready(hc.read_screen(name, SCREEN_ROWS)) else None  # O(s)
    if st == "working":  # O(1)
        return hc.wait_state(name, ["idle", "done", "blocked"], 180000)  # O(1)
    return "blocked" if st == "blocked" else None  # O(1)


def _keep(sd, wid, why, screen, label):  # O(s)
    """Keep the screen of a worker that did not start and log it."""
    if screen is not None:  # O(1)
        d = Path(sd) / "fleet" / "screens"  # O(1)
        d.mkdir(parents=True, exist_ok=True)  # O(1)
        (d / f"{wid}.txt").write_text(screen, encoding="utf-8")  # O(s)
    try:  # O(1)
        import incident  # O(1)
        incident.append(Path(sd) / "incidents.jsonl", [incident.make_entry(  # O(1)
            "fleet.py", 0, f"{label}: {why}"[:150], agent=wid, kind="workaround")])
    except Exception:  # noqa: BLE001 | O(1)
        pass  # O(1)


def _blocked(sd, wid, account, why, screen=None, named=True):  # O(s)
    """Print the BLOCKED line, keep the screen, exit 3."""
    _keep(sd, wid, why, screen, "fleet spawn blocked")  # O(s)
    print(f"BLOCKED: {wid} account {account} {why}" if named else f"BLOCKED: {wid} {why}")  # O(1)
    raise SystemExit(3)  # O(1)


def _launch_line(sd, wid, agent, model, account, pane):  # O(1)
    line = {"ev": "launch", "t": int(time.time() * 1000), "agent_id": wid, "type": f"fleet:{agent}", "model": model, "desc": f"fleet worker {account} pane {pane}"}  # O(1)
    with open(Path(sd) / "metrics.jsonl", "a", encoding="utf-8") as f:  # O(1)
        f.write(json.dumps(line) + "\n")  # O(1)


def _register_pool(sd, wid, tier, account, current=None, machine=None):  # O(w)
    with fs.locked(sd):  # two parallel spawns must not drop each other's entry; callers hold no fs lock here | O(1) plus wait
        p = Path(sd) / "pool.json"  # O(1)
        data = pool.load(p)  # O(w)
        ag = pool.add(data, wid, tier, current)  # O(w)
        ag.update({"backend": "herdr", "account": account, **({"machine": machine} if machine else {})})  # O(1)
        pool.save(p, data)  # O(w)


def _sync_remote_pool(sd):  # O(w): -> (added ids, dropped ids) of this run's remote implementers' pool entries (#1057)
    sd = Path(sd)  # O(1)
    added, dropped = [], []  # O(1)
    with fs.locked(sd):  # O(1) plus wait
        mine = {}  # O(1)
        for wid, w in fs.workers(sd).items():  # O(w) iterations
            if w.get("machine") and w.get("role", "implementer") == "implementer":  # O(1)
                if Path(w.get("state_dir") or sd / "remote" / wid).resolve() == (sd / "remote" / wid).resolve():  # O(1)
                    mine[wid] = w  # O(1)
        if not mine:  # O(1)
            return added, dropped  # O(1)
        p = sd / "pool.json"  # O(1)
        data = pool.load(p)  # O(w)
        for ag in list(data.get("agents") or []):  # O(w) iterations
            if ag.get("id") in mine and not pool.currents(ag):  # a remote write worker takes one task; commit_task cleared it | O(1)
                pool.remove(data, ag["id"])  # O(w)
                dropped.append(ag["id"])  # O(1)
        for wid, w in mine.items():  # O(w) iterations
            if w.get("state") in ("busy", "blocked") and w.get("task") and pool.find(data, wid) is None:  # O(w)
                ag = pool.add(data, wid, w.get("tier") or "sonnet", w["task"])  # O(w)
                ag.update({"backend": "herdr", "account": w.get("account"), "machine": w["machine"]})  # O(1)
                added.append(wid)  # O(1)
        if added or dropped:  # O(1)
            pool.save(p, data)  # O(w)
    return added, dropped  # O(1)


def _pool_drop(sd, wid):  # O(w); caller already holds fs.locked(sd)
    p = Path(sd) / "pool.json"  # O(1)
    if p.exists():  # O(1)
        data = pool.load(p)  # O(w)
        if pool.remove(data, wid):  # O(w)
            pool.save(p, data)  # O(w)


def _trust_open(screen):  # O(s)
    """True when the folder trust dialog is on screen and no READY line is (a ready pane that shows the text is not blocked)."""
    return TRUST in screen and not _is_ready(screen)  # O(s)


def _accept_trust(name):  # O(1)
    hc.send_keys(name, ["Down", "Enter"])  # O(1)
    hc.wait_state(name, ["idle"], 60000)  # O(1)


def _is_ready(screen):  # O(s)
    """True when a screen line is just READY (TUI bullet and box characters aside); the echoed prime prompt does not count."""
    for line in screen.splitlines():  # O(s)
        t = line.strip(" \t\u23fa\u25cf\u2022\u25e6\u00b7\u25aa\u2502\u2503\u256d\u256e\u2570\u256f\u2500\u2501")  # O(1)
        if "prime" in t.lower() and ".md" in t.lower() or "reply" in t.lower():  # O(1)
            continue  # O(1)
        if t == "READY":  # O(1)
            return True  # O(1)
    return False  # O(1)


def choose_account(sd, model, env, avoid=None, lead=False):  # O(a * e + w) plus herdr and usage calls
    """The account a new worker starts on: (account, its config dir, the claude-profile account other sessions count it on).

    A lead (`lead`, or SUPERLITE_FLEET_ROLE=lead in os.environ) skips accounts at or above `lead_weekly_max` while another is usable.
    Exit 3 with a `BLOCKED: ...` line when no account has headroom or no config dir is known."""
    sd = Path(sd)  # O(1)
    data = fs.load(sd)  # O(w)
    usage, listing = ac.read_usage(env), ac.read_listing(env)  # O(1) plus subprocess time
    entries = data.get("accounts") or [a["name"] for a in (usage.get("accounts") or listing.get("accounts") or [])] or ["current"]  # O(a)
    skip = {avoid} if isinstance(avoid, str) else set(avoid or ())  # a str is one name | O(a)
    entries = [e for e in entries if ac.entry_name(e) not in skip]  # the accounts of a slow first try or a signed-out pair | O(a)
    out = signed_out_accounts(sd)  # O(a)
    entries = [e for e in entries if ac.entry_name(e) not in out]  # accounts that showed the sign-in screen lately | O(a)
    allowed = [ac.entry_name(e) for e in entries]  # config dir paths go by basename | O(a)
    entry_of = {ac.entry_name(e): e for e in entries}  # O(a)
    alias = ac.aliases(listing, entries, env)  # `current` and config dir entries -> the claude-profile account they use | O(a * e)
    own = {fs.name_of(sd, k, v) for k, v in data["workers"].items()}  # herdr agents of this run: counted below from fleet.json, not from the agent list | O(w)
    try:  # O(1)
        machine = fs.live_by_account(hc.agents(), own)  # live workers of every other session on the machine: account -> count | O(a)
    except hc.HerdrError:  # no agent list: count this run only | O(1)
        machine = {}  # O(1)
    running = {}  # live workers of this run per account: a stopped or blocked worker holds no pane | O(1)
    for v in data["workers"].values():  # O(w)
        if v.get("state") not in ("stopped", "blocked"):  # O(1)
            base = (v.get("account") or "").split("@")[0] or v.get("account")  # a remote record holds `account@label`: it counts on the account | O(1)
            running[base] = running.get(base, 0) + 1  # O(1)
    for n in allowed:  # O(a)
        if machine.get(alias.get(n, n)):  # accounts nobody else uses stay out of the dict | O(1)
            running[n] = running.get(n, 0) + machine[alias.get(n, n)]  # O(1)
    lead = lead or os.environ.get("SUPERLITE_FLEET_ROLE") == "lead"  # O(1)
    limit, over = None, {}  # account -> weekly_all percent, for the accounts at or above the lead cap | O(1)
    if lead:  # O(1)
        import backlog_cap  # noqa: PLC0415 | O(1)
        import history  # noqa: PLC0415 | O(1)
        limit = backlog_cap.machine_cfg(history.home())["lead_weekly_max"]  # O(k)
    if limit is not None:  # O(1)
        by = {u.get("name"): u for u in usage.get("accounts") or []}  # O(a)
        over = {n: ac._pct(by[alias.get(n, n)], "weekly_all") for n in allowed if alias.get(n, n) in by and ac._pct(by[alias.get(n, n)], "weekly_all") >= limit}  # O(a * l)
    ok = [n for n in allowed if n not in over]  # O(a)
    account = ac.pick_account(usage, ok, running, model, alias)  # O(a)
    if account is None:  # a path entry or `current` unknown to the usage report has no usage data, not a verdict; an aliased one has, and it said no | O(a)
        known = {u.get("name") for u in usage.get("accounts") or []}  # O(a)
        account = next((ac.entry_name(e) for e in entries if ac.entry_name(e) in ok and (ac.is_path(e) or e == "current") and ac.entry_name(e) not in known and ac.entry_name(e) not in alias), None)  # O(a)
    if account is None and over:  # every usable account is at the cap: the plain pick, with a note | O(a)
        account = ac.pick_account(usage, allowed, running, model, alias)  # O(a)
        if account in over:  # O(1)
            print(f"{account}: weekly_all {over[account]:g}% >= lead_weekly_max {limit:g}%; no account under it", file=sys.stderr)  # O(1)
    if account is not None:  # one stderr line naming the accounts left out and why (#909) | O(a * l)
        line = ac.skip_line(usage, allowed, model, alias, sorted(out))  # O(a * l)
        if line:  # O(1)
            print(line, file=sys.stderr)  # O(1)
    if account is None:  # O(1)
        why = ac.reasons(usage, allowed, model, alias)  # O(a)
        unread = bool(why) and not out and all(r.split(": ", 1)[-1].startswith("usage unreadable") for r in why)  # O(a) #917
        print("BLOCKED: usage unreadable for every account (claude-profile usage failed); rerun when sl accounts shows a reading" if unread else "BLOCKED: no account with headroom")  # O(1)
        for r in why:  # O(a)
            print(r)  # O(1)
        for n in sorted(out):  # O(a)
            print(f"{n}: signed out (Claude Code sign-in screen)")  # O(1)
        raise SystemExit(3)  # O(1)
    cdir = ac.account_dir(listing, entry_of.get(account, account), env)  # O(a)
    if cdir is None:  # O(1)
        hint = "" if listing.get("accounts") else " (claude-profile list unavailable; pass a config dir path instead)"  # O(1)
        print(f"BLOCKED: no config dir for account {account}{hint}")  # O(1)
        raise SystemExit(3)  # O(1)
    return account, cdir, alias.get(account, account)  # O(1)


def open_pane(sd, wid, cwd, env, record, machine=None):  # O(w + p) plus herdr calls
    """Open the pane of worker `wid` (workspace, split or tab), save `record` plus its pane id as the worker, return the pane id.

    With `machine` the pane opens inside `hc.on(machine)`, in that machine's own workspace (`machines.<label>` in fleet.json),
    split from the newest open pane of that machine's workers only; a local spawn never splits from a remote pane.
    A HerdrError propagates; the caller reports it."""
    sd = Path(sd)  # O(1)
    with fs.locked(sd), (hc.on(machine) if machine else contextlib.nullcontext()):  # older doubles have no `on` | O(1)  # layout decision and herdr call are one step; fs write helpers lock too, so save directly | O(1) plus wait
        data = fs.load(sd)  # O(w)
        for attempt in (0, 1):  # a split from a pane closed outside fleet fails once; the retry uses another pane | O(1)
            live = [v for v in data["workers"].values() if v.get("state") != "stopped" and v.get("machine") == machine]  # this machine's workers only | O(w)
            src = [v["pane_id"] for v in live if v.get("state") != "blocked"]  # panes still open | O(w)
            slot = (data.get("machines") or {}).get(machine) or {} if machine else data  # where this machine's workspace id is kept | O(1)
            if not slot.get("workspace_id") or not src:  # O(1)
                ws, pane = hc.create_workspace(data.get("label") or "sl:fleet", cwd, env)  # O(1)
                if machine:  # O(1)
                    data.setdefault("machines", {})[machine] = {"workspace_id": ws, "root_pane": pane}  # O(1)
                else:  # O(1)
                    data.update({"workspace_id": ws, "root_pane": pane})  # O(1)
                break  # O(1)
            bad, how = src[-1], "tab"  # the pane a failing herdr call points at: the layout read first, then the split | O(1)
            try:  # O(1)
                panes = [x for x in hc.pane_layout(src[-1]) if x["pane_id"] in src]  # the tab of the newest open pane, minus panes that are not this run's | O(p)
                how, at = fs.place(panes)  # O(p)
                if how != "tab":  # O(1)
                    bad = at  # O(1)
                    pane = hc.split_pane(at, how, cwd, env)  # O(1)
            except hc.HerdrError:  # O(1)
                if attempt:  # O(1)
                    raise  # O(1)
                for k, v in data["workers"].items():  # the pane is dead: stop its worker, drop it from the pool | O(w)
                    if v.get("pane_id") == bad and v.get("state") != "stopped" and v.get("machine") == machine:  # O(1)
                        v.update({"state": "stopped", "task": None})  # O(1)
                        _pool_drop(sd, k)  # we hold fs.locked(sd); pool.json uses the same lock | O(w)
                fs.save(sd, data)  # O(w)
                continue  # O(1)
            if how == "tab":  # a full or short tab: the next worker opens a new one in the same workspace | O(1)
                pane = hc.create_tab(slot["workspace_id"], cwd, env)[1]  # O(1)
            break  # O(1)
        data["workers"][wid] = {**record, "pane_id": pane}  # O(1)
        fs.save(sd, data)  # O(w)
    return pane  # O(1)


def _retry_account(sd, model, env, avoid, lead=False):  # O(a * e + w): another account than `avoid`, else the same one
    try:  # O(1)
        with contextlib.redirect_stdout(io.StringIO()):  # O(1)
            return choose_account(sd, model, env, avoid={avoid}, lead=lead)  # O(a * e + w)
    except SystemExit as e:  # no other account has headroom | O(1)
        if e.code != 3:  # O(1)
            raise  # O(1)
    return choose_account(sd, model, env, lead=lead)  # O(a * e + w)


def claude_json(config_dir, env=None):  # O(1) the .claude.json of a worker account: next to the default dir's home, else inside the dir
    base = os.environ if env is None else env  # O(1)
    if ac.is_default_dir(config_dir, base):  # O(1)
        return Path(base.get("HOME") or os.path.expanduser("~")) / ".claude.json"  # O(1)
    return Path(config_dir) / ".claude.json"  # O(1)


def lean_argv(argv, mcp_config=None, deny=()):  # O(n) a copy of argv with the lean flags before the deny list and the lean names added to it, each once
    a = list(argv)  # O(n)
    flags = [f for f in LEAN_FLAGS if f not in a]  # O(n)
    if mcp_config and "--mcp-config" not in a:  # the servers the worker keeps (#576) | O(1)
        at = flags.index("--strict-mcp-config") + 1 if "--strict-mcp-config" in flags else len(flags)  # O(1)
        flags[at:at] = ["--mcp-config", str(mcp_config)]  # O(1)
    extra = [*LEAN_DENY, *(d for d in deny if d not in LEAN_DENY)]  # O(n)
    if "--disallowedTools" not in a:  # O(n)
        return a + flags + ["--disallowedTools", *extra]  # O(n)
    i = a.index("--disallowedTools")  # O(n)
    j = next((k for k in range(i + 1, len(a)) if a[k].startswith("--")), len(a))  # the deny list ends at the next option | O(n)
    names = [n for n in extra if n not in a[i + 1:j]]  # O(n)
    return a[:i] + flags + a[i:j] + names + a[j:]  # O(n)


def _live_names():  # names of the live herdr agents on this machine; no agent list: none | O(a)
    try:  # O(1)
        return {x.get("name") for x in hc.agents() if x.get("name")}  # O(a)
    except hc.HerdrError:  # O(1)
        return set()  # O(1)


def live_workers(sd):  # workers of this run that hold a pane: every state but stopped and blocked | O(w)
    return sum(1 for v in fs.workers(sd).values() if v.get("state") not in ("stopped", "blocked"))  # O(w)


def spawn(sd, plan, tier, project, cfg=None, env=None, role="implementer", over=False, machine_wait=100.0, output=None, brief=False, plain=True, machine=None, task=None, remote_brief=None, bounds=None):  # O(a * e + w) plus herdr calls
    """One worker; a start that stays slow is retried once on another account.
    Implementers, fixers and package reviewers keep the MCP servers their project names or the stack default (`xcode` for an Xcode project), each checked first (#576).
    Every worker starts lean (#377): no MCP server (`--strict-mcp-config`; the exception is the line above), Chrome, skills or slash commands; Artifact, ListAgents, ReadNotifications and ReportFindings denied (LEAN_FLAGS, LEAN_DENY)."""
    if machine:  # a worker on a saved Herdr machine: its own gates and life, no local machine gate | O(1)
        import fleet_remote_worker as frw  # noqa: E402 | O(1) lazy: it imports this module
        rkw = {**({"task": task, "plan": str(plan)} if task else {}), **({"brief": remote_brief} if remote_brief else {})}  # a write worker's task or brief; a research worker passes none | O(1)
        w = frw.spawn(sd, role, tier, project, machine, cfg, **rkw)  # O(w) plus remote calls
        if task and role == "implementer":  # a dispatch write worker is busy on its task from the start, like a local one (#1057) | O(1)
            _register_pool(sd, w["id"], tier, w.get("account"), current=task, machine=machine)  # O(w)
        return w  # O(1)
    rank = 0 if role in ("package-reviewer", "final-reviewer") else 1  # a waiting review goes before a waiting implementer (#902) | O(1)
    busy = ml.gate(f"fleet spawn ({role})", machine_wait, over, rank=rank, bounds=bounds, run_workers=(lambda: live_workers(sd)) if bounds else None)  # the first attempt only; the retry below is the same spawn | O(wait)
    if busy:  # O(1)
        print(f"BLOCKED: {BUSY_HEAD}{busy}{BUSY_TAIL}")  # O(1)
        raise SystemExit(3)  # O(1) before any pane
    kw = {**({"output": output} if output is not None else {}), **({"brief": True} if brief else {}), **({"plain": False} if not plain else {})}  # only the non-default flags, so an older _spawn signature still fits | O(1)
    try:  # O(1)
        return _spawn(sd, plan, tier, project, cfg, env, role, None, **kw)  # O(a * e + w)
    except (_Slow, NoShell) as first:  # _SignedOut is a _Slow  # O(1)
        return _spawn(sd, plan, tier, project, cfg, env, role, first, **kw)  # O(a * e + w)


def with_model(argv, model):  # a copy of argv pinned to `model`: replace the value of --model, else insert after --agent NAME, else prepend | O(n)
    out = list(argv)  # O(n)
    if "--model" in out and out.index("--model") + 1 < len(out):  # O(n)
        out[out.index("--model") + 1] = model  # O(1)
    elif "--agent" in out and out.index("--agent") + 1 < len(out):  # O(n)
        i = out.index("--agent") + 2  # O(1)
        out[i:i] = ["--model", model]  # O(n)
    else:  # O(1)
        out[:0] = ["--model", model]  # O(n)
    return out  # O(1)


def fleet_roles_text(w):  # the brief-only preface for a worker without prime, else "" | O(1)
    import fleet_roles  # noqa: E402 | O(1)
    return fleet_roles.BRIEF_ONLY if w.get("brief_only") else ""  # O(1)


def _spawn(sd, plan, tier, project, cfg, env, role, after, output=None, brief=False, plain=True):  # O(a * e + w) plus herdr calls
    import fleet_roles  # noqa: E402 | O(1)
    sd = Path(sd)  # O(1)
    base = dict(os.environ) if env is None else env  # O(env)
    cfg = cfg or routing.load_cfg()  # O(file)
    launch = fleet_roles.launch(role, tier, cfg, output=output)  # a ValueError (unknown role or tier) reaches `main` | O(file)
    agent, model = launch["agent"], launch["model"]  # O(1)
    pool_tier = model  # the routing tier the pool files the worker under, whatever the run config pins | O(1)
    prime = "prime-haiku.md" if model == "haiku" else "prime.md"  # O(1)
    if launch["prime"] and not (sd / prime).is_file() and brief:  # a brief-only task outside a plan run: no prime, one turn, no pool | O(1)
        launch = fleet_roles.launch(role, tier, cfg, output=output, brief=True)  # O(file)
    if launch["prime"] and not (sd / prime).is_file():  # no pane, account or worker id for a worker that cannot read its prime | O(1)
        flag = "--tier haiku " if model == "haiku" else ""  # O(1)
        more = ", or pass --brief FILE for a brief-only task outside a plan run" if plain else ""  # O(1)
        print(f"BLOCKED: no {sd.resolve() / prime}; run build_prime {flag}--plan PLAN first{more}")  # O(1)
        raise SystemExit(3)  # O(1)
    solo = role == "implementer" and not launch["prime"]  # O(1)
    fresh = isinstance(after, NoShell)  # O(1)
    tail = "" if after is None else f"; retried in a fresh pane after {after.wid}" if fresh else f"; retried after {after.wid} on {after.account}"  # O(1)
    rcfg = run_config.active(sd, project)  # the run's snapshot, else the layered default | O(file)
    pin = rcfg["workers"].get(role)  # a per-role model of the run config | O(1)
    if pin:  # O(1)
        model = pin  # O(1) the prime file above was chosen from the tier's own model
    account, cdir, shared = choose_account(sd, model, base) if after is None or fresh else _retry_account(sd, model, base, after.account)  # O(a * e + w)
    if fresh:  # O(1)
        print(f"{after.wid} {after.why}; retrying in a fresh pane", file=sys.stderr)  # O(1)
    elif after is not None:  # O(1)
        print(f"{after.wid} account {after.account} {after.why}; retrying on account {account}", file=sys.stderr)  # O(1)
    wid = fs.next_id(sd)  # O(w)
    name = fs.agent_name(sd, wid, taken=_live_names())  # herdr rejects `W1`; every herdr agent call below uses this name | O(a)
    wenv = {**worker_env(sd, wid, agent, cdir, base), **fleet_roles.env(role)}  # O(1)
    if rcfg["cache_ttl"].get("workers"):  # O(1)
        wenv["CLAUDE_CODE_PROMPT_CACHE_TTL"] = rcfg["cache_ttl"]["workers"]  # O(1)
    cwd = str(project)  # O(1)
    kept, names, path = {}, [], None  # O(1)
    try:  # a lookup or check error never stops a spawn: the worker stays lean (#576) | O(1)
        import fleet_mcp  # noqa: E402 | O(1)
        import mcp_check  # noqa: E402 | O(1)
        found, notes = fleet_mcp.servers(role, project, claude_json(cdir, base))  # O(n + f)
        for n, d in found.items():  # O(k)
            why = mcp_check.check(n, d, sd, project)  # O(1)
            if why:  # O(1)
                notes.append(f"mcp: {n} left out: {why}")  # O(1)
            else:  # O(1)
                kept[n] = d  # O(1)
        for note in notes:  # O(k)
            print(f"{wid} {note}", file=sys.stderr)  # O(1)
        names = sorted(kept)  # O(k)
        path = fleet_mcp.write_config(sd, kept) if names else None  # O(k)
    except Exception as e:  # noqa: BLE001 | O(1)
        kept, names, path = {}, [], None  # O(1)
        print(f"{wid} mcp: none: {e}", file=sys.stderr)  # O(1)
    argv = lean_argv(with_model(launch["argv"], pin) if pin else launch["argv"], path, fleet_mcp.deny(names) if names else ())  # O(n)
    argv = fleet_roles.skills_read(argv, project=project)  # O(n) the plugin skill files are readable (#905)
    seal = write_gh_seal(sd.resolve(), base)  # O(1)
    if seal is not None:  # O(1)
        argv += ["--settings", str(seal)]  # O(1)
        if plugin_dir() is not None:  # O(1)
            argv += ["--plugin-dir", str(plugin_dir())]  # O(1)
    note = fleet_mcp.usage_note(names, project) if names else ""  # O(1)
    if note:  # O(1)
        argv += ["--append-system-prompt", note]  # O(1)
    try:  # a state dir outside the project (a worktree run) is not readable by default | O(1)
        sd.resolve().relative_to(Path(project).resolve())  # O(len)
    except ValueError:  # O(1)
        argv += ["--add-dir", str(sd.resolve())]  # O(1)
    record = {"name": name, "account": account, "agent": agent, "tier": tier or model, "model": model, "state": "starting", "task": None, "role": role, "one_turn": launch["one_turn"],  # O(1)
              "run_config": rcfg["id"], "launch": {"argv": argv, "env": wenv, "cwd": cwd}}
    if solo:  # O(1)
        record["brief_only"] = True  # O(1)
    if names:  # O(1)
        record["mcp"] = names  # O(1)
    try:  # O(1)
        pane = open_pane(sd, wid, cwd, wenv, record)  # O(w + p)
        _INFLIGHT.update(sd=sd, wid=wid, pane=pane)  # a stop from here on blocks this worker and closes its pane (#783) | O(1)
        with contextlib.suppress(OSError):  # the registry only spreads accounts; an unwritable one must not stop a spawn | O(1)
            fs.register_agent(name, shared)  # other sessions count this worker on its claude-profile account | O(1)
    except hc.HerdrError as e:  # O(1)
        _blocked(sd, wid, account, f"startup: {e.message or e.code}{tail}")  # O(1)
    def fail(why, screen=None, named=True, slow=False, shell=False, signed_out=False):  # O(s + w)
        _INFLIGHT.clear()  # O(1)
        fs.set_state(sd, wid, "blocked")  # O(w)
        if signed_out:  # O(1)
            mark_signed_out(sd, account)  # O(w)
            why = SIGNED_OUT_WHY  # O(1)
        try:  # O(1)
            hc.close_pane(pane)  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        if signed_out and after is None:  # the caller starts it once more on another account | O(1)
            _keep(sd, wid, why, screen, "fleet spawn retry")  # O(s)
            raise _SignedOut(wid, account, why)  # O(1)
        if signed_out:  # O(1)
            var = "" if ac.is_default_dir(cdir, base) else f"CLAUDE_CONFIG_DIR={cdir} "  # O(1)
            why += f"; sign in once ({var}claude, then /login), then rerun"  # O(1)
        if slow and after is None:  # the caller starts it once more on another account | O(1)
            _keep(sd, wid, why, screen, "fleet spawn retry")  # O(s)
            raise _Slow(wid, account, why)  # O(1)
        if shell and after is None:  # the caller starts it once more in a fresh pane | O(1)
            _keep(sd, wid, why, screen, "fleet spawn retry")  # O(s)
            raise NoShell(wid, account, why)  # O(1)
        _blocked(sd, wid, account, why + tail, screen, named)  # O(s)

    def first_line(screen, e):  # O(s)
        return next((x.strip() for x in screen.splitlines() if x.strip()), e.message or e.code)  # O(s)

    st, screen, retried = "idle", "", ""  # O(1)
    try:  # O(1)
        try:  # O(1)
            retried = start_on_shell(name, pane, argv)  # O(1)
        except hc.HerdrError as e:  # O(1)
            screen = ""  # O(1)
            try:  # O(1)
                screen = hc.read_screen(name, SCREEN_ROWS)  # O(s)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
            if e.code != "agent_not_ready" or TRUST not in screen:  # O(s)
                shell = SHELL_MSG in (getattr(e, "message", "") or "")  # O(len)
                retried = getattr(e, "retried", "")  # O(1)
                fail(f"startup: {e.message if shell else first_line(screen, e)}{retried}", screen, slow=_slow(e), shell=shell)  # O(s)
            _accept_trust(name)  # O(1)
        seen = ""  # a failed read is an empty screen, as in fleet_lead | O(1)
        try:  # O(1)
            seen = hc.read_screen(name, SCREEN_ROWS)  # O(s)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        if ac.sign_in_screen(seen):  # the account is signed out (#782) | O(s)
            fail("", seen, signed_out=True)  # O(s)
        if not launch["prime"]:  # a one-turn worker may stand on the trust dialog too (#514) | O(1)
            if _trust_open(seen):  # O(s)
                _accept_trust(name)  # O(1)
        if launch["prime"]:  # a one-turn worker gets its brief as the first message, no prime | O(1)
            ask = f"Read {sd.resolve() / prime}, then reply READY"  # O(1)
            try:  # O(1)
                st = hc.prompt(name, ask, ["idle", "done", "blocked"], 180000)  # a pane on screen settles as idle, never done | O(1)
            except hc.HerdrError as e:  # O(1)
                if e.code != "agent_prompt_stalled":  # a stall is the one error a second send can fix | O(1)
                    raise  # O(1)
                st = _late_prime(name) or hc.prompt(name, ask, ["idle", "done", "blocked"], 180000)  # a late start is waited for, else resent once; a second stall is slow | O(s)
            screen = hc.read_screen(name, SCREEN_ROWS)  # O(s)
            if _trust_open(screen):  # the dialog came up after the first prime: accept it, send the same prime once more | O(s)
                _accept_trust(name)  # O(1)
                st = hc.prompt(name, ask, ["idle", "done", "blocked"], 180000)  # O(1)
                screen = hc.read_screen(name, SCREEN_ROWS)  # O(s)
    except hc.HerdrError as e:  # a failed key, wait or prime call must not leave a raw traceback | O(1)
        fail(f"startup: {e.code}: {e.message}", slow=_slow(e))  # O(1)
    if launch["prime"] and (st == "blocked" or not _is_ready(screen)):  # O(s)
        size = ""  # read before `fail` closes the pane | O(1)
        try:  # O(1)
            mine = next((x for x in hc.pane_layout(pane) if x["pane_id"] == pane), None)  # O(p)
            size = f" (pane {mine['rows']} rows, {mine['cols']} cols)" if mine else ""  # O(1)
        except (hc.HerdrError, KeyError):  # O(1)
            pass  # O(1)
        gone = "" if (sd / prime).is_file() else f"; no {sd.resolve() / prime}"  # the prime vanished while the worker started | O(1)
        if ac.sign_in_screen(screen):  # O(s)
            fail("", screen, signed_out=True)  # O(s)
        if _trust_open(screen):  # O(s)
            fail(f"no READY: the folder trust dialog is still open in {cwd}; accept it once per account (start claude there on account {account}), then rerun", screen, named=False)  # O(s)
        fail("no READY" + size + gone, screen, named=False)  # O(s)
    if launch["pool"]:  # the pool entry first: a concurrent round must not see a ready worker outside the pool | O(1)
        _register_pool(sd, wid, pool_tier, account)  # O(w)
    _store_session(sd, wid, name)  # O(w)
    fs.set_state(sd, wid, "ready")  # O(w)
    _launch_line(sd, wid, agent, model, account, pane)  # O(1)
    _INFLIGHT.clear()  # O(1)
    print(f"{wid} account={account} pane={pane} agent={agent}" + ("" if role == "implementer" else f" role={role}") + (f" mcp={','.join(names)}" if names else ""))  # O(1)
    return {"id": wid, "account": account, "pane_id": pane, "agent": agent, "model": model, "role": role, **({"brief_only": True} if solo else {})}  # O(1)


def _machine_line():  # O(p): the machine measurement as the status line; nothing while both checks are off or on any error
    try:  # O(1)
        if ml.enabled():  # O(1)
            print(ml.snapshot_text())  # O(p)
    except Exception:  # noqa: BLE001 | a status line must not fail the status | O(1)
        pass  # O(1)


BUSY_HEAD, BUSY_TAIL = "fleet spawn: ", "; rerun later, or pass --over-limit"  # O(1) the machine gate's BLOCKED reason
QUEUE_TAIL = "the next round sends it once a worker finishes, or pass --over-limit"  # O(1) #916


def _in_flight(sd):  # O(w) a worker of this fleet is busy, so a later round gets room or a worker back
    return any(v.get("state") == "busy" for v in fs.workers(sd).values())  # O(w)


def _spawn_quiet(sd, plan, tier, project, over=False, machine_wait=100.0, bounds=None, **extra):  # O(spawn) -> (worker dict, None) or (None, reason of the BLOCKED lines)
    buf = io.StringIO()  # O(1)
    try:  # spawn prints its own worker or BLOCKED line; a dispatch round reports one line per dispatch line instead | O(1)
        with contextlib.redirect_stdout(buf):  # O(1)
            return spawn(sd, plan, tier, project, over=over, machine_wait=machine_wait, plain=False, **({"bounds": bounds} if bounds else {}), **extra), None  # O(spawn)
    except SystemExit as e:  # O(1)
        if e.code != 3:  # O(1)
            raise  # O(1)
        lines = [x.strip() for x in buf.getvalue().splitlines() if x.strip()]  # O(s)
        return None, "; ".join(x[len("BLOCKED: "):] if x.startswith("BLOCKED: ") else x for x in lines) or "spawn blocked"  # O(s)


def _dropped_ready(sd):  # O(w): ready implementers pool.json no longer lists (an earlier dispatch evicted them)
    p = Path(sd) / "pool.json"  # O(1)
    if not p.exists():  # O(1)
        return []  # O(1)
    listed = {a.get("id") for a in pool.load(p).get("agents") or []}  # O(w)
    return [k for k, v in fs.workers(sd).items() if v.get("state") == "ready" and (v.get("role") or "implementer") == "implementer" and not v.get("machine") and k not in listed]  # O(w)


def _dispatch_machine(sd, plan, project, machine, lines, sl, fio):  # O(R * (spawn + send)): each ready task gets its own remote implementer
    import fleet_remote_worker as frw  # noqa: E402 | O(1) lazy
    blocked = False  # O(1)
    for tasks, decision in lines:  # O(R) iterations
        if decision.startswith("wave0") or not (decision.startswith(("fresh", "agent=", "poll"))):  # O(1)
            print(f"BLOCKED: {tasks} not sent (no remote dispatch for: {decision}; run Wave 0 without --machine)" if decision.startswith("wave0") else f"BLOCKED: {tasks} not sent (no remote dispatch for: {decision})")  # O(1)
            blocked = True  # O(1)
            continue  # O(1)
        tier = (re.search(r"\btier=(\S+)", decision) or [None, "sonnet"])[1]  # O(len)
        for t in [x for x in tasks.split(",") if x]:  # a batch line is split into single tasks | O(k)
            w, why = _spawn_quiet(sd, plan, tier, project, machine=machine, task=t)  # O(spawn)
            if why is None:  # O(1)
                try:  # O(1)
                    frw.send_task(sd, w["id"], plan, [t], sl)  # O(w + n)
                    print(f"{w['id']} {t} sent machine={machine}")  # O(1)
                    continue  # O(1)
                except (fio.hc.HerdrError, OSError, KeyError) as e:  # O(1)
                    stop(sd, [w["id"]])  # O(w)
                    why = getattr(e, "message", "") or getattr(e, "code", "") or str(e)  # O(1)
            print(f"BLOCKED: {t} not sent ({why})")  # O(1)
            blocked = True  # the next task still goes out | O(1)
    return 3 if blocked else 0  # O(1)


def _placed(sd, role, project, tier=None):  # O(w + m): the machine placement picks for a new worker, or None for local; off, or any failure, means local
    try:  # O(1)
        import fleet_placement as fp  # noqa: E402 | O(1) lazy
        if tier == "haiku" or not fp.enabled(sd):  # O(w)
            return None  # O(1)
        return fp.choose(sd, role, project)  # O(w + m)
    except Exception:  # noqa: BLE001 | placement never blocks a spawn | O(1)
        return None  # O(1)


def _unavailable(sd, machine, why):  # O(k): say the remote start failed and keep the machine out of placement for a while
    why = re.sub(r"^(BLOCKED: )?(fleet spawn: )?(machine " + re.escape(machine) + r": )?", "", why or "").strip() or "failed"  # O(len)
    import fleet_remote_account as fra  # noqa: PLC0415 | O(1) lazy
    acct = fra.signed_out_account(why)  # O(len)
    if acct:  # O(1)
        print(f"placement: account {acct} skipped on {machine} (not signed in there); local")  # O(1)
    else:  # O(1)
        print(f"placement: {machine} unavailable ({why}); local")  # O(1)
    try:  # O(1)
        import fleet_placement as fp  # noqa: E402 | O(1) lazy
        fp.skip(sd, machine, why)  # O(k)
    except Exception:  # noqa: BLE001 | O(1)
        pass  # O(1)


def _dispatch_placed(sd, plan, project, tasks, decision, sl, fio):  # O(R * (spawn + send)): tasks of a fresh or poll line that placement puts on a machine -> (tasks left for local, blocked)
    tier = (re.search(r"\btier=(\S+)", decision) or [None, "sonnet"])[1]  # O(len)
    left = []  # O(1)
    for t in [x for x in tasks.split(",") if x]:  # O(k)
        m = _placed(sd, "implementer", project, tier)  # O(w + m)
        if not m:  # O(1)
            left.append(t)  # O(1)
            continue  # O(1)
        w, why = _spawn_quiet(sd, plan, tier, project, machine=m, task=t)  # O(spawn)
        if why is not None:  # the remote start failed: this task goes local | O(1)
            _unavailable(sd, m, why)  # O(k)
            left.append(t)  # O(1)
            continue  # O(1)
        try:  # O(1)
            import fleet_remote_worker as frw  # noqa: E402 | O(1) lazy
            frw.send_task(sd, w["id"], plan, [t], sl)  # O(w + n)
            print(f"{w['id']} {t} sent machine={m}")  # O(1)
        except (fio.hc.HerdrError, OSError, KeyError) as e:  # the task did not land on the machine: it goes local like a failed start | O(1)
            try:  # O(1)
                with contextlib.redirect_stdout(io.StringIO()):  # O(1)
                    stop(sd, [w["id"]])  # O(w)
            except Exception:  # noqa: BLE001 | an unreachable host must not block the task | O(1)
                pass  # O(1)
            _unavailable(sd, m, f"{w['id']} not sent: {getattr(e, 'message', '') or getattr(e, 'code', '') or str(e)}")  # O(k)
            left.append(t)  # O(1)
    return ",".join(left), False  # a placed task never blocks: every failure sends it local | O(k)


def for_dispatch(sd, plan, project, over=False, machine_wait=100.0, machine=None, place=True, bounds=None):  # O(R * (spawn + send)): one dispatch round, a line after the other
    import dispatch as dp  # noqa: E402 | O(1) lazy: only this command needs it
    import fleet_io as fio  # noqa: E402 | O(1) lazy
    import orchestrator  # noqa: E402 | O(1) lazy
    sd = Path(sd)  # O(1)
    import plan_tools as pt  # noqa: E402 | O(1) lazy
    plan = plan or str(pt.run_plan(sd) or dp.nt.DEFAULT_PLAN)  # as `dispatch`: stable.json, pool.json, plan.md | O(pool bytes)
    shut = orchestrator.require(plan, "dispatch")  # human mode waits for approval, as `dispatch` | O(file)
    if shut:  # O(1)
        return shut  # O(1)
    _sync_remote_pool(sd)  # O(w): a pruned remote entry back, a taskless one out (#1057)
    pp = sd / "pool.json"  # O(1)
    if pp.exists():  # a worker's baseline is what it held at READY; read outside the lock, written under it | O(w)
        found = {}  # O(1)
        for ag in pool.load(pp).get("agents") or []:  # O(w) iterations
            if ag.get("backend") == "herdr" and ag.get("baseline_k") is None:  # O(1)
                k = fio.baseline_k(sd, ag["id"])  # O(file)
                if k is not None:  # O(1)
                    found[ag["id"]] = k  # O(1)
        if found:  # O(1)
            with fs.locked(sd):  # O(1) plus wait
                data = pool.load(pp)  # O(w)
                for ag in data.get("agents") or []:  # O(w) iterations
                    if ag["id"] in found:  # O(1)
                        ag["baseline_k"] = found[ag["id"]]  # O(1)
                pool.save(pp, data)  # O(w)
    lines, evict = dp.run(plan, pp, sd / "progress.md", cap=sys.maxsize)  # every ready task goes out, no cap of 10 | O(dispatch)
    dp.render([], evict)  # the `evict=` lines on stderr; the dispatch lines themselves become the worker lines below | O(a)
    sl, root = str(fio.HERE / "sl"), str(fio.HERE.parents[2])  # O(1)
    if machine:  # remote write workers: one fresh worker per task, never a reused one; each gets a pool entry busy on its task (#1057) | O(R)
        return _dispatch_machine(sd, plan, project, machine, lines, sl, fio)  # O(R * (spawn + send))
    state_of = {k: v.get("state") for k, v in fs.workers(sd).items()}  # O(w)
    ids = [k for k in evict if state_of.get(k) == "ready"]  # an evicted busy worker finishes its task | O(w)
    ids += [k for k in _dropped_ready(sd) if k not in ids]  # #424: dropped by an earlier round | O(w)
    for wid in stop(sd, ids):  # O(w) plus herdr calls
        print(f"stopped {wid}")  # O(1)
    blocked = False  # O(1)
    deadline = time.monotonic() + machine_wait  # one wait budget for the whole round | O(1)
    full = None  # the machine-busy reason once the gate refused this round while a worker is busy (#916) | O(1)

    def fresh(tier):  # O(spawn) -> (worker id or None, reason or None, queued)
        nonlocal full  # O(1)
        if full is not None:  # no room this round: the later fresh lines wait for the next one, untried | O(1)
            return None, full, True  # O(1)
        wait = 0.0 if _in_flight(sd) else max(0.0, deadline - time.monotonic())  # a busy worker frees room for the next round: no wait | O(w)
        w, why = _spawn_quiet(sd, plan, tier, project, over, wait, **({"bounds": bounds} if bounds else {}))  # O(spawn)
        if why and why.startswith(BUSY_HEAD + "machine busy") and _in_flight(sd):  # O(w)
            full = why[len(BUSY_HEAD):].removesuffix(BUSY_TAIL)  # O(len)
            return None, full, True  # O(1)
        return (w["id"] if w else None), why, False  # O(1)

    for tasks, decision in lines:  # O(R) iterations
        why, wid, brief, queued = None, None, None, False  # O(1)
        if place and decision.startswith(("fresh", "poll")):  # placement: tasks that go to a machine get a new worker each; the rest stays below | O(k)
            tasks, placed_blocked = _dispatch_placed(sd, plan, project, tasks, decision, sl, fio)  # O(k * spawn)
            blocked = blocked or placed_blocked  # O(1)
            if not tasks:  # O(1)
                continue  # O(1)
        if decision.startswith("wave0"):  # one haiku worker, sent the Wave 0 brief that `wave0 --plan` wrote | O(1)
            brief = sd / "briefs" / "wave0.md"  # O(1)
            if brief.is_file():  # no worker for a brief that is not there | O(1)
                tier = (re.search(r"\btier=(\S+)", decision) or [None, "haiku"])[1]  # O(len)
                wid, why, queued = fresh(tier)  # O(spawn)
            else:  # O(1)
                why = "no .superlite/briefs/wave0.md; run wave0 --plan PLAN"  # O(1)
        elif decision.startswith("fresh"):  # O(1)
            tier = (re.search(r"\btier=(\S+)", decision) or [None, "sonnet"])[1]  # O(len)
            wid, why, queued = fresh(tier)  # O(spawn)
        elif decision.startswith("agent="):  # an idle worker of an earlier round | O(1)
            wid = decision.split()[0].split("=", 1)[1]  # O(len)
            why = None if wid in fs.load(sd)["workers"] else f"unknown worker {wid}"  # O(w)
        else:  # `poll ...` never resolves outside fleet mode | O(1)
            why = f"no fleet decision: {decision}"  # O(1)
        if why is None:  # O(1)
            try:  # O(1)
                if brief is not None:  # O(1)
                    fio.send_brief(sd, wid, str(brief), tasks)  # prints `Wn T0 sent` | O(w + len)
                else:  # O(1)
                    fio.send(sd, plan, wid, tasks.split(","), sl, root)  # prints `Wn Tn[,Tm] sent` | O(w + n)
            except KeyError as e:  # a task id the plan does not know | O(1)
                why = f"unknown task {e.args[0]}"  # O(1)
            except FileNotFoundError:  # the brief went away between the check and the send | O(1)
                why = "no .superlite/briefs/wave0.md; run wave0 --plan PLAN"  # O(1)
            except fio.hc.HerdrError as e:  # O(1)
                why = e.message or e.code  # O(1)
        if queued:  # not a block: the tasks stay ready for the next round (#916) | O(1)
            print(f"QUEUED: {tasks} not sent ({why}); {QUEUE_TAIL}")  # O(1)
        elif why is not None:  # O(1)
            if SHELL_MSG in why:  # O(len)
                why += "; rerun sl fleet spawn --for-dispatch"  # O(1)
            print(f"BLOCKED: {tasks} not sent ({why})")  # O(1)
            blocked = True  # the next line still goes out | O(1)
    try:  # a hint failure must not fail the round | O(1)
        for line in fio.hint_lines(sd, plan, sl):  # O(n) iterations
            print(line)  # O(k)
    except (ValueError, OSError, KeyError) as e:  # O(1)
        print(f"warning: no review hints ({e})", file=sys.stderr)  # O(1)
    return 3 if blocked else 0  # O(1)


def for_review(sd, plan, project, tasks, package=None, over=False, machine_wait=100.0, note=None, machine=None, bounds=None):  # O(L + e + spawn + send): a package-reviewer for TASKS (or PACKAGE's committed tasks), brief written and sent
    import fleet_io as fio  # noqa: E402 | O(1) lazy
    sd = Path(sd)  # O(1)
    import plan_tools as pt  # noqa: E402 | O(1) lazy
    plan = plan or str(pt.run_plan(sd) or fio.nt.DEFAULT_PLAN)  # as for_dispatch | O(pool bytes)
    tasks = list(dict.fromkeys(tasks or []))  # O(k)
    if tasks and package:  # O(1)
        print("error: --for-review takes task ids or --package, not both", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if not tasks and not package:  # O(1)
        print("error: --for-review needs task ids or --package", file=sys.stderr)  # O(1)
        return 2  # O(1)
    commits = fio.ledger_commits(sd / "progress.md")  # O(lines)
    try:  # O(1)
        if package:  # O(1)
            ids = fio.package_tasks(plan, package)  # O(L + n*h)
            if not ids:  # O(1)
                print(f"error: unknown package {package} (packages: {', '.join(fio.package_names(plan))})", file=sys.stderr)  # O(L)
                return 2  # O(1)
            tasks = [t for t in ids if commits.get(t)]  # O(n)
            if not tasks:  # O(1)
                print(f"BLOCKED: no committed task in package {package}")  # O(1)
                return 3  # O(1)
        else:  # O(1)
            by_id = fio.pt.Plan.load(str(plan)).by_id  # O(L)
            for t in tasks:  # O(k) iterations
                if t not in by_id:  # O(1)
                    print(f"error: unknown task {t}", file=sys.stderr)  # O(1)
                    return 2  # O(1)
            for t in tasks:  # O(k) iterations
                if not commits.get(t):  # O(1)
                    print(f"BLOCKED: {t} has no commit line in progress.md; run commit_task {t} first")  # O(1)
                    return 3  # O(1)
    except OSError as e:  # an unreadable plan | O(1)
        print(f"error: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    try:  # a task that shares a file with an uncommitted one waits for the last commit (#741) | O(1)
        pl = fio.pt.Plan.load(str(plan))  # O(L)
        held = []  # O(1)
        for t in tasks:  # O(k) iterations
            waiting = [g for g in fio.share_group(pl, t) if not commits.get(g)]  # O(n^2*o)
            if waiting:  # O(1)
                files = [f for f in fio._shared_files(pl, fio.share_group(pl, t)) if f in fio._paths(pl.by_id[t])] or fio._paths(pl.by_id[t])  # O(n*o)
                held.append(f"BLOCKED: {t} shares {', '.join(files)} with {', '.join(waiting)}, not committed yet; run --for-review {t} {' '.join(waiting)} after {', '.join(waiting)} {'commits' if len(waiting) == 1 else 'commit'}")  # O(n)
        if held:  # O(1)
            print("\n".join(held))  # O(k)
            return 3  # O(1)
    except OSError as e:  # O(1)
        print(f"error: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    label = "review-" + (re.sub(r"[^a-z0-9]+", "-", package.lower()).strip("-") if package else ",".join(tasks))  # O(len)
    f = sd / "briefs" / (label.replace(",", "-") + ".md")  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    body = fio.review_brief(sd, plan, tasks, str(fio.HERE / "sl"), str(fio.HERE.parents[2]), package)  # O(L + e + B)
    import orchestrator  # noqa: E402 | O(1) lazy
    body = with_constraints(body, orchestrator.plan_file(sd, str(plan)))  # before the notes | O(L + B)
    import findings  # noqa: E402 | O(1) lazy
    standing = findings.standing_note(sd)  # O(file)
    if standing:  # the lead's standing note, once, after the constraints (#738) | O(1)
        body = body.rstrip("\n") + "\n\n" + "\n".join(standing) + "\n"  # O(B)
    if note and note.strip():  # O(len)
        body = body.rstrip("\n") + "\n\n## Coordinator notes\n\nThese notes add to the review above; review every task and file it lists all the same.\n\n" + note.strip() + "\n"  # O(B)
    f.write_text(body, encoding="utf-8")  # O(B)
    mkw = {"machine": machine, "remote_brief": str(f)} if machine else {}  # the remote reviewer's start commit carries the brief | O(1)
    w = spawn(sd, plan, None, project, role="package-reviewer", over=over, machine_wait=machine_wait, **({"bounds": bounds} if bounds else {}), **mkw)  # prints its own Wn or BLOCKED line; exit 3 stays | O(a * e + w)
    try:  # O(1)
        fio.send_brief(sd, w["id"], str(f), label)  # prints `Wn review-.. sent` | O(w + len)
    except (fio.hc.HerdrError, OSError, KeyError) as e:  # O(1)
        stop(sd, [w["id"]])  # close the reviewer just spawned, so a rerun does not leave two | O(w)
        print(f"BLOCKED: {w['id']} {label} not sent ({getattr(e, 'message', '') or getattr(e, 'code', '') or e})")  # O(1)
        return 3  # O(1)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        data["workers"][w["id"]]["review"] = tasks  # O(1)
        fs.save(sd, data)  # O(w)
    return 0  # O(1)


def _close_machine_workspace(sd, machine):  # the last live worker of `machine` stopped: forget and close its workspace | O(w) plus a herdr call
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        if [v for v in data["workers"].values() if v.get("machine") == machine and v.get("state") != "stopped"]:  # O(w)
            return  # O(1)
        slot = (data.get("machines") or {}).pop(machine, None)  # O(1)
        if not slot:  # O(1)
            return  # O(1)
        fs.save(sd, data)  # state first, as for the local workspace | O(w)
    try:  # O(1)
        with hc.on(machine):  # O(1)
            hc.close_workspace(slot["workspace_id"])  # O(1)
    except hc.HerdrError:  # O(1)
        pass  # O(1)


def slash_commands(w):  # O(a): whether the worker's agent takes slash commands (#930)
    argv = (w.get("launch") or {}).get("argv")  # O(1)
    if isinstance(argv, list):  # O(1)
        return "--disable-slash-commands" not in argv  # O(a)
    return w.get("role") == "lead"  # older records: only a lead keeps slash commands | O(1)


def worktree_line(sd, on):  # O(1) plus a git call: names the cwd worktree's own fleet when it disagrees with the folder status read (#904)
    try:  # O(1)
        top = state.worktree_top(".")  # O(1)
    except OSError:  # a status line must not fail the status | O(1)
        return None  # O(1)
    if top is None or not (Path(top) / ".superlite").is_dir():  # O(1)
        return None  # O(1)
    W, S = (Path(top) / ".superlite").resolve(), Path(sd).resolve()  # O(1)
    if W == S or fs.is_on(W) == on:  # O(1)
        return None  # O(1)
    if on:  # the worktree is off  | O(1)
        return f"worktree: fleet is off in {W}, the folder fleet spawn --plan {W} checks (this status read {S}); run sl fleet on --plan {W} first"  # O(1)
    return f"worktree: fleet is on in {W}, the folder fleet spawn --plan {W} uses (this status read {S}); sl fleet status --plan {W} shows its workers"  # O(1)


def stop(sd, ids=None, all_=False, keep_workspace=False):  # O(w) plus herdr calls
    sd = Path(sd)  # O(1)
    live = {k: v for k, v in fs.workers(sd).items() if v.get("state") != "stopped"}  # O(w)
    targets = list(live) if all_ else [i for i in (ids or []) if i in live]  # O(w)
    p = sd / "pool.json"  # O(1)
    pdata = pool.load(p) if p.exists() else None  # O(w)
    for wid in targets:  # O(w)
        if live[wid].get("machine"):  # a remote worker: exit, close and tree drop run on its machine | O(1)
            import fleet_remote_worker as frw  # noqa: E402 | O(1) lazy
            frw.stop(sd, wid)  # O(1) plus remote calls
            if pdata is not None:  # O(1)
                pool.remove(pdata, wid)  # O(w)
            _close_machine_workspace(sd, live[wid]["machine"])  # O(w)
            continue  # O(1)
        if live[wid].get("role") == "lead" and live[wid].get("lead_sd") and Path(live[wid]["lead_sd"]).is_dir():  # a lead's workers exit before the lead | O(w)
            try:  # O(1)
                stop(Path(live[wid]["lead_sd"]), all_=True)  # O(w)
            except Exception:  # noqa: BLE001 | O(1)
                pass  # O(1)
        try:  # O(1)
            hc.exit_agent(fs.name_of(sd, wid, live[wid]), slash=slash_commands(live[wid]))  # a lean agent gets no /exit: close_pane ends it (#930) | O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        try:  # O(1)
            hc.close_pane(live[wid]["pane_id"])  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        fs.set_state(sd, wid, "stopped")  # O(w)
        _tel_worker_stop(sd, live[wid], "STOPPED")  # O(1)
        if sd.name == ".superlite":  # the worker's tree is no longer needed (#614) | O(tree size)
            try:  # O(1)
                import trees  # noqa: E402 | O(1) lazy
                if not trees.is_busy(sd.parent, f"worker-{wid}"):  # O(markers)
                    trees.drop(sd.parent, f"worker-{wid}")  # O(tree size)
            except Exception:  # noqa: BLE001 | O(1) cleanup is best effort
                pass  # O(1)
        if pdata is not None:  # O(1)
            pool.remove(pdata, wid)  # O(w)
    if pdata is not None and targets:  # O(1)
        pool.save(p, pdata)  # O(w)
    data = fs.load(sd)  # O(w)
    if data.get("workspace_id") and not [v for v in data["workers"].values() if v.get("state") != "stopped" and not v.get("machine")]:  # O(w)
        fs.set_workspace(sd, None, None)  # state first: closing the workspace kills the pane of a caller that runs inside it | O(w)
        if not keep_workspace:  # `off` closes it itself, after it has said so | O(1)
            try:  # O(1)
                hc.close_workspace(data["workspace_id"])  # O(1)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
    return targets  # O(1)


def _tel_fleet(sd, on, accounts):  # the `fleet` event of on and off; never raises | O(1)
    try:  # O(1)
        import telemetry  # noqa: E402 | O(1) lazy
        telemetry.emit("fleet", sd=sd, on=on, accounts=list(accounts))  # O(s)
    except BaseException:  # a telemetry failure never changes the command | O(1)
        pass  # O(1)


def _sd(a):  # O(d)
    return Path(state.resolve(getattr(a, "plan", None))).resolve()  # O(d)


def _brief_arg(argv):  # the value of the last --brief X or --brief=X, else None | O(n)
    found = None  # O(1)
    for i, x in enumerate(argv):  # O(n)
        if x == "--brief" and i + 1 < len(argv):  # O(1)
            found = argv[i + 1]  # O(1)
        elif x.startswith("--brief="):  # O(1)
            found = x[len("--brief="):]  # O(1)
    return found  # O(1)


def with_constraints(text, plan):  # TEXT with the plan's Global constraints appended as one section; unchanged when it has them, no plan, or none stated (#635); review and fix briefs keep it by ruling (#1059) | O(L + len)
    if plan is None or re.search(r"^#{1,4}\s+Global constraints", text, re.I | re.M):  # O(len)
        return text  # O(1)
    import plan_tools  # noqa: E402 | O(1) lazy
    import wave0  # noqa: E402 | O(1) lazy
    lines = wave0.constraint_lines(plan_tools.Plan.load(str(plan)))  # O(L)
    if not lines:  # O(1)
        return text  # O(1)
    return text.rstrip("\n") + "\n\n## Global constraints\n\n" + "\n".join(lines) + "\n"  # O(len)


def add_constraints(brief, plan):  # rewrite the brief file with the constraints section; whether it changed. Any error leaves it as it was (#635) | O(L + len)
    try:  # O(1)
        p = Path(brief)  # O(1)
        old = p.read_text(encoding="utf-8")  # O(file)
        new = with_constraints(old, plan)  # O(L + len)
        if new == old:  # O(1)
            return False  # O(1)
        p.write_text(new, encoding="utf-8")  # O(file)
    except (Exception, SystemExit):  # noqa: BLE001 | O(1) a send never fails on it
        return False  # O(1)
    return True  # O(1)


def _plan_arg(argv):  # the value of the last --plan P or --plan=P (argparse's pick), else None | O(n)
    found = None  # O(1)
    for i, x in enumerate(argv):  # O(n)
        if x == "--plan" and i + 1 < len(argv):  # O(1)
            found = argv[i + 1]  # O(1)
        elif x.startswith("--plan="):  # O(1)
            found = x[len("--plan="):]  # O(1)
    return found  # O(1)


def _role_arg(argv):  # the value of the last --role X or --role=X, else None | O(n)
    found = None  # O(1)
    for i, x in enumerate(argv):  # O(n)
        if x == "--role" and i + 1 < len(argv):  # O(1)
            found = argv[i + 1]  # O(1)
        elif x.startswith("--role="):  # O(1)
            found = x[len("--role="):]  # O(1)
    return found  # O(1)


def _plan_problem(plan):  # why a --plan value cannot hold a run, or "" | O(d)
    pp = Path(plan)  # O(1)
    if pp.exists() and not (pp.is_file() or pp.is_dir()):  # O(1) e.g. /dev/null
        return "not a plan file or folder"  # O(1)
    sd = state.plan_dir(plan).resolve()  # O(d)
    if sd.is_dir():  # O(1)
        return ""  # O(1)
    d = sd.parent  # O(1)
    while not d.exists() and d != d.parent:  # nearest existing ancestor | O(d)
        d = d.parent  # O(1)
    return "" if d.is_dir() and os.access(d, os.W_OK) else f"cannot create {sd}"  # O(1)


def agent_gone(name, client=None):  # True only when herdr says the agent does not exist; any other failure is unknown, so False | O(1)
    c = client or hc  # O(1)
    try:  # O(1)
        c.agent_state(name)  # O(1)
    except Exception as e:  # noqa: BLE001 | O(1)
        return getattr(e, "code", None) == "agent_not_found"  # O(1)
    return False  # O(1)


def _tel_worker_stop(sd, w, status):  # one agent_stop line (DEAD or STOPPED) for a fleet worker; never raises | O(1)
    try:  # O(1)
        import fleet_io  # noqa: PLC0415 | O(1)
        import telemetry  # noqa: PLC0415 | O(1)
        m = re.match(r"T\d+", str(w.get("task") or ""))  # O(1)
        busy = w.get("state") == "busy" and w.get("sent")  # O(1)
        dur = round((fleet_io.now_ms() - w["sent"]) / 1000, 1) if busy else None  # O(1)
        telemetry.emit("agent_stop", sd=sd, task=m.group(0) if m else None, role=w.get("role") or "implementer", model=w.get("model") or w.get("tier"), effort=None, account=w.get("account"), machine=w.get("machine") or None, duration_s=dur, tokens=None, cost_usd=None, tool_calls=None, status=status, agent_session=w.get("session"))  # O(1)
    except BaseException:  # noqa: BLE001 | a telemetry failure never changes the state change | O(1)
        pass  # O(1)


def mark_dead(sd, wid):  # stopped, dead, off the pool; no pane is closed; one agent_stop DEAD line on the first transition | O(w)
    sd = Path(sd)  # O(1)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        w = data["workers"].get(wid)  # O(1)
        if w is None:  # O(1)
            return  # O(1)
        before = dict(w)  # O(1)
        w.update({"state": "stopped", "dead": True, "was": w.get("was") if w.get("dead") else w.get("state"), "last_task": w.get("task") or w.get("last_task"), "task": None})  # O(1)
        fs.save(sd, data)  # O(w)
        _pool_drop(sd, wid)  # O(w)
    if not before.get("dead"):  # O(1)
        _tel_worker_stop(sd, before, "DEAD")  # O(1)


def respawn_hint(sd, wid, plan=None):  # the `sl fleet spawn` line that starts a fresh worker like WID; KeyError for an unknown worker | O(w)
    w = fs.load(Path(sd))["workers"][wid]  # O(w)
    role = w.get("role") or "implementer"  # O(1)
    parts = ["sl fleet spawn"]  # O(1)
    if role != "implementer":  # O(1)
        parts.append(f"--role {role}")  # O(1)
    if w.get("tier") and role in ("implementer", "fixer", "research"):  # other roles take no --tier | O(1)
        parts.append(f"--tier {w['tier']}")  # O(1)
    if w.get("brief"):  # O(1)
        parts.append(f"--brief {w['brief']}")  # O(1)
    parts.append(f"--plan {plan or sd}")  # O(1)
    return " ".join(parts)  # O(1)


def _ended_stop(sd, wid, w):  # the stop record of a busy worker's turn that ended since its send, else None | O(m + w)
    if w.get("state") != "busy" or w.get("role") == "layer":  # O(1)
        return None  # O(1)
    import fleet_io as fio  # noqa: E402 | O(1) lazy
    return fio.latest_stop(sd, wid, int(w.get("sent") or 0))  # O(m + w)


def _report(sd, ids):  # print each worker's last report or a report by label; read-only | O(ids * file)
    rd = sd / "fleet" / "reports"  # O(1)
    ws = fs.workers(sd)  # O(w)
    bad = False  # O(1)
    for x in ids:  # O(ids)
        label = x  # O(1)
        rd = sd / "fleet" / "reports"  # O(1)
        if x in ws:  # O(1)
            w = ws[x]  # O(1)
            rec = _ended_stop(sd, x, w)  # O(m + w)
            if rec is not None:  # a turn that ended and nobody collected: read it, change nothing | O(1)
                import fleet_io as fio  # noqa: E402 | O(1) lazy
                tr = rec.get("transcript")  # O(1)
                t = (fio.report_text(tr) if tr else "") or ("" if tr else rec.get("last", ""))  # O(T)
                print(f"{x} {w.get('task') or x}: turn ended, not collected yet; read-only, collect with sl fleet wait {x}", file=sys.stderr)  # O(1)
                if len(ids) > 1:  # O(1)
                    print(f"== {x} {tr or 'stop record'}")  # O(1)
                print(t, end="" if t.endswith("\n") else "\n")  # O(len)
                continue  # O(1)
            if w.get("state") == "busy":  # O(1)
                print(f"error: {x} is busy on {w.get('task')}; run sl fleet wait {x} first", file=sys.stderr)  # O(1)
                bad = True  # O(1)
                continue  # O(1)
            if w.get("state") == "blocked" or w.get("task"):  # a current task: last_task is an older label's report | O(1)
                print(f"error: {x} is blocked on {w.get('task') or x} (BLOCKED-UI); screen: {sd / 'fleet' / 'screens' / f'{x}.txt'}", file=sys.stderr)  # O(1)
                bad = True  # O(1)
                continue  # O(1)
            if not w.get("last_task"):  # O(1)
                print(f"error: {x} has no collected report; run sl fleet wait {x} first", file=sys.stderr)  # O(1)
                bad = True  # O(1)
                continue  # O(1)
            label = w["last_task"]  # O(1)
            import fleet_io as fio  # noqa: E402 | O(1) lazy
            rd = fio.report_dir(sd, w)  # O(1)
        key = label.split(",")[0]  # O(1)
        f = next((q for q in (rd / f"{key}.md", rd / f"{key}.json") if q.is_file()), None)  # O(1)
        if f is None:  # O(1)
            print(f"error: {x} {label}: no report file in {rd}" if x in ws else f"error: unknown worker or report label {x}", file=sys.stderr)  # O(1)
            bad = True  # O(1)
            continue  # O(1)
        if len(ids) > 1:  # O(1)
            print(f"== {x} {f}")  # O(1)
        t = f.read_text(encoding="utf-8")  # O(file)
        print(t, end="" if t.endswith("\n") else "\n")  # O(file)
    return 1 if bad else 0  # O(1)


def _follow(plan, named=False):  # O(w)
    """Move the session's fleet into the folder this command names; one stderr line when it moved, a warning when it failed."""
    try:  # O(1)
        sd = Path(state.resolve(plan)).resolve()  # O(d)
    except (state.Foreign, OSError):  # O(1)
        return  # O(1)
    try:  # O(1)
        r = fs.follow(sd, named=named)  # O(w)
    except Exception as e:  # noqa: BLE001 | a failed move must not stop the command | O(1)
        print(f"fleet: warning: fleet not moved ({e})", file=sys.stderr)  # O(1)
        return  # O(1)
    if r:  # O(1)
        print(r["line"], file=sys.stderr)  # O(1)


class _Stopped(BaseException):  # a signal during the start phase of `fleet spawn`: not an Exception, so no `except Exception` of a start swallows it | O(1)
    def __init__(self, name):  # O(1)
        super().__init__(name)  # O(1)
        self.name = name  # O(1)


_INFLIGHT = {}  # O(1) the worker `_spawn` has a pane for and has not finished: sd, wid, pane


def _raise_stopped(signum, frame):  # O(1)
    raise _Stopped(signal.Signals(signum).name)  # O(1)


def _stopped_line(name, secs, text=None):  # the one BLOCKED line of a stopped or failed spawn; the worker in flight is set blocked and its pane closed: exit code 3 | O(w)
    left = ""  # O(1)
    cur = dict(_INFLIGHT)  # O(1)
    _INFLIGHT.clear()  # O(1)
    if cur:  # O(1)
        with contextlib.suppress(Exception):  # O(1)
            fs.set_state(cur["sd"], cur["wid"], "blocked")  # O(w)
        with contextlib.suppress(Exception):  # O(1)
            hc.close_pane(cur["pane"])  # O(1)
        left = f"; {cur['wid']} left blocked"  # O(1)
    if text is None:  # O(1)
        text = f"fleet spawn stopped by {name} after {int(secs)} s{left}; give the Bash call a timeout of 600000 ms, then rerun"  # O(1)
    else:  # O(1)
        text += left  # O(1)
    print(f"BLOCKED: {text}")  # O(1)
    return 3  # O(1)



def _bounds(a):  # the --max-workers and --min-swap-free-mb values as a dict, or None when neither is set | O(1)
    if a.max_workers is None and a.min_swap_free_mb is None:  # O(1)
        return None  # O(1)
    return {"max_workers": a.max_workers, "min_swap_free_mb": a.min_swap_free_mb}  # O(1)


def _spawn_cmd(a, sd, note, output, tmo, restore):  # the gate-to-send work of `spawn`: its exit code | O(R * (spawn + send))
    if a.role == "lead":  # a lead for a plan in its own worktree (#906) | O(start)
        import fleet_lead  # noqa: E402 | O(1) lazy
        code, wid = fleet_lead.start_plan_lead(sd, a.plan, brief=a.brief, label=a.label, over=a.over_limit, machine_wait=a.machine_wait)  # O(start)
        if code == 0 and a.wait:  # O(1)
            restore()  # the signal handlers end with the start phase | O(1)
            importlib.import_module("fleet_io").wait(sd, [wid], tmo)  # O(wait)
        return code  # O(1)
    forced = a.machine == "local"  # forces this machine: placement is not asked | O(1)
    if forced:  # O(1)
        a.machine = None  # O(1)
    if a.machine and (a.package or not (a.for_dispatch or a.for_review is not None or a.brief)):  # O(1)
        print("error: --machine works with --for-dispatch, --for-review Tn or a plain spawn (--role R --brief F)", file=sys.stderr)  # O(1)
        return 2  # O(1) before any pane
    if a.machine:  # O(1)
        import fleet_placement  # noqa: E402 | O(1) lazy
        why = fleet_placement.machine_refusal(state.project(sd), a.machine)  # O(f * k)
        if why:  # O(1)
            print(why, file=sys.stderr)  # O(1)
            return 2  # O(1) before any pane
    if (a.for_dispatch or a.for_review is not None or a.package) and a.plan and Path(a.plan).is_dir():  # a run folder names its plan file (#508) | O(d)
        import plan_tools as pt  # noqa: E402 | O(1) lazy
        try:  # O(1)
            a.plan = str(pt.resolve_plan(a.plan))  # O(d)
        except pt.PlanError as e:  # O(1)
            print(f"error: {e}", file=sys.stderr)  # O(1)
            return 2  # O(1) before dispatch: no pane, no worker id
    if a.plan:  # a spawn that knows its plan stops while the budget is paused; the gate fails open | O(compute)
        try:  # O(compute)
            import budget  # noqa: E402 | O(1) lazy
            paused = budget.gate(a.plan, str(sd))  # O(compute)
        except Exception:  # noqa: BLE001 | O(1)
            paused = None  # O(1)
        if paused:  # O(1)
            print(f"BLOCKED: fleet spawn: {paused}")  # O(1)
            return 3  # O(1) before any pane or worker id
    if not a.for_dispatch:  # dispatch gates the disk itself (#614) | O(1)
        import trees  # noqa: E402 | O(1) lazy
        level, line = trees.disk_gate(state.project(sd))  # O(1)
        if level == "refuse":  # O(1)
            print(f"BLOCKED: fleet spawn: {line}")  # O(1)
            return 3  # O(1) before any pane
        if level == "warn":  # O(1)
            print(f"fleet: {line}", file=sys.stderr)  # O(1)
    if not a.machine:  # a local worker lands in this launchd session (#798) | O(1)
        try:  # never blocks a spawn | O(1)
            import gui_session  # noqa: E402 | O(1) lazy
            import testcmd  # noqa: E402 | O(1) lazy
            warn = gui_session.spawn_warning(testcmd.read_config(state.project(sd)))  # O(file)
            if warn:  # O(1)
                print(f"fleet: warning: {warn}", file=sys.stderr)  # O(1)
        except Exception:  # noqa: BLE001 | O(1)
            pass  # O(1)
    bkw = {"bounds": _bounds(a)} if _bounds(a) else {}  # only a set bound is passed on | O(1)
    if a.for_dispatch:  # O(1)
        return for_dispatch(sd, a.plan, state.project(sd), a.over_limit, a.machine_wait, a.machine, not forced, **bkw)  # O(R * (spawn + send))
    if a.for_review is not None or a.package:  # O(1)
        ids = [x for v in a.for_review or [] for x in re.split(r"[,\s]+", v) if x]  # O(len)
        return for_review(sd, a.plan, state.project(sd), ids, a.package, a.over_limit, a.machine_wait, note, a.machine, **bkw)  # O(L + e + spawn + send)
    placed = False  # the machine came from placement, not from --machine | O(1)
    if a.brief and not a.machine and not forced:  # O(1)
        a.machine = _placed(sd, a.role, state.project(sd))  # O(w + m)
        placed = bool(a.machine)  # O(1)
    mkw = {"machine": a.machine, "remote_brief": a.brief} if a.machine else {}  # only a remote spawn passes it | O(1)
    if a.machine and a.brief:  # a remote worker's start commit carries the brief, so its constraints go in first | O(L + len)
        import orchestrator  # noqa: E402 | O(1) lazy
        add_constraints(a.brief, orchestrator.plan_file(sd, a.plan))  # O(L + len)
    try:  # O(1)
        if placed:  # a remote failure is not a block: its output is held back and the worker starts here | O(w)
            buf = io.StringIO()  # O(1)
            try:  # O(1)
                with contextlib.redirect_stdout(buf):  # O(1)
                    w = spawn(sd, a.plan or sd, a.tier, state.project(sd), role=a.role, over=a.over_limit, machine_wait=a.machine_wait, output=output, brief=bool(a.brief), **bkw, **mkw)  # O(w)
            except (SystemExit, Exception) as e:  # noqa: BLE001 | O(1)
                if isinstance(e, SystemExit) and e.code != 3:  # O(1)
                    sys.stdout.write(buf.getvalue())  # the held-back lines of a real exit are not lost | O(s)
                    raise  # O(1)
                if isinstance(e, ValueError):  # a bad role or tier is the caller's error, not a machine failure | O(1)
                    raise  # O(1)
                _unavailable(sd, a.machine, "; ".join(x.strip() for x in buf.getvalue().splitlines() if x.strip()) or str(e))  # O(s)
                placed, mkw = False, {}  # O(1)
            else:  # O(1)
                sys.stdout.write(buf.getvalue())  # O(s)
        if not placed:  # O(1)
            w = spawn(sd, a.plan or sd, a.tier, state.project(sd), role=a.role, over=a.over_limit, machine_wait=a.machine_wait, output=output, brief=bool(a.brief), **bkw, **mkw)  # O(w)
    except ValueError as e:  # an unknown role or tier | O(1)
        print(f"error: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if a.brief:  # O(1)
        import fleet_io as fio  # noqa: E402 | O(1) lazy
        label = a.label or Path(a.brief).stem  # O(1)
        import orchestrator  # noqa: E402 | O(1) lazy
        add_constraints(a.brief, orchestrator.plan_file(sd, a.plan))  # O(L + len)
        while True:  # at most twice: a placed remote worker whose brief did not land is replaced by a local one | O(1)
            try:  # O(1)
                fio.send_brief(sd, w["id"], a.brief, a.label, **({"preface": fleet_roles_text(w)} if w.get("brief_only") else {}))  # O(w)
                break  # O(1)
            except (hc.HerdrError, OSError, KeyError) as e:  # a worker that got no brief is stopped, not left ready | O(w)
                why = getattr(e, "message", "") or e  # O(1)
                if not placed:  # O(1)
                    stop(sd, [w["id"]])  # O(w)
                    print(f"BLOCKED: {w['id']} {label} not sent ({why})")  # O(1)
                    return 3  # O(1)
                try:  # O(1)
                    with contextlib.redirect_stdout(io.StringIO()):  # the remote worker's stop lines are not this spawn's result | O(1)
                        stop(sd, [w["id"]])  # O(w)
                except Exception:  # noqa: BLE001 | an unreachable host must not end the fallback | O(1)
                    pass  # O(1)
                _unavailable(sd, a.machine, f"{w['id']} not sent: {why}")  # O(k)
                placed = False  # O(1)
                w = spawn(sd, a.plan or sd, a.tier, state.project(sd), role=a.role, over=a.over_limit, machine_wait=a.machine_wait, output=output, brief=True, **bkw)  # O(w)
        if a.wait:  # O(1)
            restore()  # the signal handlers end with the start phase | O(1)
            fio.wait(sd, [w["id"]], tmo)  # O(wait)
    return 0  # O(1)


def main(argv=None):  # O(w) plus command cost
    argv = list(sys.argv[1:] if argv is None else argv)  # O(n)
    plan = _plan_arg(argv)  # O(n)
    lead = bool(argv) and argv[0] == "spawn" and _role_arg(argv) == "lead"  # --plan names the lead's plan, not this run (#906) | O(n)
    if lead:  # O(1)
        plan = None  # O(1)
    why = _plan_problem(plan) if plan is not None else ""  # O(d)
    if why:  # O(1)
        print(f"error: --plan {plan}: {why}; pass the plan file or the run's .superlite folder, or leave --plan out to use the current directory's run", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if plan is not None and argv and argv[0] not in ("on", "name") and not argv[0].startswith("-"):  # a missing state folder is refused, nothing created, no fleet moves (#707) | O(d)
        sd = Path(state.resolve(plan)).resolve()  # O(d)
        if not sd.is_dir():  # O(1)
            print(f"error: --plan {plan}: no run state at {sd}", file=sys.stderr)  # O(1)
            return 2  # O(1)
    if argv and argv[0] != "name" and not argv[0].startswith("-"):  # Every subcommand but name first moves this session's fleet into its folder (#580) | O(1)
        _follow(plan, named=argv[0] == "on")  # O(w)
    if argv and argv[0] == "send" and _brief_arg(argv):  # the brief gains the plan's Global constraints once (#635) | O(L + len)
        try:  # O(1)
            import orchestrator  # noqa: E402 | O(1) lazy
            add_constraints(_brief_arg(argv), orchestrator.plan_file(_sd(argparse.Namespace(plan=plan)), plan))  # O(L + len)
        except Exception:  # noqa: BLE001 | a send never fails on the constraints | O(1)
            pass  # O(1)
    if argv and argv[0] in ("send", "keys", "wait"):  # O(1)
        return importlib.import_module("fleet_io").main(argv)  # O(1) delegated
    if argv and argv[0] == "run":  # a layer run: a shell pane per layer | O(1)
        return importlib.import_module("fleet_layer").main(argv[1:])  # O(1) delegated
    if argv and argv[0] == "restore":  # after a Herdr restart: every pane again | O(1)
        return importlib.import_module("fleet_restore").main(argv[1:])  # O(1) delegated
    if argv and argv[0] == "resume":  # continue a stopped one-turn worker's session | O(1)
        return importlib.import_module("fleet_resume").main(argv[1:])  # O(1) delegated
    p = argparse.ArgumentParser(prog="fleet.py")  # O(1)
    sub = p.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("on", help="turn fleet mode on")  # O(1)
    s.add_argument("--accounts", default="")  # O(1)
    s.add_argument("--plan")  # O(1)
    s.add_argument("--config")  # O(1) a named run config (#681); written as the run's snapshot
    sub.add_parser("off", help="stop every worker and turn fleet mode off").add_argument("--plan")  # O(1)
    s = sub.add_parser("status", help="list the workers")  # O(1)
    s.add_argument("--plan")  # O(1)
    s.add_argument("--all", action="store_true")  # O(1) also stopped and blocked workers
    s = sub.add_parser("spawn", help="start a worker")  # O(1)
    s.add_argument("--role", default="implementer")  # O(1) checked by fleet_roles, which names the valid roles
    s.add_argument("--tier", default=None)  # O(1) the implementer's default is sonnet, a fixer's tier is 1/2/3
    s.add_argument("--plan")  # O(1)
    s.add_argument("--for-review", nargs="*", default=None)  # O(1) task ids, commas or spaces
    s.add_argument("--package")  # O(1) alone it means --for-review of the package's committed tasks
    s.add_argument("--note")  # O(1) a file of coordinator notes appended to the review brief
    s.add_argument("--brief")  # O(1) a plain spawn sends this brief file to the new worker
    s.add_argument("--label", default="")  # O(1) the brief's task label
    s.add_argument("--wait", action="store_true")  # O(1) then waits for its report
    s.add_argument("--timeout", default=None)  # O(1) with --wait: ms, 580s, 9m
    s.add_argument("--over-limit", action="store_true")  # O(1) skip the machine gate (memory floor and count cap) for every spawn
    s.add_argument("--max-workers", type=int, default=None)  # O(1) bound --over-limit: refuse when this run already has this many live workers
    s.add_argument("--min-swap-free-mb", type=int, default=None)  # O(1) bound --over-limit: refuse when swap has less free than this
    s.add_argument("--machine-wait", type=float, default=100.0)  # O(1) seconds a spawn waits for room on the machine
    s.add_argument("--machine", default=None)  # O(1) a saved Herdr machine: the worker runs there (plain spawn only)
    s.add_argument("--for-dispatch", action="store_true")  # O(1) run dispatch, spawn per `fresh` line, send each line's tasks
    s = sub.add_parser("placement", help="show or set where new workers start: spread (the default) or local")  # O(1)
    s.add_argument("mode", nargs="?", choices=("spread", "local"))  # O(1)
    s.add_argument("--plan")  # O(1)
    s = sub.add_parser("stop", help="close workers")  # O(1)
    s.add_argument("ids", nargs="*")  # O(1)
    s.add_argument("--all", action="store_true")  # O(1)
    s.add_argument("--plan")  # O(1)
    s = sub.add_parser("name", help="print the full agent name sl:{repo}-{worktree}-{id}")  # O(1)
    s.add_argument("ident", nargs="?", default="")  # O(1)
    s.add_argument("--plan")  # O(1)
    s = sub.add_parser("report", help="print a worker's last report")  # O(1)
    s.add_argument("ids", nargs="+")  # O(1)
    s.add_argument("--plan")  # O(1)
    s = sub.add_parser("collect", help="collect a remote write worker's late snapshot again")  # O(1)
    s.add_argument("id")  # O(1)
    s.add_argument("--plan")  # O(1)
    for n, h in (("send", "send tasks, a brief or text to a worker"), ("keys", "send keys to a worker's pane"),  # O(1) delegated before parsing: these feed --help only
                 ("wait", "wait for busy workers to report"), ("run", "run a test layer in a shell pane"),  # O(1)
                 ("restore", "re-launch every worker after a Herdr restart"),  # O(1)
                 ("resume", "continue a stopped one-turn worker's session")):  # O(1)
        sub.add_parser(n, help=h)  # O(1)
    a = p.parse_args(argv)  # O(n)
    sd = Path(state.resolve(None)).resolve() if a.cmd == "spawn" and a.role == "lead" else _sd(a)  # a lead's spawning fleet is the current directory's run (#906) | O(d)
    if a.cmd == "name":  # O(1) before any herdr call; fleet mode may be off
        print(fs.full_name(sd, a.ident))  # O(1)
        return 0  # O(1)
    if a.cmd == "placement":  # O(1) before any herdr call; fleet mode may be off
        import fleet_placement as fp  # noqa: E402 | O(1) lazy
        if a.mode:  # O(1)
            fp.set_mode(sd, a.mode)  # O(w)
            print(f"placement: {a.mode}")  # O(1)
            return 0  # O(1)
        print(f"placement: {fs.load(sd).get('placement') or 'spread'}" + ("" if fp.enabled(sd) else " (off: machine.json names no remote_room and remote_tree, or the mode is local)"))  # O(w)
        names, files, err = fp.excluded(state.project(sd))  # O(f * k)
        if err:  # O(1)
            print(f"excluded: {err}; every worker of this project stays local")  # O(1)
        elif names:  # O(1)
            print(f"excluded: {', '.join(sorted(names))} ({', '.join(str(f) for f in files)})")  # O(n)
        for label, info in fp.room(sd).items():  # O(m)
            print(f"{label}: {info.get('state')} room {info.get('room') if info.get('room') is not None else '?'}" + (" (excluded)" if label != "local" and fp.is_excluded(label, names) else ""))  # O(n)
        return 0  # O(1)
    if a.cmd == "on":  # O(1)
        raw = a.accounts or os.environ.get("SUPERLITE_FLEET_ACCOUNTS", "")  # O(1) flag wins over env
        accts = [x.strip() for x in raw.split(",") if x.strip()]  # O(a)
        if a.config:  # O(1)
            try:  # O(1)
                cfg_rc = run_config.resolve(a.config, Path(sd).resolve().parent)  # O(file)
            except run_config.ConfigError as e:  # O(1)
                print(f"error: {e}", file=sys.stderr)  # O(1)
                return 2  # O(1)
            run_config.write_active(sd, cfg_rc)  # O(1)
            print(f"fleet: run config {cfg_rc['id']}", file=sys.stderr)  # O(1)
        fs.set_on(sd, fs.full_name(sd), accts)  # O(w)
        if any(not ac.is_path(x) and x != "current" for x in accts) and not ac.read_listing().get("accounts"):  # O(a) plus subprocess time
            print("fleet: warning: claude-profile list unavailable; account names cannot be resolved, pass config dir paths instead", file=sys.stderr)  # O(1)
        print(f"fleet: on accounts={','.join(accts) or 'auto'}", file=sys.stderr)  # O(a) stdout stays clean for worker lines
        _tel_fleet(sd, True, accts)  # O(1)
    elif a.cmd == "off":  # O(1)
        ws = fs.load(sd).get("workspace_id")  # read before stop clears it | O(w)
        was = list(fs.load(sd).get("accounts") or [])  # O(w)
        stop(sd, all_=True, keep_workspace=True)  # O(w)
        fs.set_off(sd)  # O(1)
        _tel_fleet(sd, False, was)  # O(1)
        print("fleet: off", flush=True)  # said before the workspace closes: a caller inside it dies with its pane | O(1)
        if ws:  # O(1)
            try:  # O(1)
                hc.close_workspace(ws)  # O(1)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
    elif a.cmd == "status":  # O(w)
        import fleet_lead  # noqa: E402 | O(1) lazy
        hint = fleet_lead.backlog_hint(sd, Path.cwd()) if not a.plan else None  # a plain status only; --plan names a run | O(b)
        if not fs.is_on(sd):  # O(w)
            moved = fs.load(sd).get("moved_to")  # O(w)
            print(f"fleet: off (moved to {moved})" if moved else "fleet: off")  # O(1)
            wl = worktree_line(sd, False) if not a.plan else None  # O(1)
            if wl:  # O(1)
                print(wl)  # O(1)
            _machine_line()  # O(p)
            if hint:  # O(1)
                print(hint)  # O(1)
            return 0  # O(1)
        print("fleet: on")  # O(1)
        wl = worktree_line(sd, True) if not a.plan else None  # O(1)
        if wl:  # O(1)
            print(wl)  # O(1)
        import fleet_io as fio  # noqa: E402 | O(1) lazy
        pooled = {x["id"]: x for x in pool.load(sd / "pool.json").get("agents") or []}  # O(w)
        newly, ended = [], []  # O(1)
        for wid, w in fs.workers(sd).items():  # probe: a gone agent is dead, an unreachable herdr changes nothing | O(w)
            if w.get("state") in ("ready", "busy") and w.get("role") != "layer" and not w.get("machine") and agent_gone(fs.name_of(sd, wid, w)):  # O(1)
                mark_dead(sd, wid)  # O(w)
                newly.append(wid)  # O(1)
        try:  # what a busy worker waits on; never stops the status | O(w + p)
            waits = fleet_waits.suffixes(sd, fs.workers(sd))  # O(w + p)
        except Exception:  # noqa: BLE001 | O(1)
            waits = {}  # O(1)
        for wid, w in fs.workers(sd).items():  # O(w)
            if not a.all and wid not in newly and w.get("state") in ("stopped", "blocked"):  # O(1)
                continue  # O(1)
            role = w.get("role")  # O(1)
            tail = ""  # O(1)
            if wid in pooled:  # O(1)
                bk = fio.baseline_k(sd, wid)  # O(file)
                tail = f" context_k={pooled[wid].get('context_k', '-')} baseline_k={'-' if bk is None else bk}"  # O(1)
            shown = "dead" if w.get("dead") and w.get("state") == "stopped" else w.get("state")  # O(1)
            if shown == "busy" and _ended_stop(sd, wid, w) is not None:  # O(m + w)
                shown = "reported"  # O(1)
                ended.append(wid)  # O(1)
            print(f"{wid} {shown} account={w.get('account')} pane={w.get('pane_id')} task={w.get('task') or '-'}" + (f" role={role}" if role and role != "implementer" else "") + tail + (waits.get(wid, "") if shown == "busy" else ""))  # O(1)
        import status as _status  # noqa: E402 | O(1) lazy
        for wid, w in fs.workers(sd).items():  # a lead's own progress line (#906) | O(w)
            if not a.all and wid not in newly and w.get("state") in ("stopped", "blocked"):  # O(1)
                continue  # O(1)
            pl = _status.lead_progress(wid, w)  # O(file)
            if pl is not None:  # O(1)
                print(pl)  # O(1)
        for wid in newly:  # O(w)
            print(f"dead: {wid} (its agent is gone); start a fresh one: {respawn_hint(sd, wid, str(sd))}")  # O(w)
        if newly:  # O(1)
            print(f"restore: after a Herdr restart, sl fleet restore --plan {sd} resumes the workers in their own sessions")  # O(1)
        for wid in ended:  # O(w)
            print(f"reported: {wid}; collect: sl fleet wait {wid} --plan {sd}")  # O(1)
        _machine_line()  # O(p)
        if hint:  # O(1)
            print(hint)  # O(1)
    elif a.cmd == "spawn":  # O(1)
        if _bounds(a) and not a.over_limit:  # before any spawn path | O(1)
            print("error: --max-workers and --min-swap-free-mb bound --over-limit; pass --over-limit too", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not fs.is_on(sd):  # a worktree run keeps its own fleet.json: the main checkout's `fleet on` does not reach it (#355) | O(w)
            hint = "sl fleet on" + (f" --plan {a.plan}" if a.plan and a.role != "lead" else "")  # O(1) the same --plan resolves the same state dir
            moved = fs.load(sd).get("moved_to")  # O(w)
            tail = f"this fleet moved to {moved}: pass --plan {moved}" if moved else "a worktree run keeps its own fleet.json"  # O(1)
            print(f"BLOCKED: fleet is off in {sd}; run {hint} first" + (f"; {tail}" if moved else f" ({tail})"))  # O(1)
            return 3  # O(1) before dispatch: no task marked, no pane, no worker id
        is_lead = a.role == "lead"  # O(1)
        if is_lead:  # O(1)
            if a.tier or a.machine or a.for_dispatch or a.for_review is not None or a.package or a.note is not None:  # O(1)
                print("error: --role lead takes no --tier, --machine, --for-dispatch, --for-review, --package or --note", file=sys.stderr)  # O(1)
                return 2  # O(1)
            if not a.plan:  # O(1)
                print("error: --role lead needs --plan P (the lead's plan; with --brief F any path inside its worktree)", file=sys.stderr)  # O(1)
                return 2  # O(1)
        if a.cmd == "spawn" and a.wait and not a.brief and not is_lead:  # before any pane | O(1)
            print("error: --wait needs --brief", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if a.timeout is not None and not a.wait:  # O(1)
            print("error: --timeout needs --wait", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if a.brief and (a.for_dispatch or a.for_review is not None or a.package):  # O(1)
            print("error: --brief is for a plain spawn", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if a.note is not None and a.for_review is None and not a.package:  # O(1)
            print("error: --note is for --for-review or --package", file=sys.stderr)  # O(1)
            return 2  # O(1)
        note = None  # O(1)
        if a.note is not None:  # before any pane | O(1)
            if not Path(a.note).is_file():  # O(1)
                print(f"error: note not found: {Path(a.note).resolve()}", file=sys.stderr)  # O(1)
                return 2  # O(1)
            note = Path(a.note).read_text(encoding="utf-8")  # O(file)
            bad = outside_paths(note, state.project(sd), sd)  # O(file)
            if bad:  # O(1)
                print(outside_error("note", Path(a.note).resolve(), bad, sd), file=sys.stderr)  # O(1)
                return 2  # O(1)
        if a.role == "writer" and not a.brief:  # O(1)
            print("error: --role writer needs --brief naming its Output: file", file=sys.stderr)  # O(1)
            return 2  # O(1)
        output = None  # O(1)
        if a.role == "writer" and a.brief and Path(a.brief).is_file():  # a missing brief is reported below | O(file)
            try:  # O(1)
                output = str(writer_output(a.brief, state.project(sd), sd))  # O(file)
            except ValueError as e:  # O(1)
                print(f"error: {e}", file=sys.stderr)  # O(1)
                return 2  # O(1) before any pane
        tmo = 540000  # O(1)
        if a.brief or (is_lead and a.wait):  # before any pane: a missing brief or a bad timeout spawns nothing | O(1)
            if a.brief and not Path(a.brief).is_file():  # O(1)
                print(f"error: brief not found: {Path(a.brief).resolve()}", file=sys.stderr)  # O(1)
                return 2  # O(1)
            if a.brief and not is_lead:  # a lead reads outside its worktree (#1015) | O(file)
                import orchestrator  # noqa: E402 | O(1)
                try:  # O(1)
                    plan = orchestrator.plan_file(sd, a.plan)  # O(L)
                except Exception:  # noqa: BLE001 | no readable plan: the brief alone is checked | O(1)
                    plan = None  # O(1)
                why = importlib.import_module("fleet_io").brief_refusal(sd, a.brief, a.role, plan=plan)  # O(file)
                if why:  # O(1)
                    print(why, file=sys.stderr)  # O(1)
                    return 2  # O(1)
                why = report_refusal(sd, a.brief, a.label or Path(a.brief).stem, state.project(sd))  # O(file)
                if why:  # O(1)
                    print(why, file=sys.stderr)  # O(1)
                    return 2  # O(1)
            try:  # O(1)
                tmo = importlib.import_module("fleet_io").parse_timeout(a.timeout or "540000")  # O(len)
            except ValueError as e:  # O(1)
                print(f"error: {e}", file=sys.stderr)  # O(1)
                return 2  # O(1)
        saved, t0 = {}, time.monotonic()  # O(1)
        def restore():  # O(1)
            for s_, h in saved.items():  # O(1)
                signal.signal(s_, h)  # O(1)
            saved.clear()  # O(1)
        if threading.current_thread() is threading.main_thread():  # a handler can only be set there | O(1)
            for s_ in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):  # O(1)
                saved[s_] = signal.signal(s_, _raise_stopped)  # O(1)
        try:  # O(1)
            return _spawn_cmd(a, sd, note, output, tmo, restore)  # O(R * (spawn + send))
        except _Stopped as e:  # O(1)
            restore()  # O(1)
            return _stopped_line(e.name, time.monotonic() - t0)  # O(w)
        except Exception as e:  # noqa: BLE001 | a bug must end as one BLOCKED line, the traceback on stderr | O(1)
            restore()  # O(1)
            import traceback  # noqa: E402 | O(1)
            traceback.print_exc()  # O(1)
            return _stopped_line(None, 0, f"fleet spawn: {type(e).__name__}: {e}")  # O(w)
        finally:  # O(1)
            restore()  # O(1)
    elif a.cmd == "collect":  # O(len + w)
        return importlib.import_module("fleet_io").recollect(sd, a.id)  # O(len + w)
    elif a.cmd == "report":  # O(ids * file)
        return _report(sd, a.ids)  # O(ids * file)
    elif a.cmd == "stop":  # O(w)
        for wid in stop(sd, a.ids, a.all):  # O(w)
            print(f"stopped {wid}")  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
