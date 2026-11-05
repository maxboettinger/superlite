"""Spawn a batch lead: a fleet worker of main's run, role `lead`, in its own worktree with its own run state.

Not a CLI. `backlog_run` calls `spawn_lead`. A lead gets no prime and no pool entry; its brief arrives as the first message.
"""
import os  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet  # noqa: E402 | O(1)


def lead_argv(sl_path, model):  # O(1)
    return ["--model", model, "--permission-mode", "auto", "--allowedTools", "Bash(maxapp ship *)",  # O(1)
            f"Bash({sl_path} backlog ship *)", "--disallowedTools", "AskUserQuestion"]


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
    fs, hc = fleet.fs, fleet.hc  # O(1)
    main_sd, worktree = Path(main_sd), Path(worktree)  # O(1)
    base = dict(os.environ) if env is None else env  # O(env)
    account, cdir, shared = fleet.choose_account(main_sd, model, base)  # O(a * e + w)
    wid = fs.next_id(main_sd)  # O(w)
    name = fs.agent_name(main_sd, wid)  # O(1)
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
        fleet._blocked(main_sd, wid, account, f"startup: {e.message or e.code}")  # O(1)
    sl = str(Path(__file__).resolve().parent / "sl")  # O(1)

    def fail(why, screen=None):  # O(s + w)
        fs.set_state(main_sd, wid, "blocked")  # O(w)
        try:  # O(1)
            hc.close_pane(pane)  # O(1)
        except hc.HerdrError:  # O(1)
            pass  # O(1)
        fleet._blocked(main_sd, wid, account, why, screen)  # O(s)

    try:  # O(1)
        try:  # O(1)
            hc.start_agent(name, pane, lead_argv(sl, model))  # O(1)
        except hc.HerdrError as e:  # O(1)
            screen = ""  # O(1)
            try:  # O(1)
                screen = hc.read_screen(name, fleet.SCREEN_ROWS)  # O(s)
            except hc.HerdrError:  # O(1)
                pass  # O(1)
            if e.code != "agent_not_ready" or fleet.TRUST not in screen:  # O(s)
                first = next((x.strip() for x in screen.splitlines() if x.strip()), e.message or e.code)  # O(s)
                fail(f"startup: {first}", screen)  # O(s)
            hc.send_keys(name, ["Down", "Enter"])  # O(1)
            hc.wait_state(name, ["idle"], 60000)  # O(1)
    except hc.HerdrError as e:  # O(1)
        fail(f"startup: {e}")  # O(1)
    fs.set_state(main_sd, wid, "ready")  # O(w)
    fleet._launch_line(main_sd, wid, "lead", model, account, pane)  # O(1)
    print(f"{wid} account={account} pane={pane} agent=lead role=lead")  # O(1)
    return {"id": wid, "name": name, "account": account, "pane_id": pane, "agent": "lead", "model": model, "role": "lead", "lead_sd": lsd_s}  # O(1)
