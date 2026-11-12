#!/usr/bin/env python3
"""The machine's admission for full test runs (#655, per toolchain #659).

`<home>/machine.json` `{"admission": ["<gate>", "run", "--"]}` names an argv prefix that decides when a full run
starts. `admission_command` reads it; `run_admitted` runs a command through it and tells, with a start marker the
command touches as its first act, when the gate admitted the run. Stdlib only.
"""
# Complexity notation:
# o = output bytes of the command, w = seconds waited (polled every 0.5 s)
import json  # O(1)
import os  # O(1)
import shlex  # O(1)
import shutil  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)
from typing import NamedTuple  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

POLL = 0.5  # seconds between checks | O(1)
SHOW_AFTER = 1.0  # seconds before the wait line and note | O(1)


class NotAdmitted(Exception):  # the gate exited or could not start before the marker showed
    def __init__(self, returncode, reason: str, text: str = ""):  # O(1)
        super().__init__(reason)  # O(1)
        self.returncode, self.reason, self.text = returncode, reason, text  # O(1)


class AdmissionBusy(Exception):  # wait_limit passed before the marker showed; the gate was killed
    def __init__(self, seconds, name: str):  # O(1)
        super().__init__(f"{name} did not start the full run after {seconds} s")  # O(1)
        self.seconds, self.name = seconds, name  # O(1)


class Admission(NamedTuple):  # how one toolchain's full run is admitted
    mode: str | None  # "command", "self", "lock"; None: no key | O(1)
    argv: list | None  # O(1)
    note: str | None  # O(1)
    warning: str | None  # O(1)


NONE = Admission(None, None, None, None)  # O(1)
LOCK_TAIL = "; running under the full-suite lock"  # O(1)


def _usable(entry, where: str):  # (argv, None) or (None, warning) for a list entry | O(len entry)
    if not isinstance(entry, list) or not entry or not all(isinstance(x, str) and x for x in entry):  # O(len entry)
        return None, f'{where} must be a non-empty list of strings, "self" or "lock"{LOCK_TAIL}'  # O(1)
    if not shutil.which(entry[0]):  # O(PATH)
        return None, f'admission command {entry[0]} not found ({where}){LOCK_TAIL}'  # O(1)
    return entry, None  # O(1)


def admission_for(toolchain: str, home: Path | None = None) -> Admission:  # O(file)
    """How a full run of one toolchain is admitted, from `<home>/machine.json` "admission" (#655, #659).
    A list is the admission command for every toolchain. An object is keyed by toolchain with an optional
    "default" key; each value is a list (admission command), "self" (the machine admits the run itself) or
    "lock" (superlite's full-suite lock). Unset: Admission(None, None, None, None)."""
    import history  # O(1)
    f = Path(home or history.home()) / "machine.json"  # O(1)
    try:  # O(1)
        data = json.loads(f.read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return NONE  # O(1)
    if not isinstance(data, dict) or "admission" not in data:  # O(1)
        return NONE  # O(1)
    adm = data["admission"]  # O(1)
    if isinstance(adm, list):  # O(1)
        argv, warn = _usable(adm, 'machine.json "admission"')  # O(len adm)
        if warn:  # O(1)
            warn = warn.replace(', "self" or "lock"', "")  # the list form has no other values | O(len warn)
            return Admission("lock", None, None, warn)  # O(1)
        return Admission("command", argv, f'full run through the admission command {os.path.basename(argv[0])} (machine.json "admission"); no full-suite lock', None)  # O(1)
    if not isinstance(adm, dict):  # O(1)
        return Admission("lock", None, None, 'machine.json "admission" must be a non-empty list of strings or an object keyed by toolchain' + LOCK_TAIL)  # O(1)
    if toolchain and toolchain in adm:  # O(1)
        key, where = toolchain, f'machine.json "admission" for {toolchain}'  # O(1)
    elif "default" in adm:  # O(1)
        key, where = "default", f'machine.json "admission" "default" for {toolchain}'  # O(1)
    else:  # O(1)
        return Admission("lock", None, f'full run under the {toolchain} full-suite lock (machine.json "admission" has no "{toolchain}" or "default" entry)', None)  # O(1)
    entry = adm[key]  # O(1)
    if entry == "self":  # O(1)
        return Admission("self", None, f'full run admitted by the machine itself ({where}: "self"); no full-suite lock, no admission command', None)  # O(1)
    if entry == "lock":  # O(1)
        return Admission("lock", None, f'full run under the {toolchain} full-suite lock ({where}: "lock")', None)  # O(1)
    argv, warn = _usable(entry, where)  # O(len entry)
    if warn:  # O(1)
        return Admission("lock", None, None, warn)  # O(1)
    return Admission("command", argv, f'full run through the admission command {os.path.basename(argv[0])} ({where}); no full-suite lock', None)  # O(1)


def admission_command(home: Path | None = None, toolchain: str = "python") -> tuple:  # O(file)
    """The command view of admission_for: (argv, None) for mode command, (None, warning) when the key is set
    but unusable, (None, None) otherwise."""
    a = admission_for(toolchain, home)  # O(file)
    if a.mode == "command":  # O(1)
        return a.argv, None  # O(1)
    return None, a.warning  # O(1)


def _text(f) -> str:  # O(o)
    try:  # O(1)
        return Path(f).read_text(encoding="utf-8", errors="replace")  # O(o)
    except OSError:  # O(1)
        return ""  # O(1)


def _last_line(text: str) -> str:  # O(o)
    lines = [ln for ln in text.splitlines() if ln.strip()]  # O(o)
    return lines[-1].strip() if lines else ""  # O(1)


def run_admitted(prefix: list, cmd: str | list, limit: float | None = None, wait_limit: float | None = None,
                 env: dict | None = None, cwd: str | None = None, note: Path | None = None) -> subprocess.CompletedProcess:  # O(w + o)
    """Run cmd (shell string or argv) behind the prefix. Raises NotAdmitted when the gate exits or cannot start
    before the start marker shows, AdmissionBusy after wait_limit seconds without it (the gate is killed),
    subprocess.TimeoutExpired when limit seconds pass after the marker. `waited` on the result = seconds
    before the marker."""
    import _pyrun  # O(1)
    name = os.path.basename(prefix[0])  # O(1)
    tmp = tempfile.mkdtemp(prefix="sl-gate-")  # O(1)
    marker = os.path.join(tmp, "started")  # O(1)
    out_f, err_f = os.path.join(tmp, "out"), os.path.join(tmp, "err")  # O(1)
    body = cmd if isinstance(cmd, str) else shlex.join(cmd)  # O(len cmd)
    argv = [*prefix, "/bin/sh", "-c", ": > " + shlex.quote(marker) + "\n" + body]  # O(len prefix)
    t0 = time.time()  # O(1)
    shown = False  # O(1)
    admitted = None  # O(1)
    proc = None  # O(1)
    try:  # O(1)
        try:  # O(1)
            with open(out_f, "wb") as fo, open(err_f, "wb") as fe:  # O(1)
                proc = subprocess.Popen(argv, stdout=fo, stderr=fe, env=env, cwd=cwd, start_new_session=True)  # O(1) process spawn
        except OSError as e:  # O(1)
            raise NotAdmitted(None, f"could not start: {e}") from e  # O(1)
        while True:  # O(w / POLL)
            rc = proc.poll()  # O(1)
            now = time.time()  # O(1)
            if admitted is None and os.path.exists(marker):  # O(1)
                admitted = now  # O(1)
                if shown:  # O(1)
                    print(f"run_tests: admission command {name} started the full run after {admitted - t0:.0f} s", file=sys.stderr)  # O(1)
                    if note:  # O(1)
                        Path(note).unlink(missing_ok=True)  # O(1)
                    shown = False  # O(1)
            if rc is not None:  # O(1)
                if admitted is None:  # O(1)
                    text = _text(err_f) or _text(out_f)  # O(o)
                    last = _last_line(text)  # O(o)
                    raise NotAdmitted(rc, f"exited {rc} before the tests started" + (f": {last}" if last else ""), text)  # O(1)
                return _done(proc, argv, rc, out_f, err_f, admitted - t0)  # O(o)
            if admitted is None:  # O(1)
                if wait_limit and now - t0 >= wait_limit:  # O(1)
                    raise AdmissionBusy(wait_limit, name)  # O(1)
                if not shown and now - t0 >= SHOW_AFTER:  # O(1)
                    shown = True  # O(1)
                    print(f"run_tests: waiting for the admission command {name} to start the full run "
                          "(machine.json \"admission\"); the machine's gate decides when it runs", file=sys.stderr)  # O(1)
                    if note:  # O(1)
                        Path(note).write_text(json.dumps({"admission": name, "pid": os.getpid(), "since": t0}), encoding="utf-8")  # O(1)
            elif limit and now - admitted >= limit:  # O(1)
                raise subprocess.TimeoutExpired(argv, limit, output=(_text(out_f) + _text(err_f)).encode())  # the output so far stays in the log | O(o)
            time.sleep(POLL)  # O(1)
    finally:  # O(D) kill
        if proc is not None and proc.poll() is None:  # O(1)
            _pyrun.kill_tree(proc)  # O(D)
        if proc is not None:  # O(1)
            try:  # O(1)
                proc.wait(timeout=5)  # O(1)
            except subprocess.TimeoutExpired:  # O(1)
                pass  # O(1)
        if note:  # O(1)
            Path(note).unlink(missing_ok=True)  # O(1)
        shutil.rmtree(tmp, ignore_errors=True)  # O(files)


def _done(proc, argv, rc, out_f, err_f, waited) -> subprocess.CompletedProcess:  # O(o)
    r = subprocess.CompletedProcess(argv, rc, _text(out_f), _text(err_f))  # O(o)
    r.waited = waited  # O(1)
    return r  # O(1)
