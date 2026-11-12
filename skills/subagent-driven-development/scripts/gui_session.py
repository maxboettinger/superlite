#!/usr/bin/env python3
"""macOS GUI session check for xcodebuild tests (#561).

A macOS `xcodebuild test` needs the desktop login session (testmanagerd). Without it the run fails before any test, which is an
environment fault, not a red test. Library: needs_gui, session_kind, preflight, runner_unreachable, unreachable_reason. Stdlib only.
"""
# Complexity notation:
#   n = command length, w = words in a segment, o = output length
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import shutil  # O(1)
import subprocess  # O(1)
from pathlib import PurePosixPath  # O(1)

import testcmd  # O(1)

TIMEOUT = 5  # seconds launchctl may take | O(1)
FALLBACK = ("fallback: swift test for package targets, else an iOS Simulator destination "
            "(--destination 'platform=iOS Simulator,name=<device>'), else run it from the logged-in desktop session")  # O(1)
UNREACHABLE = re.compile(r"testmanagerd|Failed to establish communication with the test runner|never finished bootstrapping|Test runner never began executing tests")  # O(1)
EXECUTED = re.compile(r"Executed [1-9]\d* tests?|^\s*Test [Cc]ase '|^\W*[◇✔✘] Test ", re.MULTILINE)  # O(1)
GUI_PLATFORMS = ("macOS", "macCatalyst")  # O(1)


def _segment_needs_gui(seg: str) -> bool:  # one command segment runs a macOS xcodebuild test | O(w)
    try:  # O(1)
        words = shlex.split(seg)  # O(n)
    except ValueError:  # O(1)
        return False  # O(1)
    idx = next((i for i, w in enumerate(words) if PurePosixPath(w).name == "xcodebuild"), -1)  # O(w)
    if idx < 0 or any(not (w in ("env", "xcrun") or re.match(r"[A-Za-z_]\w*=", w)) for w in words[:idx]):  # O(w)
        return False  # O(1)
    rest = words[idx + 1:]  # O(w)
    if "test" not in rest and "test-without-building" not in rest:  # O(w)
        return False  # O(1)
    dests = [rest[i + 1] for i, w in enumerate(rest[:-1]) if w == "-destination"]  # O(w)
    return not dests or any(testcmd.destination_platform(d) in GUI_PLATFORMS for d in dests)  # O(w)


def needs_gui(command: str) -> bool:  # the command runs an xcodebuild test on macOS or Mac Catalyst | O(n)
    return any(_segment_needs_gui(seg) for seg in testcmd._segments(command)[::2])  # O(n)


def session_kind(launchctl: str | None = None) -> str | None:  # `launchctl managername` first line, None when unknown | O(1)
    path = launchctl or shutil.which("launchctl")  # O(path)
    if not path:  # O(1)
        return None  # O(1)
    try:  # O(1)
        r = subprocess.run([path, "managername"], capture_output=True, text=True, timeout=TIMEOUT)  # O(1)
    except (OSError, subprocess.TimeoutExpired):  # O(1)
        return None  # O(1)
    lines = r.stdout.strip().splitlines() if r.returncode == 0 else []  # O(o)
    return lines[0].strip() if lines else None  # O(1)


def preflight(commands: list[str]) -> str | None:  # ENV-ERROR text when a macOS xcodebuild test would run outside the desktop session | O(c*n)
    if os.environ.get("SUPERLITE_GUI_CHECK") == "0" or not any(needs_gui(c) for c in commands):  # O(c*n)
        return None  # O(1)
    kind = session_kind()  # O(1)
    if kind is None or kind == "Aqua":  # O(1)
        return None  # O(1)
    return (f"ENV-ERROR: no macOS GUI session (launchctl managername: {kind}, not Aqua): xcodebuild test on macOS needs the "
            f"desktop login session (testmanagerd), so nothing ran; {FALLBACK}; SUPERLITE_GUI_CHECK=0 skips this check")  # O(1)


def runner_unreachable(text: str) -> bool:  # xcodebuild could not reach its test runner and no test executed | O(o)
    return bool(UNREACHABLE.search(text)) and not EXECUTED.search(text)  # O(o)


def unreachable_reason(kind: str | None) -> str:  # ENV-ERROR text for a run whose test runner was unreachable | O(1)
    return ("ENV-ERROR: xcodebuild could not reach its test runner (testmanagerd) and ran no test: an environment fault, "
            f"not a test failure; session: {kind or 'unknown'}; {FALLBACK}")  # O(1)
