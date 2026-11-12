"""Spawn a batch lead: a fleet worker of main's run, role `lead`, in its own worktree with its own run state.

Not a CLI. `backlog_run` calls `spawn_lead`. A lead gets no prime and no pool entry; its brief arrives as the first message.
A lead starts with `--autocompact` set to main's window (`main_window`, #464). A start that stays slow is retried once on another account (#454).
A pane still no shell after that retry is closed and the lead starts once more in a fresh pane (#551).
A folder trust dialog still open after a successful start is accepted (#514).
"""
import json  # O(1)
import os  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet  # noqa: E402 | O(1)


NoShell = fleet.NoShell  # moved to fleet.py: workers retry in a fresh pane too | O(1)


DEFAULT_WINDOW = 400000  # O(1) the window /superlite:setup offers


def _pos(v):  # O(1)
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None  # O(1)


def main_window(env, model):  # O(k) main's auto-compact window: env variable, user settings, model settings, else the default
    try:  # O(1)
        n = _pos(int(env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "")))  # O(1)
    except ValueError:  # O(1)
        n = None  # O(1)
    if n:  # O(1)
        return n  # O(1)
    cdir = env.get("CLAUDE_CONFIG_DIR")  # O(1)
    path = Path(cdir) / "settings.json" if cdir else Path(env.get("HOME") or Path.home()) / ".claude" / "settings.json"  # O(1)
    try:  # O(1)
        data = json.loads(path.read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return DEFAULT_WINDOW  # O(1)
    if not isinstance(data, dict):  # O(1)
        return DEFAULT_WINDOW  # O(1)
    n = _pos(data.get("autoCompactWindow"))  # O(1)
    if n:  # O(1)
        return n  # O(1)
    ms = data.get("modelSettings")  # O(1)
    if isinstance(ms, dict):  # O(1)
        for key in sorted(ms):  # O(k log k)
            if model in key and isinstance(ms[key], dict) and _pos(ms[key].get("autoCompactWindow")):  # O(1)
                return ms[key]["autoCompactWindow"]  # O(1)
    return DEFAULT_WINDOW  # O(1)


def lead_argv(sl_path, model, window=None):  # O(1)
    argv = ["--model", model, "--permission-mode", "auto", "--allowedTools", "Bash(maxapp ship *)",  # O(1)
            f"Bash({sl_path} backlog ship *)", "--disallowedTools", "AskUserQuestion"]
    if window is not None:  # O(1)
        argv += ["--autocompact", f"{window // 1000}k" if window % 1000 == 0 else str(window)]  # O(1)
    return argv  # O(1)


def lead_env(main_sd, lead_sd, wid, config_dir, base_env, accounts):  # O(a)
    env = {"SUPERLITE_FLEET_WORKER": wid, "SUPERLITE_FLEET_AGENT": "lead", "SUPERLITE_FLEET_ROLE": "lead",  # O(1)
           "SUPERLITE_STATE_DIR": str(Path(lead_sd).resolve()), "SUPERLITE_FLEET_PARENT_DIR": str(Path(main_sd).resolve()),
           "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "0"}
    if accounts:  # O(1)
        env["SUPERLITE_FLEET_ACCOUNTS"] = ",".join(accounts)  # O(a)
    if not fleet.ac.is_default_dir(config_dir, base_env):  # O(1)
        env["CLAUDE_CONFIG_DIR"] = config_dir  # O(1)
    for k in fleet.PASS_THROUGH:  # O(1)
        if base_env.get(k):  # O(1)
            env[k] = base_env[k]  # O(1)
    return env  # O(1)


def spawn_lead(main_sd, worktree, model="opus", env=None):  # O(a * e + w) plus herdr calls
    base = dict(os.environ) if env is None else env  # O(env)
    try:  # O(1)
        return _spawn_lead(main_sd, worktree, model, base, None)  # O(a * e + w)
    except (fleet._Slow, NoShell) as first:  # O(1)
        return _spawn_lead(main_sd, worktree, model, base, first)  # O(a * e + w)


def _spawn_lead(main_sd, worktree, model, base, after):  # O(a * e + w) plus herdr calls
    fs, hc = fleet.fs, fleet.hc  # O(1)
    main_sd, worktree = Path(main_sd), Path(worktree)  # O(1)
    fresh = isinstance(after, NoShell)  # O(1)
    tail = "" if after is None else f"; retried in a fresh pane after {after.wid}" if fresh else f"; retried after {after.wid} on {after.account}"  # O(1)
    account, cdir, shared = fleet.choose_account(main_sd, model, base) if after is None or fresh else fleet._retry_account(main_sd, model, base, after.account)  # O(a * e + w)
    if fresh:  # O(1)
        print(f"{after.wid} {after.why}; retrying in a fresh pane", file=sys.stderr)  # O(1)
    elif after is not None:  # O(1)
        print(f"{after.wid} account {after.account} {after.why}; retrying on account {account}", file=sys.stderr)  # O(1)
    wid = fs.next_id(main_sd)  # O(w)
    name = fs.agent_name(main_sd, wid, root=worktree, ident="lead", taken=fleet._live_names())  # O(a)
    worktree.mkdir(parents=True, exist_ok=True)  # O(1)
    lsd = worktree / ".superlite"  # O(1)
    lsd.mkdir(parents=True, exist_ok=True)  # O(1)
    wt, lsd_s = str(worktree.resolve()), str(lsd.resolve())  # O(1)
    wenv = lead_env(main_sd, lsd, wid, cdir, base, fs.load(main_sd).get("accounts") or [])  # O(w)
    record = {"name": name, "account": account, "agent": "lead", "tier": model, "state": "starting", "task": None, "role": "lead",  # O(1)
              "one_turn": False, "lead_sd": lsd_s, "worktree": wt}
    try:  # O(1)
        pane = fleet.open_pane(main_sd, wid, wt, wenv, record)  # O(w + p)
        try:  # O(1)
            fs.register_agent(name, shared)  # O(1)
        except OSError:  # O(1)
            pass  # O(1)
    except hc.HerdrError as e:  # O(1)
        fleet._blocked(main_sd, wid, account, f"startup: {e.message or e.code}{tail}")  # O(1)
    sl = str(Path(__file__).resolve().parent / "sl")  # O(1)

    def fail(why, screen=None, slow=False, shell=False):  # O(s + w)
        fs.set_state(main_sd, wid, "blocked")  # O(w)
        try:  # O(1)
            hc.close_pane(pane)  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        if slow and after is None:  # the caller starts it once more on another account | O(1)
            fleet._keep(main_sd, wid, why, screen, "fleet spawn retry")  # O(s)
            raise fleet._Slow(wid, account, why)  # O(1)
        if shell and after is None:  # the caller starts it once more in a fresh pane | O(1)
            fleet._keep(main_sd, wid, why, screen, "fleet spawn retry")  # O(s)
            raise NoShell(wid, account, why)  # O(1)
        fleet._blocked(main_sd, wid, account, why + tail, screen)  # O(s)

    try:  # O(1)
        try:  # O(1)
            retried = fleet.start_on_shell(name, pane, lead_argv(sl, model, main_window(base, model)))  # O(1)
        except hc.HerdrError as e:  # O(1)
            screen = ""  # O(1)
            try:  # O(1)
                screen = hc.read_screen(name, fleet.SCREEN_ROWS)  # O(s)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
            if e.code != "agent_not_ready" or fleet.TRUST not in screen:  # O(s)
                shell = fleet.SHELL_MSG in (getattr(e, "message", "") or "")  # O(len)
                first = next((x.strip() for x in screen.splitlines() if x.strip()), e.message or e.code)  # O(s)
                fail(f"startup: {e.message + getattr(e, 'retried', '') if shell else first}", screen, slow=fleet._slow(e), shell=shell)  # O(s)
            hc.send_keys(name, ["Down", "Enter"])  # O(1)
            hc.wait_state(name, ["idle"], 60000)  # O(1)
        else:  # O(1)
            try:  # O(1)
                screen = hc.read_screen(name, fleet.SCREEN_ROWS)  # O(s)
            except hc.HerdrError:  # O(1)
                screen = ""  # O(1)
            if fleet.TRUST in screen and not fleet._is_ready(screen):  # O(s)
                hc.send_keys(name, ["Down", "Enter"])  # O(1)
                hc.wait_state(name, ["idle"], 60000)  # O(1)
    except hc.HerdrError as e:  # O(1)
        fail(f"startup: {e}", slow=fleet._slow(e))  # O(1)
    fs.set_state(main_sd, wid, "ready")  # O(w)
    fleet._launch_line(main_sd, wid, "lead", model, account, pane)  # O(1)
    print(f"{wid} account={account} pane={pane} agent=lead role=lead")  # O(1)
    return {"id": wid, "name": name, "account": account, "pane_id": pane, "agent": "lead", "model": model, "role": "lead", "lead_sd": lsd_s}  # O(1)


def backlog_hint(sd, cwd):  # O(b)
    """One `backlog:` line naming the leads a backlog in the main checkout runs, or None."""
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # O(1)
        return None  # O(1)
    import backlog_state as bs  # O(1)
    try:  # O(1)
        root = bs.main_root(Path(cwd))  # O(1)
    except RuntimeError:  # O(1)
        return None  # O(1)
    if Path(sd).resolve() == (root / ".superlite").resolve():  # O(1)
        return None  # O(1)
    rows = [f"{b['id']} {b['lead']}" for b in bs.load(bs.path(root)).get("batches", []) if b.get("state") in ("running", "needs_decision") and b.get("lead")]  # O(b)
    if not rows:  # O(1)
        return None  # O(1)
    one = len(rows) == 1  # O(1)
    return f"backlog: {len(rows)} lead{'' if one else 's'} run{'s' if one else ''} in {root}/.superlite ({', '.join(rows)}); sl backlog status lists {'it' if one else 'them'}, sl backlog tell B --text T messages {'it' if one else 'one'}"  # O(b)
