#!/usr/bin/env python3
"""Account mirroring for remote fleet workers: the account a local spawn would pick, mapped to the host.

`pick(sd, label, model, env, remote_home, local_home)` runs `fleet.choose_account` with the pair's signed-out accounts as `avoid` (a ready remote worker counts like a local one) and returns
`("<account>@<label>", <config dir on the host or None for the default dir>)`; `login_screen(text)` is true for Claude Code's sign-in screen.
"""
# Complexity notation:
# l = length of a text, a = accounts, w = workers
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import accounts as ac  # noqa: E402 | O(1)

LOGIN_MARKS = ("Select login method:", "Please run /login", "Invalid API key")  # O(1) screens that mean the account is signed out on the host
SIGNED_OUT = re.compile(r"account (\S+) is not signed in on ")  # O(1) the one reason phrase of a remote sign-in failure


def signed_out_account(why):  # O(l): the account name a sign-in failure reason names, else None
    m = SIGNED_OUT.search(why or "")  # O(l)
    return m.group(1) if m else None  # O(1)


def pick(sd, label, model, env, remote_home, local_home=None):  # O(a * e + w) plus herdr and usage calls
    import fleet  # noqa: PLC0415 | O(1) fleet imports this module's callers
    import fleet_placement  # noqa: PLC0415 | O(1)
    account, cdir, _ = fleet.choose_account(sd, model, env, avoid=fleet_placement.signed_out_pairs(sd, label))  # O(a * e + w)
    name = f"{account}@{label}"  # O(1)
    if ac.is_default_dir(cdir, env):  # the host's own default dir: leave CLAUDE_CONFIG_DIR unset | O(1)
        return name, None  # O(1)
    local = str(local_home if local_home is not None else Path.home()).rstrip("/")  # O(1)
    if not cdir.startswith(local + "/"):  # O(l)
        print(f"BLOCKED: fleet spawn: machine {label}: account {account} folder {cdir} is outside {local}")  # O(1)
        raise SystemExit(3)  # O(1)
    return name, remote_home.rstrip("/") + cdir[len(local):]  # O(l)


def login_screen(text):  # O(l)
    return ac.sign_in_screen(text) or any(m in (text or "") for m in LOGIN_MARKS)  # O(l)
