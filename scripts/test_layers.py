#!/usr/bin/env python3
from __future__ import annotations  # O(1)
import argparse  # O(1)
import hashlib  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

HERE = str(Path(__file__).resolve().parent)  # O(1)
if HERE not in sys.path:  # O(1)  tests load this file by path, so the sibling script is not importable yet
    sys.path.insert(0, HERE)  # O(1)
import layer_store  # noqa: E402  # O(1)

LAYERS = ("unit", "headless", "tui", "evals")  # O(1)
KEYWORDS = ("CLAUDE_CODE_FORK_SUBAGENT", "agent_summary")  # O(1)
SKIP_SCAN = ("docs/plans/", "scripts/test_layers.py", "tests/scripts/")  # O(1)
EXCLUDED = ("evals/results/", ".superlite/")  # O(1)
MARKERS = ("stable.json", "prime.md", "pool.json")  # O(1)
MANIFESTS = (".*-plugin/*.json", "package.json", "gemini-extension.json")  # O(1)  a version bump alone must not move a layer
VERSION = re.compile(r'"version"\s*:\s*"[^"]*"')  # O(1)
SL = "bash skills/subagent-driven-development/scripts/sl"  # O(1)
MATRIX = {  # O(1)
    "unit": (["skills/**/scripts/**", "hooks/**", "tests/scripts/**", "tests/bench/**", "bench/*.py", "scripts/*.py"], []),  # O(1)
    "headless": (["hooks/**", "skills/**", "agents/**", "commands/**", ".claude-plugin/**", "tests/e2e/harness.py", "tests/e2e/test_headless.py"], ["skills/**/scripts/**"]),  # O(1)
    "tui": (["hooks/session-start", "hooks/hooks.json", "tests/e2e/tui_driver.py", "tests/e2e/test_tui.py"], []),  # O(1)
    "evals": (["skills/*/SKILL.md", "commands/**", "agents/**", "evals/**"], []),  # O(1)
}  # O(1)
DEFAULT_UNIT_WAIT = 540.0  # O(1)
NO_RESULT = re.compile(r"^tests: no result yet after (\S+) s(?: \(pid (\d+) still running\))?; run again: (.+)$", re.M)  # O(1)


def unit_command(wait: float) -> str:  # O(1)
    return f"{SL} run_tests --full --background && {SL} run_tests --wait --timeout {wait:g}"  # O(1)


COMMANDS = {  # O(1)
    "unit": unit_command(DEFAULT_UNIT_WAIT),  # O(1)
    "headless": f"{SL} run_tests --fast tests/e2e/test_headless.py",  # O(1)
    "tui": f"{SL} run_tests --fast tests/e2e/test_tui.py",  # O(1)
    "evals": "bash scripts/evals.sh",  # O(1)
}  # O(1)


def to_regex(pattern: str) -> re.Pattern:  # O(1)
    parts = re.split(r"(\*\*|\*)", pattern)  # O(p)
    body = "".join(".*" if p == "**" else "[^/]*" if p == "*" else re.escape(p) for p in parts)  # O(p)
    return re.compile(body + r"\Z")  # O(p)


def matches(layer: str, path: str) -> bool:  # O(1)
    if path.startswith(EXCLUDED):  # O(1)
        return False  # O(1)
    include, exclude = MATRIX[layer]  # O(1)
    return any(to_regex(g).match(path) for g in include) and not any(to_regex(g).match(path) for g in exclude)  # O(g)


def layers_for(paths: list[str], diffs: dict[str, str] | None = None) -> list[str]:  # O(1)
    hit = set()  # O(1)
    for path in paths:  # O(n)
        path = path.replace("\\", "/")  # O(1)
        hit.update(layer for layer in LAYERS if matches(layer, path))  # O(1)
        if diffs and any(k in diffs.get(path, "") for k in KEYWORDS):  # O(1)
            hit.add("tui")  # O(1)
    return [layer for layer in LAYERS if layer in hit]  # O(1)


def repo_files(root: Path) -> list[str]:  # O(1)
    out = []  # O(1)
    for args in (["ls-files", "-z"], ["ls-files", "-z", "--others", "--exclude-standard"]):  # O(1)
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)  # O(n)
        out += [p for p in r.stdout.split("\0") if p]  # O(n)
    return sorted({p.replace("\\", "/") for p in out if not p.startswith(EXCLUDED)})  # O(n log n)


def read_text(path: Path) -> str:  # O(1)
    try:  # O(1)
        return path.read_bytes()[:1_000_000].decode("utf-8", "ignore")  # O(size)
    except OSError:  # O(1)
        return ""  # O(1)


def layer_files(layer: str, root: Path) -> list[str]:  # O(1)
    files = [p for p in repo_files(root) if (root / p).is_file()]  # O(n)
    chosen = [p for p in files if matches(layer, p)]  # O(n)
    if layer == "tui":  # O(1)
        extra = [p for p in files if p not in chosen and not p.startswith(SKIP_SCAN) and any(k in read_text(root / p) for k in KEYWORDS)]  # O(n * size)
        chosen = sorted(chosen + extra)  # O(n log n)
    return chosen  # O(1)


def is_manifest(path: str) -> bool:  # O(1)
    return any(to_regex(g).match(path) for g in MANIFESTS)  # O(g)


def file_digest(path: str, root: Path, keyword_lines: bool = False) -> str:  # O(1)
    if keyword_lines:  # O(1)
        lines = [line for line in read_text(root / path).splitlines() if any(k in line for k in KEYWORDS)]  # O(size)
        return hashlib.sha256("\n".join(lines).encode("utf-8", "surrogateescape")).hexdigest()  # O(size)
    data = (root / path).read_bytes()  # O(size)
    if is_manifest(path):  # O(1)
        data = VERSION.sub('"version": ""', data.decode("utf-8", "surrogateescape")).encode("utf-8", "surrogateescape")  # O(size)
    return hashlib.sha256(data).hexdigest()  # O(size)


def layer_digests(layer: str, root: Path) -> dict[str, str]:  # O(1)
    root = Path(root)  # O(1)
    return {p: file_digest(p, root, layer == "tui" and not matches(layer, p)) for p in layer_files(layer, root)}  # O(n * size)


def hash_digests(digests: dict[str, str]) -> str:  # O(1)
    digest = hashlib.sha256()  # O(1)
    for path, value in sorted(digests.items()):  # O(n log n)
        digest.update(path.encode() + b"\0" + value.encode() + b"\0")  # O(1)
    return digest.hexdigest()  # O(1)


def layer_hash(layer: str, root: Path) -> str:  # O(1)
    return hash_digests(layer_digests(layer, root))  # O(n * size)


def checkout_key(root: Path) -> str:  # O(1)
    return str(Path(root).resolve())  # O(1)


def stale_detail(state: Path, layer: str, digests: dict[str, str], checkout: str | None = None) -> str:  # O(1)
    changed = layer_store.changed_files(state, layer, digests, checkout=checkout) if layer_store.has_manifest(state, layer, checkout=checkout) else []  # O(n)
    if not changed:  # O(1)
        return "no green stamp"  # O(1)
    return ", ".join(changed[:5]) + (f" (+{len(changed) - 5} more)" if len(changed) > 5 else "")  # O(1)


def stamp_detail(digest: str, rec: dict) -> str:  # O(1)
    red = rec.get("red")  # O(1)
    names = ", ".join(str(r) for r in red) if isinstance(red, list) and red else "none"  # O(red)
    return f"{digest[:12]} at {rec.get('at', '')}, red: {names}, ruling: {rec.get('ruling', '')}"  # O(1)


def red_cases(path: Path) -> list[str]:  # O(1)
    data = layer_store.read_json(path)  # O(size)
    data = data if isinstance(data, dict) else {}  # O(1)
    suite, cases = data.get("suite"), data.get("cases")  # O(1)
    threshold = suite.get("threshold", 1.0) if isinstance(suite, dict) else 1.0  # O(1)
    threshold = threshold if isinstance(threshold, (int, float)) and not isinstance(threshold, bool) else 1.0  # O(1)
    out = []  # O(1)
    for case in cases if isinstance(cases, list) else []:  # O(cases)
        agg = case.get("aggregates") if isinstance(case, dict) else None  # O(1)
        score = agg.get("score") if isinstance(agg, dict) else None  # O(1)
        if isinstance(case, dict) and (not isinstance(score, (int, float)) or isinstance(score, bool) or score < threshold):  # O(1)
            out.append(str(case.get("name")))  # O(1)
    return out  # O(cases)


def layer_states(root: Path, state: Path) -> list[tuple[str, str, str]]:  # O(1)
    out = []  # O(1)
    checkout = checkout_key(root)  # O(1)
    for layer in LAYERS:  # O(L)
        digests = layer_digests(layer, Path(root))  # O(n * size)
        digest = hash_digests(digests)  # O(n)
        if not digests:  # O(1)
            out.append((layer, "none", ""))  # O(1)
        elif layer_store.is_green(state, layer, digest):  # O(1)
            rec = layer_store.stamp_of(state, layer, digest)  # O(1)
            out.append((layer, "green", digest[:12]) if rec is None else (layer, "stamped", stamp_detail(digest, rec)))  # O(1)
        elif layer_store.running(state, layer, digest):  # O(1)
            out.append((layer, "running", "run in progress"))  # O(1)
        else:  # O(1)
            out.append((layer, "stale", stale_detail(state, layer, digests, checkout)))  # O(n)
    return out  # O(1)


def stale_layers(root: Path, state: Path) -> list[str]:  # O(1)
    return [layer for layer, status, _ in layer_states(root, state) if status == "stale"]  # O(L * n)


def write_stamp(root: Path, state: Path, layer: str, digests: dict | None = None, stamp: dict | None = None) -> None:  # digests taken before a run keep a file changed during it unstamped | O(1)
    digests = layer_digests(layer, Path(root)) if digests is None else digests  # O(n * size)
    layer_store.record_green(state, layer, hash_digests(digests), digests, checkout=checkout_key(root), stamp=stamp)  # O(n)


def toplevel(cwd: str) -> Path:  # O(1)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True)  # O(1)
    return Path(r.stdout.strip() or cwd)  # O(1)


def cmd_check(args, root: Path, state: Path) -> int:  # O(1)
    if not args.hook:  # O(1)
        stale = [f"{layer} stale: {detail}" for layer, status, detail in layer_states(root, state) if status == "stale"]  # O(L * n)
        print("\n".join(stale)) if stale else None  # O(L)
        return 2 if stale else 0  # O(1)
    try:  # O(1)
        return hook_check(args)  # O(L * n)
    except Exception:  # O(1)
        return 0  # O(1)


def hook_check(args) -> int:  # O(1)
    try:  # O(1)
        data = {} if sys.stdin.isatty() else json.loads(sys.stdin.read(1_000_000) or "{}")  # O(size)
        data = data if isinstance(data, dict) else {}  # O(1)
    except ValueError:  # O(1)
        data = {}  # O(1)
    if data.get("stop_hook_active") or os.environ.get("SUPERLITE_TEST_LAYERS") == "off":  # O(1)
        return 0  # O(1)
    root = Path(args.root) if args.root else toplevel(str(data.get("cwd") or os.getcwd()))  # O(1)
    state = Path(args.state) if args.state else layer_store.store_path(root)  # O(1)
    if any((root / ".superlite" / m).exists() for m in MARKERS):  # O(1)
        return 0  # O(1)
    stale = stale_layers(root, state)  # O(L * n)
    if stale:  # O(1)
        names = " ".join(stale)  # O(L)
        reason = f"{names} not run since the last change: run `python3 scripts/test_layers.py run {names}` or `stamp <layer> --ruling \"<why>\"` (status: python3 scripts/test_layers.py status)"  # O(L)
        print(json.dumps({"decision": "block", "reason": reason}))  # O(L)
    return 0  # O(1)


def still_running(output: str) -> tuple[int | None, str, str] | None:  # O(1)
    m = NO_RESULT.search(output)  # O(size)
    return None if m is None else (int(m.group(2)) if m.group(2) else None, m.group(1), m.group(3))  # O(1)


def unit_wait(args) -> float:  # O(1)
    if args.wait is not None:  # O(1)
        return args.wait  # O(1)
    try:  # O(1)
        env = float(os.environ.get("SUPERLITE_UNIT_WAIT", ""))  # O(1)
    except ValueError:  # O(1)
        return DEFAULT_UNIT_WAIT  # O(1)
    return env if env > 0 else DEFAULT_UNIT_WAIT  # O(1)


def pending_wait(state: Path, layer: str, before: str) -> str | None:  # the wait command of the unit run still pending for these exact digests | O(1)
    rec = layer_store.pending(state, layer) if layer == "unit" else {}  # O(size)
    wait = rec.get("wait")  # O(1)
    if not isinstance(wait, str) or rec.get("digest") != before:  # O(1)
        return None  # O(1)
    pid = rec.get("pid")  # O(1)
    try:  # O(1)
        summary = Path(shlex.split(wait)[-1])  # O(1)
    except ValueError:  # O(1)
        return None  # O(1)
    alive = isinstance(pid, int) and not isinstance(pid, bool) and layer_store.pid_alive(pid)  # O(1)
    return wait if alive or summary.exists() else None  # O(1)


def cmd_run(args, root: Path, state: Path) -> int:  # O(1)
    override = dict(item.split("=", 1) for item in (args.command_override or []))  # O(k)
    code, running = 0, False  # O(1)
    for layer in args.layers:  # O(L)
        if layer not in LAYERS:  # O(1)
            print(f"{layer}: unknown layer", file=sys.stderr)  # O(1)
            code = 1  # O(1)
            continue  # O(1)
        env = {**os.environ, **({"SUPERLITE_E2E": "1"} if layer in ("headless", "tui") else {})}  # O(env)
        digests = layer_digests(layer, root)  # O(n * size)
        before = hash_digests(digests)  # O(n)
        resumed = pending_wait(state, layer, before)  # O(1)
        layer_store.start_run(state, layer, before, os.getpid())  # O(1)
        command = override.get(layer, unit_command(unit_wait(args)) if layer == "unit" else COMMANDS[layer])  # O(1)
        if resumed:  # O(1)
            print(f"{layer}: waiting on the run started earlier: {resumed}", file=sys.stderr)  # O(1)
            command = f"{resumed} --timeout {unit_wait(args):g}"  # O(1)
        try:  # O(1)
            r = subprocess.run(command, shell=True, cwd=root, env=env, capture_output=True, text=True)  # O(run)
        finally:  # O(1)
            layer_store.end_run(state, layer)  # O(1)
        if r.returncode == 0:  # O(1)
            write_stamp(root, state, layer, digests)  # O(n)
            print(f"{layer}: green")  # O(1)
            continue  # O(1)
        text = r.stdout + r.stderr  # O(size)
        wait = still_running(text)  # O(size)
        if wait:  # O(1)
            pid, secs, rerun = wait  # O(1)
            if pid:  # O(1)
                layer_store.start_run(state, layer, before, pid, wait=rerun)  # O(1)
            print(f"{layer}: running (no result after {secs} s; run `python3 scripts/test_layers.py run {layer}` again to wait on this run and stamp it; see it: {rerun})")  # O(1)
            running = True  # O(1)
            continue  # O(1)
        print(f"{layer}: red")  # O(1)
        print("\n".join(text.splitlines()[-20:]), file=sys.stderr)  # O(1)
        code = 1  # O(1)
    return code or (4 if running else 0)  # O(1)


def cmd_stamp(args, root: Path, state: Path) -> int:  # O(1)
    if args.layer not in LAYERS:  # O(1)
        print(f"{args.layer}: unknown layer", file=sys.stderr)  # O(1)
        return 1  # O(1)
    red = args.red if args.red is not None else red_cases(root / "evals" / "results" / "last.json") if args.layer == "evals" else []  # O(cases)
    ruling = " ".join(args.ruling.split())  # O(size)
    write_stamp(root, state, args.layer, stamp={"ruling": ruling, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "red": red})  # O(n)
    progress = root / ".superlite" / "progress.md"  # O(1)
    progress.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    with progress.open("a") as f:  # O(1)
        f.write(f"Ruling: skip {args.layer} - {args.ruling}\n")  # O(1)
    print(f"{args.layer}: stamped (red: {', '.join(red) if red else 'none'})")  # O(red)
    return 0  # O(1)


def cmd_status(args, root: Path, state: Path) -> int:  # O(1)
    for layer, status, detail in layer_states(root, state):  # O(L * n)
        print(f"{layer} none" if status == "none" else f"{layer} {status} " + (f"({detail})" if status == "stale" else detail))  # O(1)
    return 0  # O(1)


def main(argv: list[str] | None = None) -> int:  # O(1)
    common = argparse.ArgumentParser(add_help=False)  # O(1)
    common.add_argument("--root")  # O(1)
    common.add_argument("--state")  # O(1)
    parser = argparse.ArgumentParser(description="Map changes to test layers and stamp green runs.")  # O(1)
    sub = parser.add_subparsers(dest="cmd", required=True)  # O(1)
    sub.add_parser("check", parents=[common]).add_argument("--hook", action="store_true")  # O(1)
    sub.add_parser("status", parents=[common])  # O(1)
    run = sub.add_parser("run", parents=[common])  # O(1)
    run.add_argument("layers", nargs="+")  # O(1)
    run.add_argument("--command-override", nargs="+")  # O(1)
    run.add_argument("--wait", type=float)  # O(1)
    stamp = sub.add_parser("stamp", parents=[common])  # O(1)
    stamp.add_argument("layer")  # O(1)
    stamp.add_argument("--ruling", required=True)  # O(1)
    stamp.add_argument("--red", nargs="*")  # O(1)
    args = parser.parse_args(argv)  # O(1)
    root = Path(args.root) if args.root else toplevel(os.getcwd())  # O(1)
    state = Path(args.state) if args.state else layer_store.store_path(root)  # O(1)
    return {"check": cmd_check, "status": cmd_status, "run": cmd_run, "stamp": cmd_stamp}[args.cmd](args, root, state)  # O(run)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(run)
