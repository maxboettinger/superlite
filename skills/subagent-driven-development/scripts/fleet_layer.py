#!/usr/bin/env python3
"""Layer runner: one test layer (headless, tui, evals) in a Herdr shell pane, on the account with the most headroom.

    fleet_layer.py --layer headless|tui|evals [--plan P]

Prints `Wn layer-<L> started account=<a> pane=<p>`. The pane's shell runs `scripts/test_layers.py run <L>`, writes
`<sd>/fleet/layers/<Wn>-<L>.log` and, when it ends, the exit code to `<Wn>-<L>.exit`; `result` reads both for `fleet wait`.
Exit 2 for a bad layer or a missing scripts/test_layers.py, 3 with a `BLOCKED: ...` line when no pane can be opened.
"""

# Complexity notation:
# w = workers in the fleet, a = accounts, l = log size
import argparse  # O(1)
import os  # O(1)
import shlex  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import accounts as ac  # noqa: E402 | O(1)
import fleet  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import herdr_client as hc  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)
from herdr_client import HerdrError  # noqa: E402 | O(1)

LAYERS = ("headless", "tui", "evals")  # O(1)
LAST_MAX = 200  # O(1) longest `last` line


def _dir(sd):  # O(1)
    return Path(sd) / "fleet" / "layers"  # O(1)


def _files(sd, wid, layer):  # O(1)
    d = _dir(sd)  # O(1)
    return d / f"{wid}-{layer}.log", d / f"{wid}-{layer}.exit"  # O(1)


def run(sd, layer, root, env=None):  # O(a + w) plus herdr calls
    sd = Path(sd)  # as given, never resolved: main passes a resolved one | O(1)
    if layer not in LAYERS:  # O(1)
        raise ValueError(f"unknown layer {layer} ({', '.join(LAYERS)})")  # O(1)
    script = Path(root) / "scripts" / "test_layers.py"  # O(1)
    if not script.is_file():  # O(1)
        raise FileNotFoundError(f"no scripts/test_layers.py in {root}")  # O(1)
    base = dict(os.environ) if env is None else env  # O(env)
    account, cdir, _ = fleet.choose_account(sd, None, base)  # its SystemExit(3) passes through | O(a)
    pane_env = {}  # a layer's own e2e Claude sessions must not look like fleet workers: only the account and pass-through | O(1)
    if not ac.is_default_dir(cdir, base):  # the default dir is chosen by leaving the variable unset | O(1)
        pane_env["CLAUDE_CONFIG_DIR"] = cdir  # O(1)
    for k in fleet.PASS_THROUGH:  # O(1)
        if base.get(k):  # O(1)
            pane_env[k] = base[k]  # O(1)
    wid = fs.next_id(sd)  # O(w)
    record = {"role": "layer", "layer": layer, "account": account, "agent": None, "tier": None, "one_turn": True,  # O(1)
              "state": "busy", "task": f"layer-{layer}", "sent": int(time.time() * 1000)}
    log, ex = _files(sd, wid, layer)  # O(1)
    log.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    ex.unlink(missing_ok=True)  # a stale exit file would read as finished | O(1)
    q = shlex.quote  # O(1)
    command = f"cd {q(str(root))} && {q(sys.executable)} -u scripts/test_layers.py run {layer} > {q(str(log))} 2>&1; echo $? > {q(str(ex))}"  # O(1)
    try:  # O(1)
        pane = fleet.open_pane(sd, wid, str(root), pane_env, record)  # O(w)
    except HerdrError as e:  # O(1)
        print(f"BLOCKED: {wid} layer {layer} {e}")  # O(1)
        raise SystemExit(3)  # O(1)
    try:  # O(1)
        hc.run_in_pane(pane, command)  # O(len command)
    except HerdrError as e:  # O(1)
        try:  # the shell pane stays open otherwise | O(1)
            hc.close_pane(pane)  # O(1)
        except HerdrError:  # O(1)
            pass  # O(1)
        try:  # the pane is open and registered: a busy record nobody finishes would hold its account for good | O(w)
            fs.set_state(sd, wid, "blocked")  # O(w)
        except KeyError:  # O(1)
            pass  # O(1)
        print(f"BLOCKED: {wid} layer {layer} {e}")  # O(1)
        raise SystemExit(3)  # O(1)
    return {"id": wid, "account": account, "pane_id": pane, "layer": layer, "log": str(log), "exit": str(ex)}  # O(1)


def result(sd, wid, w):  # O(l)
    """The finished layer of worker `wid` as {"status": GREEN|RED, "exit", "last", "log"}, or None while it still runs."""
    log, ex = _files(sd, wid, w.get("layer", ""))  # O(1)
    try:  # a missing or half-written (empty) exit file reads as still running | O(1)
        code = int(ex.read_text().strip())  # O(1)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    last = "(no log)"  # O(1)
    try:  # O(1)
        lines = [x.strip() for x in log.read_text(errors="replace").splitlines() if x.strip()]  # O(l)
        if lines:  # O(1)
            last = lines[-1][:LAST_MAX]  # O(1)
    except OSError:  # O(1)
        pass  # O(1)
    return {"status": "GREEN" if code == 0 else "RED", "exit": code, "last": last, "log": str(log)}  # O(1)


def main(argv):  # O(a + w) plus herdr calls
    p = argparse.ArgumentParser(prog="fleet_layer.py")  # O(1)
    p.add_argument("--layer", required=True)  # O(1)
    p.add_argument("--plan")  # O(1)
    a = p.parse_args(list(argv))  # O(n)
    sd = Path(state.resolve(a.plan)).resolve()  # O(d)
    root = Path(state.git_root(sd) or sd.parent)  # O(d)
    try:  # O(1)
        r = run(sd, a.layer, root)  # O(a + w)
    except (ValueError, FileNotFoundError) as e:  # O(1)
        print(f"error: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    print(f"{r['id']} layer-{r['layer']} started account={r['account']} pane={r['pane_id']}")  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main(sys.argv[1:]))  # O(1)
