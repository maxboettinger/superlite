#!/usr/bin/env python3
"""Re-launch every worker and lead of a run after a Herdr server restart (#577).

    fleet_restore.py [--plan P]

Per worker: the pane that holds its session (Herdr agent list) or its recorded pane gives the place; a fresh pane is split
off it with the recorded env, the old pane is closed, the recorded agent starts with `--resume <session>`. A busy worker
whose turn the restart cut gets a continue prompt (a lead's ends with its phase's report contract, fleet_io.report_contract). Leads' own fleets come first. Prints one line per worker, then the waits
to re-arm and the test runs that ended meanwhile. Exit 3 when a line says BLOCKED, else 0.
"""

# Complexity notation:
# w = workers in the fleet, a = agents herdr lists, n = argv length
import argparse  # O(1)
import os  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet  # noqa: E402 | O(1)
import fleet_io as fio  # noqa: E402 | O(1)
import fleet_report  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import herdr_client  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

SL = str(Path(__file__).resolve().parent / "sl")  # O(1)
CONTINUE = ("Herdr restarted and ended your last turn; sl fleet restore resumed this session with its fleet env. Continue the work of your last message "
            "where it stopped (check what is already done first; a wait or test run you started died with the restart: run it again in the foreground), "
            "then end with the report it asks for.")  # O(1)
LEAD_CONTINUE = ("Herdr restarted and ended your last turn; sl fleet restore resumed this session and your fleet with their fleet env. "
                 "Your waits died with the restart: re-arm them in the foreground first:")  # O(1)
LEAD_TAIL = "Then continue your brief where you stopped."  # O(1)
REVIEW_ROLES = ("final-reviewer",)  # O(1)
WAIT_MS = 540000  # O(1)


def _pause(s):  # tests swap it | O(s)
    fleet._pause(s)  # O(s)


def _client():  # O(1)
    return herdr_client  # O(1)


def _test_lines(sd):  # the test run lines of SD; none when they cannot be read | O(runs)
    try:  # O(1)
        import fleet_rearm  # noqa: E402 | O(1) lazy
        return list(fleet_rearm.test_run_lines(Path(sd)))  # O(runs)
    except Exception:  # noqa: BLE001 | O(1)
        return []  # O(1)


def _layer_alive(sd, wid, w):  # True live shell, False gone, None unknown | O(1)
    try:  # O(1)
        import fleet_layer  # noqa: E402 | O(1) lazy
        return fleet_layer.alive(Path(sd), wid, w)  # O(1)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def _layer_done(sd, wid, w):  # True when the layer wrote its exit file | O(l)
    try:  # O(1)
        import fleet_layer  # noqa: E402 | O(1) lazy
        return fleet_layer.result(Path(sd), wid, w) is not None  # O(l)
    except Exception:  # noqa: BLE001 | O(1)
        return False  # O(1)


def _try(fn, *args):  # fn(*args), or None when it is missing or raises | O(fn)
    if fn is None:  # O(1)
        return None  # O(1)
    try:  # O(1)
        return fn(*args)  # O(fn)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def _msg(e):  # O(1)
    return getattr(e, "message", "") or getattr(e, "code", "") or str(e)  # O(1)


def _session_of(agent):  # the session id of a herdr agent dict, else None | O(1)
    fn = getattr(herdr_client, "session_of", None)  # O(1)
    if fn is not None:  # O(1)
        return _try(fn, agent)  # O(1)
    s = agent.get("agent_session") if isinstance(agent, dict) else None  # O(1)
    v = s.get("value") if isinstance(s, dict) else None  # O(1)
    return v if isinstance(v, str) and v else None  # O(1)


def _update(sd, wid, **kw):  # one lock-held record change; a None value removes the key | O(w)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        rec = data["workers"].get(wid)  # O(1)
        if rec is None:  # O(1)
            return  # O(1)
        for k, v in kw.items():  # O(k)
            if v is None and k in ("dead", "was"):  # O(1)
                rec.pop(k, None)  # O(1)
            else:  # O(1)
                rec[k] = v  # O(1)
        fs.save(sd, data)  # O(w)


def _argv(launch, sid):  # the recorded argv without an earlier --resume pair, plus --resume SID | O(n)
    argv, out, i = list(launch.get("argv") or []), [], 0  # O(1)
    while i < len(argv):  # O(n)
        if argv[i] == "--resume":  # O(1)
            i += 2  # O(1)
            continue  # O(1)
        out.append(argv[i])  # O(1)
        i += 1  # O(1)
    return out + ["--resume", sid]  # O(n)


def _new_pane(c, sd, old, launch):  # a fresh pane: split off OLD, else a tab of the workspace, else a new workspace | O(1) plus herdr calls
    cwd, env = launch.get("cwd") or str(sd.parent), launch.get("env") or {}  # O(1)
    if old:  # O(1)
        try:  # O(1)
            return c.split_pane(old, "down", cwd, env)  # O(e)
        except Exception:  # noqa: BLE001 | O(1)
            pass  # O(1)
    data = fs.load(sd)  # O(w)
    ws = data.get("workspace_id")  # O(1)
    if ws:  # O(1)
        try:  # O(1)
            return c.create_tab(ws, cwd, env)[1]  # O(e)
        except Exception:  # noqa: BLE001 | O(1)
            pass  # O(1)
    new_ws, pane = c.create_workspace(data.get("label") or "sl:fleet", cwd, env)  # O(e)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        data.update({"workspace_id": new_ws, "root_pane": pane})  # O(1)
        fs.save(sd, data)  # O(w)
    return pane  # O(1)


def _start(c, name, pane, argv):  # start the agent, one retry after a pause on a pane that is no shell yet; a trust dialog is accepted | O(1)
    for attempt in (0, 1):  # O(1)
        try:  # O(1)
            c.start_agent(name, pane, argv)  # O(n)
            break  # O(1)
        except Exception as e:  # noqa: BLE001 | O(1)
            if fleet.SHELL_MSG in _msg(e) and attempt == 0:  # O(len)
                _pause(fleet.SHELL_PAUSE_S)  # O(1)
                continue  # O(1)
            screen = _try(c.read_screen, name, fleet.SCREEN_ROWS) or ""  # O(s)
            if getattr(e, "code", "") == "agent_not_ready" and fleet.TRUST in screen:  # O(s)
                c.send_keys(name, ["Down", "Enter"])  # O(1)
                c.wait_state(name, ["idle"], 60000)  # O(1)
                break  # O(1)
            raise  # O(1)
    screen = _try(c.read_screen, name, fleet.SCREEN_ROWS) or ""  # O(s)
    if fleet._trust_open(screen):  # O(s)
        c.send_keys(name, ["Down", "Enter"])  # O(1)
        c.wait_state(name, ["idle"], 60000)  # O(1)


def _find(c, name, w):  # (the live agent dict or None, its session or None) | O(a)
    agents = [a for a in (_try(getattr(c, "all_agents", None)) or []) if isinstance(a, dict)]  # O(a)
    mine = next((a for a in agents if a.get("name") == name), None)  # O(a)
    if mine is None and w.get("session"):  # O(a)
        mine = next((a for a in agents if _session_of(a) == w["session"]), None)  # O(a)
    sid = _session_of(mine) if mine else None  # O(1)
    return mine, sid or _try(getattr(c, "agent_session", None), name) or w.get("session")  # O(1)


def _stem(sd, wid):  # the transcript stem of the newest stop record of WID, else None | O(m + w)
    e = fio.latest_stop(sd, wid, 0)  # O(m + w)
    return Path(e["transcript"]).stem if e and e.get("transcript") else None  # O(1)


def _one(sd, c, wid, w, rearm_of_lead, prefix):  # (line, blocked) for one worker | O(a + w) plus herdr calls
    who, name, dead = f"{prefix}{wid}", fs.name_of(sd, wid, w), w.get("state") == "stopped"  # O(1)
    launch = w.get("launch")  # O(1)
    if not launch:  # O(1)
        return f"BLOCKED: {who} not restored (no launch record; spawned before restore existed); start a fresh one: {fleet.respawn_hint(sd, wid)}", True  # O(w)
    was = w.get("was") if dead else w.get("state")  # O(1)
    task = w.get("last_task") if dead else w.get("task")  # O(1)
    if dead and was == "busy" and task:  # another worker took a task over | O(w)
        ids = {t.strip() for t in str(task).split(",") if t.strip()}  # a joined label T3,T4 holds several ids | O(len)
        for k, v in fs.load(sd)["workers"].items():  # O(w)
            if k == wid:  # O(1)
                continue  # O(1)
            theirs = {t.strip() for t in str(v.get("task") or "").split(",")} if v.get("state") == "busy" else set()  # O(len)
            if not (v.get("state") == "stopped" and v.get("dead")) or int(v.get("sent") or 0) > int(w.get("sent") or 0):  # a dead worker's last_task counts only when it is newer | O(1)
                theirs |= {t.strip() for t in str(v.get("last_task") or "").split(",")}  # O(len)
            if ids & theirs:  # O(ids)
                return f"{who} skipped (its task {task} went to {k})", False  # O(1)
        done = fio.ledger_commits(sd / "progress.md")  # O(lines)
        if any(t in done for t in ids):  # a task is committed already | O(ids)
            return f"{who} skipped (its task {task} went to ledger)", False  # O(1)
    agent, sid = _find(c, name, w)  # O(a)
    if agent and agent.get("agent_status") == "working":  # O(1)
        return f"{who} skipped (its agent is working in pane {agent.get('pane_id')})", False  # O(1)
    if not sid:  # O(m + w)
        sid = _stem(sd, wid)  # O(m + w)
    if not sid:  # O(1)
        return f"BLOCKED: {who} not restored (no session id)", True  # O(1)
    old = agent.get("pane_id") if agent else None  # O(1)
    if not old and w.get("pane_id"):  # O(1)
        exists = getattr(c, "pane_exists", None)  # O(1)
        old = w["pane_id"] if exists is None or _try(exists, w["pane_id"]) else None  # O(1)
        if old and any(isinstance(a, dict) and a.get("pane_id") == old and _session_of(a) != sid for a in (_try(getattr(c, "all_agents", None)) or [])):  # the id now holds another session's pane | O(a)
            old = None  # O(1)
    if old and old == os.environ.get("HERDR_PANE_ID"):  # O(1)
        return f"BLOCKED: {who} not restored (its pane is this session's pane)", True  # O(1)
    try:  # O(1)
        pane = _new_pane(c, sd, old, launch)  # O(e)
    except Exception as e:  # noqa: BLE001 | O(1)
        return f"BLOCKED: {who} not restored (no pane: {_msg(e)})", True  # O(1)
    if old and old != pane:  # O(1)
        _try(c.close_pane, old)  # O(1)
    try:  # O(1)
        _start(c, name, pane, _argv(launch, sid))  # O(n)
    except Exception as e:  # noqa: BLE001 | O(1)
        _try(c.close_pane, pane)  # O(1)
        if not dead:  # a dead worker keeps its record, so a rerun tries it again | O(1)
            _update(sd, wid, state="blocked")  # O(w)
        return f"BLOCKED: {who} not restored (startup: {_msg(e)})", True  # O(1)
    role = w.get("role") or "implementer"  # O(1)
    sent = int(w.get("sent") or 0)  # O(1)
    _update(sd, wid, pane_id=pane, session=sid)  # O(w)
    if dead:  # O(1)
        _update(sd, wid, state=was, task=task if was == "busy" else None, dead=None, was=None)  # O(w)
        if role == "implementer":  # back into the pool | O(1)
            fleet._register_pool(sd, wid, w.get("tier"), w.get("account"))  # O(w)
    line = f"{who} restored pane={pane} session={sid[:8]} {was}"  # O(1)
    if was != "busy":  # O(1)
        return line, False  # O(1)
    if fio.latest_stop(sd, wid, sent):  # the turn ended with a report before the restart | O(m + w)
        return line + ", reported", False  # O(m + w)
    if role == "lead":  # O(1)
        text = "\n".join([LEAD_CONTINUE] + rearm_of_lead + [LEAD_TAIL]) + "\n\n" + fio.report_contract(w)  # O(r + size of the brief)
    else:  # O(1)
        text = CONTINUE + "\n\n" + (fleet_report.REVIEW if role in REVIEW_ROLES else fleet_report.WORK)  # O(1)
    try:  # O(1)
        c.prompt(name, text, ["working"], 15000)  # O(len)
    except Exception as e:  # noqa: BLE001 | O(1)
        return f"{line}, continue not sent ({_msg(e)}); send it: {SL} fleet send {wid} --text \"continue\" --plan {sd}", False  # O(1)
    fio._busy(sd, wid, task, fio.now_ms(), w.get("brief"))  # O(w + pool bytes)
    return line + ", continued", False  # O(w)


def _targets(w):  # whether restore handles worker record W | O(1)
    if w.get("role") == "layer":  # O(1)
        return False  # O(1)
    return w.get("state") in ("ready", "busy") or (w.get("state") == "stopped" and bool(w.get("dead")) and w.get("was") in ("ready", "busy"))  # O(1)


def _run(sd, c, prefix):  # (lines, re-arm lines, blocked) of one fleet | O(w * (a + w)) plus herdr calls
    sd, lines, blocked = Path(sd), [], False  # O(1)
    data = fs.load(sd)  # O(w)
    leads = {k: v for k, v in sorted(data["workers"].items()) if v.get("role") == "lead" and _targets(v)}  # O(w log w)
    lead_rearm = {}  # O(1)
    for wid, w in leads.items():  # each lead's own fleet first | O(leads)
        lsd = w.get("lead_sd")  # O(1)
        if lsd and fs.is_on(lsd):  # O(w)
            sub, rearm, b = _run(lsd, c, f"{prefix}{wid} ")  # O(sub)
            lines += sub  # O(l)
            blocked = blocked or b  # O(1)
            lead_rearm[wid] = rearm  # O(1)
    for wid, w in sorted(data["workers"].items()):  # O(w log w)
        if w.get("role") == "layer":  # O(1)
            if w.get("state") == "busy" and not _layer_done(sd, wid, w) and _layer_alive(sd, wid, w) is False:  # O(l)
                _update(sd, wid, state="stopped", task=None)  # O(w)
                lines.append(f"{prefix}{wid} layer-{w.get('layer')} died with the restart; rerun: {SL} fleet run --layer {w.get('layer')} --plan {sd}")  # O(1)
        elif _targets(w):  # O(1)
            line, b = _one(sd, c, wid, w, lead_rearm.get(wid, []), prefix)  # O(a + w)
            lines.append(line)  # O(1)
            blocked = blocked or b  # O(1)
    rearm = []  # O(1)
    if any(v.get("state") == "busy" for v in fs.load(sd)["workers"].values()):  # O(w)
        rearm.append(f"re-arm: {SL} fleet wait --wave --timeout {WAIT_MS} --plan {sd}")  # O(1)
    if leads:  # O(1)
        rearm.append(f"re-arm: {SL} backlog run")  # O(1)
    return lines, rearm + _test_lines(sd), blocked  # O(runs)


def restore(sd, client=None, prefix=""):  # (the lines to print, whether one says BLOCKED) | O(w * (a + w)) plus herdr calls
    sd = Path(sd)  # O(1)
    lines, rearm, blocked = _run(sd, client or _client(), prefix)  # O(w * (a + w))
    out = lines + rearm  # O(l)
    if not out and not prefix:  # O(1)
        out = [f"fleet restore: nothing to restore in {sd}"]  # O(1)
    return out, blocked  # O(1)


def main(argv):  # O(w * (a + w)) plus herdr calls
    p = argparse.ArgumentParser(prog="fleet_restore.py")  # O(1)
    p.add_argument("--plan")  # O(1)
    a = p.parse_args(list(argv))  # O(n)
    sd = Path(state.resolve(a.plan)).resolve()  # O(d)
    if not fs.is_on(sd):  # O(w)
        print(f"BLOCKED: fleet is off in {sd}; nothing to restore")  # O(1)
        return 3  # O(1)
    lines, blocked = restore(sd, _client())  # O(w * (a + w))
    for x in lines:  # O(l)
        print(x)  # O(1)
    return 3 if blocked else 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main(sys.argv[1:]))  # O(1)
