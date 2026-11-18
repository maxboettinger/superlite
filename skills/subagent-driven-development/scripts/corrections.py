#!/usr/bin/env python3
"""Project corrections: one tracked file of user corrections that every later run reads.

    corrections.py add TEXT [--root DIR]    record one line (whitespace collapsed, home paths as `~`, at most 300
                                            characters); refused (exit 2) for empty text, a secret or an e-mail address,
                                            or a file that would pass 2,048 bytes; a duplicate is a no-op
    corrections.py list [--root DIR]        the numbered lines
    corrections.py rm N [--root DIR]        drop line N

The file is `docs/superlite/corrections.md` in the project. Inside a git work tree a change is committed alone
(`git commit -- <file>`). A file over 2,048 bytes (edited by hand) is ignored by every reader. Stdlib only.

Library: `section(root) -> str | None` is the text the primes, briefs, packet and session start embed.
"""
# Complexity notation:
#   b = bytes of the corrections file (at most 2048), n = lines in it
import argparse  # O(1)
import os  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import feedback  # the secret, e-mail and home-path pattern table | O(1)

FILE = "docs/superlite/corrections.md"  # O(1)
MAX_BYTES = 2048  # O(1)
MAX_LINE = 300  # O(1)
HEADER = ("# Corrections\n\nOne line per correction from the user; superlite gives this file to every run. "
          "Managed by sl corrections.\n\n")  # O(1)


def _read(root: Path):  # O(b)
    """The file's text, or None when it is absent, unreadable or over the cap."""
    try:  # O(1)
        p = Path(root) / FILE  # O(1)
        if p.stat().st_size > MAX_BYTES:  # O(1)
            return None  # O(1)
        return p.read_bytes().decode("utf-8").replace("\r\n", "\n")  # O(b)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)


def lines(root: Path) -> list[str]:  # O(b)
    text = _read(root)  # O(b)
    if text is None:  # O(1)
        return []  # O(1)
    return [ln[2:] for ln in text.split("\n") if ln.startswith("- ")]  # O(b)


def section(root: Path):  # O(b)
    try:  # fail open | O(1)
        got = lines(root)  # O(b)
    except Exception:  # O(1)
        return None  # O(1)
    if not got:  # O(1)
        return None  # O(1)
    return "## Corrections (binding, from the user)\n\n" + "\n".join("- " + ln for ln in got)  # O(b)


def _render(items: list) -> str:  # O(b)
    return HEADER + "".join("- " + ln + "\n" for ln in items)  # O(b)


def _write(root: Path, items: list) -> None:  # O(b)
    p = Path(root) / FILE  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".corrections-")  # O(1)
    try:  # O(1)
        with os.fdopen(fd, "wb") as fh:  # O(1)
            fh.write(_render(items).encode("utf-8"))  # O(b)
        os.replace(tmp, p)  # atomic | O(1)
    except BaseException:  # O(1)
        try:  # O(1)
            os.unlink(tmp)  # O(1)
        except OSError:  # O(1)
            pass  # O(1)
        raise  # O(1)


def _git(root: Path, *args) -> subprocess.CompletedProcess:  # O(1) + one git process
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}  # O(1)
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)  # O(1)


def _commit(root: Path, label: str) -> str:  # O(1) + up to three git processes
    """"" when committed or not in a work tree; else `; not committed: <git's last line>`."""
    try:  # O(1)
        inside = _git(root, "rev-parse", "--is-inside-work-tree")  # O(1)
    except OSError:  # O(1)
        return ""  # O(1)
    if inside.returncode != 0 or inside.stdout.strip() != "true":  # O(1)
        return ""  # O(1)
    step = _git(root, "add", "--", FILE)  # O(1)
    if step.returncode == 0:  # O(1)
        step = _git(root, "commit", "-q", "-m", "corrections: " + label[:60], "--", FILE)  # O(1)
    if step.returncode == 0:  # O(1)
        return ""  # O(1)
    out = [ln for ln in (step.stderr + "\n" + step.stdout).splitlines() if ln.strip()]  # O(1)
    return "; not committed: " + (out[-1].strip() if out else "git failed")  # O(1)


def _key(text: str) -> str:  # O(w)
    return " ".join(text.split()).casefold()  # O(w)


def add(root: Path, text: str, commit: bool = True) -> tuple[int, str]:  # O(b) + git processes
    text = " ".join(str(text).split())  # O(w)
    if text.startswith("- "):  # O(1)
        text = text[2:].strip()  # O(w)
    elif text == "-":  # O(1)
        text = ""  # O(1)
    if not text:  # O(1)
        return 2, "corrections: refused: the text is empty"  # O(1)
    if len(text) > MAX_LINE:  # checked before anything truncates | O(1)
        return 2, f"corrections: refused: the text is {len(text)} characters; the limit is {MAX_LINE} characters"  # O(1)
    scrubbed = feedback.scrub(text)  # O(w)
    if "<secret>" in scrubbed or "<email>" in scrubbed:  # O(w)
        return 2, "corrections: refused: the text holds a secret or an email address"  # O(1)
    for rx, repl in feedback.SCRUB[:2]:  # the home-path patterns | O(1)
        text = rx.sub(repl, text)  # O(w)
    p = Path(root) / FILE  # O(1)
    if p.exists() and _read(root) is None:  # a hand-edited file over the cap or unreadable | O(b)
        return 2, f"corrections: refused: {FILE} is unreadable or over the {MAX_BYTES}-byte cap; edit it by hand"  # O(1)
    items = lines(root)  # O(b)
    if _key(text) in {_key(i) for i in items}:  # O(n)
        return 0, "corrections: already recorded"  # O(1)
    items.append(text)  # O(1)
    size = len(_render(items).encode("utf-8"))  # O(b)
    if size > MAX_BYTES:  # O(1)
        return 2, (f"corrections: refused: the file would pass the {MAX_BYTES}-byte cap ({size} bytes); "
                   "drop a line with sl corrections rm N")  # O(1)
    _write(root, items)  # O(b)
    msg = f"corrections: added ({len(items)} line{'s' if len(items) != 1 else ''}, {size}/{MAX_BYTES} bytes)"  # O(1)
    return 0, msg + (_commit(root, text) if commit else "")  # O(1)


def remove(root: Path, n: int, commit: bool = True) -> tuple[int, str]:  # O(b) + git processes
    items = lines(root)  # O(b)
    if not 1 <= n <= len(items):  # O(1)
        return 2, f"corrections: refused: no line {n} (the file has {len(items)})"  # O(1)
    gone = items.pop(n - 1)  # O(n)
    _write(root, items)  # O(b)
    size = len(_render(items).encode("utf-8"))  # O(b)
    msg = f"corrections: removed line {n} ({len(items)} left, {size}/{MAX_BYTES} bytes)"  # O(1)
    return 0, msg + (_commit(root, "remove " + gone) if commit else "")  # O(1)


def _root(given) -> Path:  # O(1) + one git process
    if given:  # O(1)
        return Path(given)  # O(1)
    try:  # O(1)
        top = _git(Path.cwd(), "rev-parse", "--show-toplevel")  # O(1)
        if top.returncode == 0 and top.stdout.strip():  # O(1)
            return Path(top.stdout.strip())  # O(1)
    except OSError:  # O(1)
        pass  # O(1)
    return Path.cwd()  # O(1)


def main(argv=None) -> int:  # O(b) + git processes
    ap = argparse.ArgumentParser(prog="corrections", description="Project corrections the user gave superlite.")  # O(1)
    ap.add_argument("--root", default=None, help="project folder (default: the git top level, else here)")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    pa = sub.add_parser("add")  # O(1)
    pa.add_argument("text", nargs="+")  # O(1)
    sub.add_parser("list")  # O(1)
    pr = sub.add_parser("rm")  # O(1)
    pr.add_argument("n", type=int)  # O(1)
    for sp in (pa, pr, sub.choices["list"]):  # --root also after the verb | O(1)
        sp.add_argument("--root", dest="root_after", default=None)  # O(1)
    try:  # O(1)
        a = ap.parse_args(argv)  # O(1)
    except SystemExit as e:  # O(1)
        return 2 if e.code else 0  # O(1)
    root = _root(a.root_after or a.root)  # O(1)
    if a.cmd == "add":  # O(1)
        code, msg = add(root, " ".join(a.text))  # O(b)
    elif a.cmd == "rm":  # O(1)
        code, msg = remove(root, a.n)  # O(b)
    else:  # O(1)
        got = lines(root)  # O(b)
        code, msg = 0, "\n".join(f"{i}. {ln}" for i, ln in enumerate(got, 1)) if got else "corrections: none"  # O(b)
    print(msg, file=sys.stderr if code else sys.stdout)  # O(1)
    return code  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
