#!/usr/bin/env python3
"""Herdr fleet CLI: workers are Claude Code sessions in Herdr panes, one per pane.

    fleet.py on [--accounts A,B] [--plan P] | off | status [--all]
    fleet.py spawn [--role R] [--tier T] --plan P | stop [IDS...] [--all]
    fleet.py spawn --for-dispatch --plan P    (one dispatch round: dispatch, spawn, send)
    fleet.py spawn --for-review Tn [Tm ...] | --package X --plan P    (write the review brief, start a package-reviewer, send it)
    fleet.py report IDS... [--plan P]    (print a worker's last report, or a report by label; read-only)
    fleet.py send | keys | wait     (delegated to fleet_io)
    fleet.py run --layer headless|tui|evals     (delegated to fleet_layer)
    fleet.py restore [--plan P]     (after a Herdr restart: delegated to fleet_restore)

Roles: implementer (default), fixer, package-reviewer, final-reviewer, research, checker, writer (see fleet_roles). Exit 2 with
`error: ...` on stderr for an unknown role or tier.
MCP (#576): implementers, fixers and package reviewers get the servers their project names through a generated `--mcp-config`; a server that fails its check is left out with one stderr line.
Exit 3 with a `BLOCKED: ...` line on stdout when a worker cannot start. `--for-dispatch` prints one
`Wn Tn[,Tm] sent` line per worker, `BLOCKED: Tn[,Tm] not sent (<reason>)` for a line that got no worker
(the other lines still go out; exit 3); the Wave 0 line starts a haiku worker and sends it `briefs/wave0.md`.
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
`stop` drops the worker's tree `worker-<id>` unless a live process marks it busy (#614).
`spawn` (not `--for-dispatch`, which dispatch gates itself) refuses on a nearly full disk: `BLOCKED: fleet spawn: disk: ...`, exit 3; below the warn level it warns on stderr (#614).
`sl fleet restore` re-launches every worker and lead of the run after a Herdr restart, each resuming its own Claude session; `status` names it after a worker found dead (#577).
`spawn --for-review|--package ... --note FILE` appends FILE to the generated review brief under `## Coordinator notes` (#604).
`spawn --role writer --brief F` needs an `Output: <file>` line in F: the writer may write only that file, inside the project or the run folder (#604).
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
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import accounts as ac  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import machine_load as ml  # noqa: E402 | O(1)
import pool  # noqa: E402 | O(1)
import routing  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

TRUST = "Yes, I trust this folder"  # O(1)
SHELL_PAUSE_S = 3.0  # O(1)
SHELL_MSG = "not an available shell"  # O(1)
PASS_THROUGH = ("CLAUDE_CODE_PLUGIN_CACHE_DIR",)  # O(1)
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


def _register_pool(sd, wid, tier, account):  # O(w)
    with fs.locked(sd):  # two parallel spawns must not drop each other's entry; callers hold no fs lock here | O(1) plus wait
        p = Path(sd) / "pool.json"  # O(1)
        data = pool.load(p)  # O(w)
        ag = pool.add(data, wid, tier)  # O(w)
        ag.update({"backend": "herdr", "account": account})  # O(1)
        pool.save(p, data)  # O(w)


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


def choose_account(sd, model, env, avoid=None):  # O(a * e + w) plus herdr and usage calls
    """The account a new worker starts on: (account, its config dir, the claude-profile account other sessions count it on).

    Exit 3 with a `BLOCKED: ...` line when no account has headroom or no config dir is known."""
    sd = Path(sd)  # O(1)
    data = fs.load(sd)  # O(w)
    usage, listing = ac.read_usage(env), ac.read_listing(env)  # O(1) plus subprocess time
    entries = data.get("accounts") or [a["name"] for a in (usage.get("accounts") or listing.get("accounts") or [])] or ["current"]  # O(a)
    entries = [e for e in entries if ac.entry_name(e) != avoid]  # the account of a slow first try | O(a)
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
            running[v.get("account")] = running.get(v.get("account"), 0) + 1  # O(1)
    for n in allowed:  # O(a)
        if machine.get(alias.get(n, n)):  # accounts nobody else uses stay out of the dict | O(1)
            running[n] = running.get(n, 0) + machine[alias.get(n, n)]  # O(1)
    account = ac.pick_account(usage, allowed, running, model, alias)  # O(a)
    if account is None:  # a path entry or `current` unknown to the usage report has no usage data, not a verdict; an aliased one has, and it said no | O(a)
        known = {u.get("name") for u in usage.get("accounts") or []}  # O(a)
        account = next((ac.entry_name(e) for e in entries if (ac.is_path(e) or e == "current") and ac.entry_name(e) not in known and ac.entry_name(e) not in alias), None)  # O(a)
    if account is None:  # O(1)
        print("BLOCKED: no account with headroom")  # O(1)
        for r in ac.reasons(usage, allowed, model, alias):  # O(a)
            print(r)  # O(1)
        raise SystemExit(3)  # O(1)
    cdir = ac.account_dir(listing, entry_of.get(account, account), env)  # O(a)
    if cdir is None:  # O(1)
        hint = "" if listing.get("accounts") else " (claude-profile list unavailable; pass a config dir path instead)"  # O(1)
        print(f"BLOCKED: no config dir for account {account}{hint}")  # O(1)
        raise SystemExit(3)  # O(1)
    return account, cdir, alias.get(account, account)  # O(1)


def open_pane(sd, wid, cwd, env, record):  # O(w + p) plus herdr calls
    """Open the pane of worker `wid` (workspace, split or tab), save `record` plus its pane id as the worker, return the pane id.

    A HerdrError propagates; the caller reports it."""
    sd = Path(sd)  # O(1)
    with fs.locked(sd):  # layout decision and herdr call are one step; fs write helpers lock too, so save directly | O(1) plus wait
        data = fs.load(sd)  # O(w)
        for attempt in (0, 1):  # a split from a pane closed outside fleet fails once; the retry uses another pane | O(1)
            live = [v for v in data["workers"].values() if v.get("state") != "stopped"]  # O(w)
            src = [v["pane_id"] for v in live if v.get("state") != "blocked"]  # panes still open | O(w)
            if not data.get("workspace_id") or not src:  # O(1)
                ws, pane = hc.create_workspace(data.get("label") or "sl:fleet", cwd, env)  # O(1)
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
                    if v.get("pane_id") == bad and v.get("state") != "stopped":  # O(1)
                        v.update({"state": "stopped", "task": None})  # O(1)
                        _pool_drop(sd, k)  # we hold fs.locked(sd); pool.json uses the same lock | O(w)
                fs.save(sd, data)  # O(w)
                continue  # O(1)
            if how == "tab":  # a full or short tab: the next worker opens a new one in the same workspace | O(1)
                pane = hc.create_tab(data["workspace_id"], cwd, env)[1]  # O(1)
            break  # O(1)
        data["workers"][wid] = {**record, "pane_id": pane}  # O(1)
        fs.save(sd, data)  # O(w)
    return pane  # O(1)


def _retry_account(sd, model, env, avoid):  # O(a * e + w): another account than `avoid`, else the same one
    try:  # O(1)
        with contextlib.redirect_stdout(io.StringIO()):  # O(1)
            return choose_account(sd, model, env, avoid=avoid)  # O(a * e + w)
    except SystemExit as e:  # no other account has headroom | O(1)
        if e.code != 3:  # O(1)
            raise  # O(1)
    return choose_account(sd, model, env)  # O(a * e + w)


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


def spawn(sd, plan, tier, project, cfg=None, env=None, role="implementer", over=False, machine_wait=100.0, output=None):  # O(a * e + w) plus herdr calls
    """One worker; a start that stays slow is retried once on another account.
    Implementers, fixers and package reviewers keep the MCP servers their project names or the stack default (`xcode` for an Xcode project), each checked first (#576).
    Every worker starts lean (#377): no MCP servers, Chrome, skills or slash commands; Artifact, ListAgents, ReadNotifications and ReportFindings denied (LEAN_FLAGS, LEAN_DENY)."""
    busy = ml.gate(f"fleet spawn ({role})", machine_wait, over)  # the first attempt only; the retry below is the same spawn | O(wait)
    if busy:  # O(1)
        print(f"BLOCKED: fleet spawn: {busy}; rerun later, or pass --over-limit")  # O(1)
        raise SystemExit(3)  # O(1) before any pane
    try:  # O(1)
        return _spawn(sd, plan, tier, project, cfg, env, role, None, output)  # O(a * e + w)
    except (_Slow, NoShell) as first:  # O(1)
        return _spawn(sd, plan, tier, project, cfg, env, role, first, output)  # O(a * e + w)


def _spawn(sd, plan, tier, project, cfg, env, role, after, output=None):  # O(a * e + w) plus herdr calls
    import fleet_roles  # noqa: E402 | O(1)
    sd = Path(sd)  # O(1)
    base = dict(os.environ) if env is None else env  # O(env)
    cfg = cfg or routing.load_cfg()  # O(file)
    launch = fleet_roles.launch(role, tier, cfg, output=output)  # a ValueError (unknown role or tier) reaches `main` | O(file)
    agent, model = launch["agent"], launch["model"]  # O(1)
    prime = "prime-haiku.md" if model == "haiku" else "prime.md"  # O(1)
    if launch["prime"] and not (sd / prime).is_file():  # no pane, account or worker id for a worker that cannot read its prime | O(1)
        flag = "--tier haiku " if model == "haiku" else ""  # O(1)
        print(f"BLOCKED: no {sd.resolve() / prime}; run build_prime {flag}--plan PLAN first")  # O(1)
        raise SystemExit(3)  # O(1)
    fresh = isinstance(after, NoShell)  # O(1)
    tail = "" if after is None else f"; retried in a fresh pane after {after.wid}" if fresh else f"; retried after {after.wid} on {after.account}"  # O(1)
    account, cdir, shared = choose_account(sd, model, base) if after is None or fresh else _retry_account(sd, model, base, after.account)  # O(a * e + w)
    if fresh:  # O(1)
        print(f"{after.wid} {after.why}; retrying in a fresh pane", file=sys.stderr)  # O(1)
    elif after is not None:  # O(1)
        print(f"{after.wid} account {after.account} {after.why}; retrying on account {account}", file=sys.stderr)  # O(1)
    wid = fs.next_id(sd)  # O(w)
    name = fs.agent_name(sd, wid, taken=_live_names())  # herdr rejects `W1`; every herdr agent call below uses this name | O(a)
    wenv = {**worker_env(sd, wid, agent, cdir, base), **fleet_roles.env(role)}  # O(1)
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
    argv = lean_argv(launch["argv"], path, fleet_mcp.deny(names) if names else ())  # O(n)
    if names and fleet_mcp.usage_note(names):  # O(k)
        argv += ["--append-system-prompt", fleet_mcp.usage_note(names)]  # O(1)
    try:  # a state dir outside the project (a worktree run) is not readable by default | O(1)
        sd.resolve().relative_to(Path(project).resolve())  # O(len)
    except ValueError:  # O(1)
        argv += ["--add-dir", str(sd.resolve())]  # O(1)
    record = {"name": name, "account": account, "agent": agent, "tier": tier or model, "state": "starting", "task": None, "role": role, "one_turn": launch["one_turn"],  # O(1)
              "launch": {"argv": argv, "env": wenv, "cwd": cwd}}
    if names:  # O(1)
        record["mcp"] = names  # O(1)
    try:  # O(1)
        pane = open_pane(sd, wid, cwd, wenv, record)  # O(w + p)
        with contextlib.suppress(OSError):  # the registry only spreads accounts; an unwritable one must not stop a spawn | O(1)
            fs.register_agent(name, shared)  # other sessions count this worker on its claude-profile account | O(1)
    except hc.HerdrError as e:  # O(1)
        _blocked(sd, wid, account, f"startup: {e.message or e.code}{tail}")  # O(1)
    def fail(why, screen=None, named=True, slow=False, shell=False):  # O(s + w)
        fs.set_state(sd, wid, "blocked")  # O(w)
        try:  # O(1)
            hc.close_pane(pane)  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
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
        if not launch["prime"]:  # a one-turn worker may stand on the trust dialog too (#514) | O(1)
            seen = ""  # a failed read is an empty screen, as in fleet_lead | O(1)
            try:  # O(1)
                seen = hc.read_screen(name, SCREEN_ROWS)  # O(s)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
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
        if _trust_open(screen):  # O(s)
            fail(f"no READY: the folder trust dialog is still open in {cwd}; accept it once per account (start claude there on account {account}), then rerun", screen, named=False)  # O(s)
        fail("no READY" + size + gone, screen, named=False)  # O(s)
    if launch["pool"]:  # the pool entry first: a concurrent round must not see a ready worker outside the pool | O(1)
        _register_pool(sd, wid, model, account)  # O(w)
    _store_session(sd, wid, name)  # O(w)
    fs.set_state(sd, wid, "ready")  # O(w)
    _launch_line(sd, wid, agent, model, account, pane)  # O(1)
    print(f"{wid} account={account} pane={pane} agent={agent}" + ("" if role == "implementer" else f" role={role}") + (f" mcp={','.join(names)}" if names else ""))  # O(1)
    return {"id": wid, "account": account, "pane_id": pane, "agent": agent, "model": model, "role": role}  # O(1)


def _machine_line():  # O(p): the machine measurement as the status line; nothing while both checks are off or on any error
    try:  # O(1)
        if ml.enabled():  # O(1)
            print(ml.snapshot_text())  # O(p)
    except Exception:  # noqa: BLE001 | a status line must not fail the status | O(1)
        pass  # O(1)


def _spawn_quiet(sd, plan, tier, project, over=False, machine_wait=100.0):  # O(spawn) -> (worker dict, None) or (None, reason of the BLOCKED lines)
    buf = io.StringIO()  # O(1)
    try:  # spawn prints its own worker or BLOCKED line; a dispatch round reports one line per dispatch line instead | O(1)
        with contextlib.redirect_stdout(buf):  # O(1)
            return spawn(sd, plan, tier, project, over=over, machine_wait=machine_wait), None  # O(spawn)
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
    return [k for k, v in fs.workers(sd).items() if v.get("state") == "ready" and (v.get("role") or "implementer") == "implementer" and k not in listed]  # O(w)


def for_dispatch(sd, plan, project, over=False, machine_wait=100.0):  # O(R * (spawn + send)): one dispatch round, a line after the other
    import dispatch as dp  # noqa: E402 | O(1) lazy: only this command needs it
    import fleet_io as fio  # noqa: E402 | O(1) lazy
    import orchestrator  # noqa: E402 | O(1) lazy
    sd = Path(sd)  # O(1)
    plan = plan or dp.load_pool(sd / "pool.json").get("plan") or dp.nt.DEFAULT_PLAN  # as `dispatch` | O(pool bytes)
    shut = orchestrator.require(plan, "dispatch")  # human mode waits for approval, as `dispatch` | O(file)
    if shut:  # O(1)
        return shut  # O(1)
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
    state_of = {k: v.get("state") for k, v in fs.workers(sd).items()}  # O(w)
    ids = [k for k in evict if state_of.get(k) == "ready"]  # an evicted busy worker finishes its task | O(w)
    ids += [k for k in _dropped_ready(sd) if k not in ids]  # #424: dropped by an earlier round | O(w)
    for wid in stop(sd, ids):  # O(w) plus herdr calls
        print(f"stopped {wid}")  # O(1)
    sl, root = str(fio.HERE / "sl"), str(fio.HERE.parents[2])  # O(1)
    blocked = False  # O(1)
    deadline = time.monotonic() + machine_wait  # one wait budget for the whole round | O(1)
    for tasks, decision in lines:  # O(R) iterations
        why, wid, brief = None, None, None  # O(1)
        if decision.startswith("wave0"):  # one haiku worker, sent the Wave 0 brief that `wave0 --plan` wrote | O(1)
            brief = sd / "briefs" / "wave0.md"  # O(1)
            if brief.is_file():  # no worker for a brief that is not there | O(1)
                tier = (re.search(r"\btier=(\S+)", decision) or [None, "haiku"])[1]  # O(len)
                w, why = _spawn_quiet(sd, plan, tier, project, over, max(0.0, deadline - time.monotonic()))  # O(spawn)
                wid = w["id"] if w else None  # O(1)
            else:  # O(1)
                why = "no .superlite/briefs/wave0.md; run wave0 --plan PLAN"  # O(1)
        elif decision.startswith("fresh"):  # O(1)
            tier = (re.search(r"\btier=(\S+)", decision) or [None, "sonnet"])[1]  # O(len)
            w, why = _spawn_quiet(sd, plan, tier, project, over, max(0.0, deadline - time.monotonic()))  # O(spawn)
            wid = w["id"] if w else None  # O(1)
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
        if why is not None:  # O(1)
            if SHELL_MSG in why:  # O(len)
                why += "; rerun sl fleet spawn --for-dispatch"  # O(1)
            print(f"BLOCKED: {tasks} not sent ({why})")  # O(1)
            blocked = True  # the next line still goes out | O(1)
    try:  # a hint failure must not fail the round | O(1)
        for tid, reasons in fio.review_hints(sd, plan):  # O(n) iterations
            print(f"review: {tid} ({'; '.join(reasons)}); run {sl} fleet spawn --for-review {tid} --plan {plan}")  # O(k)
    except (ValueError, OSError, KeyError) as e:  # O(1)
        print(f"warning: no review hints ({e})", file=sys.stderr)  # O(1)
    return 3 if blocked else 0  # O(1)


def for_review(sd, plan, project, tasks, package=None, over=False, machine_wait=100.0, note=None):  # O(L + e + spawn + send): a package-reviewer for TASKS (or PACKAGE's committed tasks), brief written and sent
    import fleet_io as fio  # noqa: E402 | O(1) lazy
    sd = Path(sd)  # O(1)
    pp = sd / "pool.json"  # O(1)
    plan = plan or (pool.load(pp).get("plan") if pp.exists() else None) or fio.nt.DEFAULT_PLAN  # as for_dispatch | O(pool bytes)
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
    label = "review-" + (re.sub(r"[^a-z0-9]+", "-", package.lower()).strip("-") if package else ",".join(tasks))  # O(len)
    f = sd / "briefs" / (label.replace(",", "-") + ".md")  # O(1)
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    body = fio.review_brief(sd, plan, tasks, str(fio.HERE / "sl"), str(fio.HERE.parents[2]), package)  # O(L + e + B)
    if note and note.strip():  # O(len)
        body = body.rstrip("\n") + "\n\n## Coordinator notes\n\nThese notes add to the review above; review every task and file it lists all the same.\n\n" + note.strip() + "\n"  # O(B)
    f.write_text(body, encoding="utf-8")  # O(B)
    w = spawn(sd, plan, None, project, role="package-reviewer", over=over, machine_wait=machine_wait)  # prints its own Wn or BLOCKED line; exit 3 stays | O(a * e + w)
    try:  # O(1)
        fio.send_brief(sd, w["id"], str(f), label)  # prints `Wn review-.. sent` | O(w + len)
    except (fio.hc.HerdrError, OSError, KeyError) as e:  # O(1)
        stop(sd, [w["id"]])  # close the reviewer just spawned, so a rerun does not leave two | O(w)
        print(f"BLOCKED: {label} not sent ({getattr(e, 'message', '') or getattr(e, 'code', '') or e})")  # O(1)
        return 3  # O(1)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        data["workers"][w["id"]]["review"] = tasks  # O(1)
        fs.save(sd, data)  # O(w)
    return 0  # O(1)


def stop(sd, ids=None, all_=False, keep_workspace=False):  # O(w) plus herdr calls
    sd = Path(sd)  # O(1)
    live = {k: v for k, v in fs.workers(sd).items() if v.get("state") != "stopped"}  # O(w)
    targets = list(live) if all_ else [i for i in (ids or []) if i in live]  # O(w)
    p = sd / "pool.json"  # O(1)
    pdata = pool.load(p) if p.exists() else None  # O(w)
    for wid in targets:  # O(w)
        if live[wid].get("role") == "lead" and live[wid].get("lead_sd") and Path(live[wid]["lead_sd"]).is_dir():  # a lead's workers exit before the lead | O(w)
            try:  # O(1)
                stop(Path(live[wid]["lead_sd"]), all_=True)  # O(w)
            except Exception:  # noqa: BLE001 | O(1)
                pass  # O(1)
        try:  # O(1)
            hc.exit_agent(fs.name_of(sd, wid, live[wid]))  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        try:  # O(1)
            hc.close_pane(live[wid]["pane_id"])  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        fs.set_state(sd, wid, "stopped")  # O(w)
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
    if data.get("workspace_id") and not [v for v in data["workers"].values() if v.get("state") != "stopped"]:  # O(w)
        fs.set_workspace(sd, None, None)  # state first: closing the workspace kills the pane of a caller that runs inside it | O(w)
        if not keep_workspace:  # `off` closes it itself, after it has said so | O(1)
            try:  # O(1)
                hc.close_workspace(data["workspace_id"])  # O(1)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
    return targets  # O(1)


def _sd(a):  # O(d)
    return Path(state.resolve(getattr(a, "plan", None))).resolve()  # O(d)


def _plan_arg(argv):  # the value of the last --plan P or --plan=P (argparse's pick), else None | O(n)
    found = None  # O(1)
    for i, x in enumerate(argv):  # O(n)
        if x == "--plan" and i + 1 < len(argv):  # O(1)
            found = argv[i + 1]  # O(1)
        elif x.startswith("--plan="):  # O(1)
            found = x[len("--plan="):]  # O(1)
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


def mark_dead(sd, wid):  # stopped, dead, off the pool; no pane is closed | O(w)
    sd = Path(sd)  # O(1)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        w = data["workers"].get(wid)  # O(1)
        if w is None:  # O(1)
            return  # O(1)
        w.update({"state": "stopped", "dead": True, "was": w.get("was") if w.get("dead") else w.get("state"), "last_task": w.get("task") or w.get("last_task"), "task": None})  # O(1)
        fs.save(sd, data)  # O(w)
        _pool_drop(sd, wid)  # O(w)


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


def _follow(plan):  # O(w)
    """Move the session's fleet into the folder this command names; one stderr line when it moved, a warning when it failed."""
    try:  # O(1)
        sd = Path(state.resolve(plan)).resolve()  # O(d)
    except (state.Foreign, OSError):  # O(1)
        return  # O(1)
    try:  # O(1)
        r = fs.follow(sd)  # O(w)
    except Exception as e:  # noqa: BLE001 | a failed move must not stop the command | O(1)
        print(f"fleet: warning: fleet not moved ({e})", file=sys.stderr)  # O(1)
        return  # O(1)
    if r:  # O(1)
        print(f"fleet: this session's fleet moved from {r['from']} to {r['to']} ({r['workers']} workers)", file=sys.stderr)  # O(1)


def main(argv=None):  # O(w) plus command cost
    argv = list(sys.argv[1:] if argv is None else argv)  # O(n)
    plan = _plan_arg(argv)  # O(n)
    why = _plan_problem(plan) if plan is not None else ""  # O(d)
    if why:  # O(1)
        print(f"error: --plan {plan}: {why}; pass the plan file or the run's .superlite folder, or leave --plan out to use the current directory's run", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if argv and argv[0] != "name" and not argv[0].startswith("-"):  # Every subcommand but name first moves this session's fleet into its folder (#580) | O(1)
        _follow(plan)  # O(w)
    if argv and argv[0] in ("send", "keys", "wait"):  # O(1)
        return importlib.import_module("fleet_io").main(argv)  # O(1) delegated
    if argv and argv[0] == "run":  # a layer run: a shell pane per layer | O(1)
        return importlib.import_module("fleet_layer").main(argv[1:])  # O(1) delegated
    if argv and argv[0] == "restore":  # after a Herdr restart: every pane again | O(1)
        return importlib.import_module("fleet_restore").main(argv[1:])  # O(1) delegated
    p = argparse.ArgumentParser(prog="fleet.py")  # O(1)
    sub = p.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("on", help="turn fleet mode on")  # O(1)
    s.add_argument("--accounts", default="")  # O(1)
    s.add_argument("--plan")  # O(1)
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
    s.add_argument("--machine-wait", type=float, default=100.0)  # O(1) seconds a spawn waits for room on the machine
    s.add_argument("--for-dispatch", action="store_true")  # O(1) run dispatch, spawn per `fresh` line, send each line's tasks
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
    for n, h in (("send", "send tasks, a brief or text to a worker"), ("keys", "send keys to a worker's pane"),  # O(1) delegated before parsing: these feed --help only
                 ("wait", "wait for busy workers to report"), ("run", "run a test layer in a shell pane"),  # O(1)
                 ("restore", "re-launch every worker after a Herdr restart")):  # O(1)
        sub.add_parser(n, help=h)  # O(1)
    a = p.parse_args(argv)  # O(n)
    sd = _sd(a)  # O(d)
    if a.cmd == "name":  # O(1) before any herdr call; fleet mode may be off
        print(fs.full_name(sd, a.ident))  # O(1)
        return 0  # O(1)
    if a.cmd == "on":  # O(1)
        raw = a.accounts or os.environ.get("SUPERLITE_FLEET_ACCOUNTS", "")  # O(1) flag wins over env
        accts = [x.strip() for x in raw.split(",") if x.strip()]  # O(a)
        fs.set_on(sd, fs.full_name(sd), accts)  # O(w)
        if any(not ac.is_path(x) and x != "current" for x in accts) and not ac.read_listing().get("accounts"):  # O(a) plus subprocess time
            print("fleet: warning: claude-profile list unavailable; account names cannot be resolved, pass config dir paths instead", file=sys.stderr)  # O(1)
        print(f"fleet: on accounts={','.join(accts) or 'auto'}", file=sys.stderr)  # O(a) stdout stays clean for worker lines
    elif a.cmd == "off":  # O(1)
        ws = fs.load(sd).get("workspace_id")  # read before stop clears it | O(w)
        stop(sd, all_=True, keep_workspace=True)  # O(w)
        fs.set_off(sd)  # O(1)
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
            _machine_line()  # O(p)
            if hint:  # O(1)
                print(hint)  # O(1)
            return 0  # O(1)
        print("fleet: on")  # O(1)
        import fleet_io as fio  # noqa: E402 | O(1) lazy
        pooled = {x["id"]: x for x in pool.load(sd / "pool.json").get("agents") or []}  # O(w)
        newly, ended = [], []  # O(1)
        for wid, w in fs.workers(sd).items():  # probe: a gone agent is dead, an unreachable herdr changes nothing | O(w)
            if w.get("state") in ("ready", "busy") and w.get("role") != "layer" and agent_gone(fs.name_of(sd, wid, w)):  # O(1)
                mark_dead(sd, wid)  # O(w)
                newly.append(wid)  # O(1)
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
            print(f"{wid} {shown} account={w.get('account')} pane={w.get('pane_id')} task={w.get('task') or '-'}" + (f" role={role}" if role and role != "implementer" else "") + tail)  # O(1)
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
        if not fs.is_on(sd):  # a worktree run keeps its own fleet.json: the main checkout's `fleet on` does not reach it (#355) | O(w)
            hint = "sl fleet on" + (f" --plan {a.plan}" if a.plan else "")  # O(1) the same --plan resolves the same state dir
            moved = fs.load(sd).get("moved_to")  # O(w)
            tail = f"this fleet moved to {moved}: pass --plan {moved}" if moved else "a worktree run keeps its own fleet.json"  # O(1)
            print(f"BLOCKED: fleet is off in {sd}; run {hint} first" + (f"; {tail}" if moved else f" ({tail})"))  # O(1)
            return 3  # O(1) before dispatch: no task marked, no pane, no worker id
        if a.cmd == "spawn" and a.wait and not a.brief:  # before any pane | O(1)
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
        if a.role == "writer" and not a.brief:  # O(1)
            print("error: --role writer needs --brief naming its Output: file", file=sys.stderr)  # O(1)
            return 2  # O(1)
        output = None  # O(1)
        if a.role == "writer" and a.brief and Path(a.brief).is_file():  # a missing brief is reported below | O(file)
            try:  # O(1)
                output = str(writer_output(a.brief, state.git_root(sd) or sd.parent, sd))  # O(file)
            except ValueError as e:  # O(1)
                print(f"error: {e}", file=sys.stderr)  # O(1)
                return 2  # O(1) before any pane
        tmo = 540000  # O(1)
        if a.brief:  # before any pane: a missing brief or a bad timeout spawns nothing | O(1)
            if not Path(a.brief).is_file():  # O(1)
                print(f"error: brief not found: {Path(a.brief).resolve()}", file=sys.stderr)  # O(1)
                return 2  # O(1)
            try:  # O(1)
                tmo = importlib.import_module("fleet_io").parse_timeout(a.timeout or "540000")  # O(len)
            except ValueError as e:  # O(1)
                print(f"error: {e}", file=sys.stderr)  # O(1)
                return 2  # O(1)
        if (a.for_dispatch or a.for_review is not None or a.package) and a.plan and Path(a.plan).is_dir():  # a run folder names its plan file (#508) | O(d)
            import orchestrator  # noqa: E402 | O(1) lazy
            found = orchestrator.plan_file(state.plan_dir(a.plan))  # O(file)
            if found is None:  # O(1)
                print(f"error: --plan {a.plan} is a run folder with no plan file (stable.json, pool.json or plan.md name none); pass the plan file", file=sys.stderr)  # O(1)
                return 2  # O(1) before dispatch: no pane, no worker id
            a.plan = str(found)  # O(1)
        if not a.for_dispatch:  # dispatch gates the disk itself (#614) | O(1)
            import trees  # noqa: E402 | O(1) lazy
            level, line = trees.disk_gate(state.git_root(sd) or sd.parent)  # O(1)
            if level == "refuse":  # O(1)
                print(f"BLOCKED: fleet spawn: {line}")  # O(1)
                return 3  # O(1) before any pane
            if level == "warn":  # O(1)
                print(f"fleet: {line}", file=sys.stderr)  # O(1)
        if a.for_dispatch:  # O(1)
            return for_dispatch(sd, a.plan, state.git_root(sd) or sd.parent, a.over_limit, a.machine_wait)  # O(R * (spawn + send))
        if a.for_review is not None or a.package:  # O(1)
            ids = [x for v in a.for_review or [] for x in re.split(r"[,\s]+", v) if x]  # O(len)
            return for_review(sd, a.plan, state.git_root(sd) or sd.parent, ids, a.package, a.over_limit, a.machine_wait, note)  # O(L + e + spawn + send)
        try:  # O(1)
            w = spawn(sd, a.plan or sd, a.tier, state.git_root(sd) or sd.parent, role=a.role, over=a.over_limit, machine_wait=a.machine_wait, output=output)  # O(w)
        except ValueError as e:  # an unknown role or tier | O(1)
            print(f"error: {e}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if a.brief:  # O(1)
            import fleet_io as fio  # noqa: E402 | O(1) lazy
            label = a.label or Path(a.brief).stem  # O(1)
            try:  # O(1)
                fio.send_brief(sd, w["id"], a.brief, a.label)  # O(w)
            except (hc.HerdrError, OSError, KeyError) as e:  # a worker that got no brief is stopped, not left ready | O(w)
                stop(sd, [w["id"]])  # O(w)
                print(f"BLOCKED: {w['id']} {label} not sent ({getattr(e, 'message', '') or e})")  # O(1)
                return 3  # O(1)
            if a.wait:  # O(1)
                fio.wait(sd, [w["id"]], tmo)  # O(wait)
    elif a.cmd == "report":  # O(ids * file)
        return _report(sd, a.ids)  # O(ids * file)
    elif a.cmd == "stop":  # O(w)
        for wid in stop(sd, a.ids, a.all):  # O(w)
            print(f"stopped {wid}")  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
