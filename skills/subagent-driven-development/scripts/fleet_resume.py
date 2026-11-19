#!/usr/bin/env python3
"""Continue a stopped one-turn worker in its own session with a follow-up text (#808).

    sl fleet resume WID --text TEXT [--plan P]    (sl fleet_resume runs the same tool)

`fleet wait` stops a one-turn worker (fixer, reviewer, research) once its status is final. This relaunches its agent with
`--resume <session>` in a fresh pane (the helpers of `fleet_restore`), then sends TEXT as `fleet send --text` does (the report
contract appended). The worker stays one-turn, so the next `fleet wait` report stops it again. Local one-turn workers only:
a pool implementer, a lead, a layer and a remote worker start fresh. Refusals print one `error:` line on stderr, exit 2, and
touch nothing; a relaunch that fails prints `BLOCKED: ...`, exit 3, and leaves the record stopped.
"""

# Complexity notation:
# w = workers in the fleet, m = metrics lines, len = text length
import argparse  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import fleet_io  # noqa: E402 | O(1)
import fleet_state as fs  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

CMD = "sl fleet resume"  # the spelling every hint prints | O(1)


def _refuse(msg):  # O(1)
    print(f"error: {msg}", file=sys.stderr)  # O(1)
    return 2  # O(1)


def _blocked(msg):  # O(1)
    print(f"BLOCKED: {msg}")  # O(1)
    return 3  # O(1)


def _msg(e):  # O(1)
    return getattr(e, "message", "") or getattr(e, "code", "") or str(e)  # O(1)


def resume(sd, wid, text):  # 0 resumed, 2 refused (nothing touched), 3 blocked (record stays stopped) | O(w + m) plus herdr calls
    import accounts  # noqa: E402 | O(1) lazy
    import fleet  # noqa: E402 | O(1) lazy
    import fleet_restore  # noqa: E402 | O(1) lazy
    sd = Path(sd)  # O(1)
    if not (text or "").strip():  # O(1)
        return _refuse("resume needs a non-empty --text")  # O(1)
    w = fs.load(sd)["workers"].get(wid)  # O(w)
    if w is None:  # O(1)
        return _refuse(f"unknown worker {wid}")  # O(1)
    hint = fleet.respawn_hint(sd, wid)  # O(w)
    role = w.get("role") or "implementer"  # O(1)
    if w.get("state") != "stopped":  # O(1)
        return _refuse(f'{wid} is {w.get("state")}, not stopped; answer it with: sl fleet send {wid} --text "..." --plan {sd}')  # O(1)
    if not w.get("one_turn") or role in ("lead", "layer"):  # O(1)
        return _refuse(f"{wid} ({role}) is no one-turn worker; start a fresh one: {hint}")  # O(1)
    if w.get("machine"):  # O(1)
        return _refuse(f"{wid} ran on {w['machine']}; resume continues local workers only; start a fresh one: {hint}")  # O(1)
    launch = w.get("launch")  # O(1)
    if not launch:  # O(1)
        return _refuse(f"{wid} has no launch record; start a fresh one: {hint}")  # O(1)
    sid = w.get("session") or fleet_restore._stem(sd, wid)  # O(m + w)
    if not sid:  # O(1)
        return _blocked(f"{wid} not resumed (no session id); start a fresh one: {hint}")  # O(1)
    c, name = fleet_io.hc, fs.name_of(sd, wid, w)  # looked up at call time: tests swap it | O(1)
    try:  # O(1)
        pane = fleet_restore._new_pane(c, sd, None, launch)  # O(1) plus herdr calls
    except Exception as e:  # noqa: BLE001 | O(1)
        return _blocked(f"{wid} not resumed (no pane: {_msg(e)})")  # O(1)
    err = None  # O(1)
    try:  # O(1)
        screen = fleet_restore._start(c, name, pane, fleet_restore._argv(launch, sid))  # O(n)
    except Exception as e:  # noqa: BLE001 | O(1)
        err, screen = e, fleet_restore._try(c.read_screen, name, fleet.SCREEN_ROWS) or ""  # O(s)
    if accounts.sign_in_screen(screen):  # O(s)
        fleet.mark_signed_out(sd, w.get("account") or "")  # O(w)
        fleet_restore._try(c.close_pane, pane)  # O(1)
        return _blocked(f"{wid} not resumed (account {w.get('account')} signed out: Claude Code sign-in screen); start a fresh one: {hint}")  # O(1)
    if err is not None:  # O(1)
        fleet_restore._try(c.close_pane, pane)  # O(1)
        return _blocked(f"{wid} not resumed (startup: {_msg(err)})")  # O(1)
    with fs.locked(sd):  # O(1) plus wait
        data = fs.load(sd)  # O(w)
        rec = data["workers"].get(wid)  # O(1)
        if rec is not None:  # O(1)
            rec.update({"state": "ready", "pane_id": pane, "session": sid})  # O(1)
            rec.pop("dead", None)  # O(1)
            rec.pop("was", None)  # O(1)
            fs.save(sd, data)  # O(w)
    print(f"{wid} resumed pane={pane} session={sid[:8]} ({role}, last task {w.get('last_task') or w.get('task') or 'none'})")  # O(1)
    try:  # O(1)
        fleet_io.send_text(sd, wid, text)  # O(w + len)
    except c.HerdrError as e:  # O(1)
        return _blocked(f'{wid} resumed, text not sent ({_msg(e)}); send it: sl fleet send {wid} --text "..." --plan {sd}')  # O(1)
    return 0  # O(1)


def main(argv=None):  # O(w + m) plus herdr calls
    p = argparse.ArgumentParser(prog="sl fleet resume")  # O(1)
    p.add_argument("wid")  # O(1)
    p.add_argument("--text", default="")  # O(1)
    p.add_argument("--plan")  # O(1)
    a = p.parse_args(sys.argv[1:] if argv is None else list(argv))  # O(n)
    return resume(Path(state.resolve(a.plan)).resolve(), a.wid, a.text)  # O(w + m)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
