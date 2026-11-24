"""Shared helpers for running pytest from the superlite scripts. Stdlib only.

project_python(root): the project's own interpreter, found by file lookup and never run:
`root/.venv/bin/python` (Windows `root/.venv/Scripts/python.exe`), else the same layout under
the `VIRTUAL_ENV` environment variable, else `sys.executable`. Checks run in it so they see the
project's packages, not only superlite's. #1068: a lead worktree or task tree also finds the main
checkout's `.venv` (main_checkout reads `.git` files, never runs git); project_cmd(root) returns the
argv prefix: that interpreter, else `uv run --frozen --project root python` for a uv project, else ours.

uv_project_env(command, root, cwd, environ): a `uv run --no-project` command that finds no Python environment
(no VIRTUAL_ENV, no `.venv` in cwd or a parent) runs in the project's environment: rewritten to
`--frozen --project root` for a uv project, else the main checkout's venv is exported (#1120).
A .venv it finds only above root (a worktree nested in the main checkout, a task tree) is another checkout's: a uv project root runs --frozen --project root too, any other root keeps the command with a note (#1133).

pytest_cmd(): command prefix that runs pytest. Uses the current interpreter when it can
import pytest, else `uv run --no-project --with pytest python -m pytest`, else raises
PytestUnavailable with a clear message (`sl` may have fallen back to a bare
`uv run --no-project python`, which has no pytest).

run_tree(cmd, timeout, **kw): subprocess.run that, on timeout, kills the whole process
tree of the child it started (POSIX: new session + killpg; Windows: new process group +
`taskkill /T /F /PID <child>`), never by name. Raises subprocess.TimeoutExpired.

spawn_detached(cmd, log): start cmd detached (own session / process group, stdin closed,
output to the log file, UTF-8 forced) and return the Popen without waiting. The child owns
its process tree (it runs run_tree itself); callers only ever kill the PID they got back.
"""
# Complexity notation:
#   o = bytes of child stdout + stderr, a = length of the command argv, D = descendants of the child process, P = directories on PATH
import importlib.util  # O(1)
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import shutil  # O(1)
import signal  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)


VENV_PYTHONS = (("bin", "python"), ("Scripts", "python.exe"))  # O(1) POSIX layout, then Windows layout


def venv_python(venv):  # O(1) two stat calls
    """The interpreter file inside the venv folder, or None."""  # O(1)
    layouts = VENV_PYTHONS[::-1] if os.name == "nt" else VENV_PYTHONS  # O(1) native layout first
    for folder, name in layouts:  # O(1) two layouts
        cand = Path(venv) / folder / name  # O(1)
        if cand.is_file():  # O(1) stat; the file is never run
            return str(cand)  # O(1)
    return None  # O(1)


def main_checkout(root):  # O(d) d = folders from root up to the first .git; stat and small reads, git never runs
    """The main checkout holding root: the first .git up the tree is a folder (that checkout) or a linked-worktree file (its commondir's parent); else None."""  # O(1)
    here = Path(root).resolve()  # O(d)
    for folder in (here, *here.parents):  # O(d)
        dot_git = folder / ".git"  # O(1)
        if dot_git.is_dir():  # O(1) stat
            return folder  # O(1)
        if not dot_git.exists():  # O(1) stat
            continue  # O(1)
        try:  # O(1)
            line = dot_git.read_text(encoding="utf-8").strip()  # O(1) small file
            if not line.startswith("gitdir:"):  # O(1)
                return None  # O(1)
            gitdir = folder / line[len("gitdir:"):].strip()  # O(1) relative to the folder holding .git
            common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()  # O(1) commondir may be absolute
        except (OSError, ValueError):  # unreadable or undecodable link | O(1)
            return None  # O(1)
        return common.parent if common.name == ".git" else None  # O(1)
    return None  # O(1)


def found_python(root):  # O(d) up to five stat calls plus the .git walk; None when no venv interpreter exists
    """root/.venv's interpreter, else the main checkout's .venv one (#1068), else the VIRTUAL_ENV one, else None."""  # O(1)
    found = venv_python(Path(root) / ".venv")  # O(1)
    if found:  # O(1)
        return found  # O(1)
    main = main_checkout(root)  # O(d)
    if main is not None and main != Path(root).resolve():  # O(d)
        found = venv_python(main / ".venv")  # O(1) returned unresolved
        if found:  # O(1)
            return found  # O(1)
    env = os.environ.get("VIRTUAL_ENV")  # O(1)
    return venv_python(env) if env else None  # O(1)


def project_python(root):  # O(d) found_python or sys.executable
    """root/.venv's interpreter, else the main checkout's .venv one (#1068), else the VIRTUAL_ENV one, else sys.executable."""  # O(1)
    return found_python(root) or sys.executable  # O(d)


def project_cmd(root):  # O(d + P) PATH search
    """argv prefix for the project's python: the found interpreter, else uv run --frozen for a uv project (#1068), else ours."""  # O(1)
    py = project_python(root)  # O(d)
    if py != sys.executable or found_python(root):  # a found interpreter that equals ours is still found | O(d)
        return [py]  # O(1)
    uv = shutil.which("uv")  # O(P) PATH search
    if uv and (Path(root) / "uv.lock").is_file() and (Path(root) / "pyproject.toml").is_file():  # O(1) two stats
        return [uv, "run", "--frozen", "--project", str(root), "python"]  # O(1)
    return [py]  # O(1)


def found_env(cwd):  # O(d) stat calls up the cwd parents; never runs uv
    """The first folder from cwd up whose .venv holds an interpreter (the one `uv run --no-project` uses), else None."""  # O(1)
    here = Path(os.path.abspath(cwd))  # O(d) absolute, unresolved: notes keep the caller's spelling
    return next((folder for folder in (here, *here.parents) if venv_python(folder / ".venv")), None)  # O(d)


def inside(folder, root):  # O(d) two resolves
    """True when folder is root or lies below it, both resolved (a symlinked spelling of the root counts)."""  # O(1)
    top, here = Path(root).resolve(), Path(folder).resolve()  # O(d)
    return here == top or top in here.parents  # O(d)


NO_PROJECT = re.compile(r"(?<!\S)--no-project(?!\S)")  # O(1)
PROGRAM_WORD = re.compile(r"^(python|python3(\.\d+)?|pytest|py\.test)$")  # O(1)
UV_VALUE_OPTIONS = frozenset({"--with", "--python", "-p", "--group", "--extra", "--with-requirements", "--directory", "--project", "--env-file", "--index"})  # O(1)


def _no_project_uv(command):  # O(c) c = length of the command; True when it is `[NAME=v ...] uv run ... --no-project ... program`
    try:  # O(1)
        words = shlex.split(command)  # O(c)
    except ValueError:  # unbalanced quote | O(1)
        return False  # O(1)
    i = 0  # O(1)
    while i < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]):  # O(c)
        i += 1  # O(1)
    if i + 1 >= len(words) or os.path.basename(words[i]) != "uv" or words[i + 1] != "run":  # O(1)
        return False  # O(1)
    j = i + 2  # O(1)
    while j < len(words):  # O(c)
        word = words[j]  # O(1)
        if word == "--no-project":  # O(1)
            return True  # O(1)
        if word == "--" or PROGRAM_WORD.match(os.path.basename(word)):  # the program word ends the uv options | O(1)
            return False  # O(1)
        j += 2 if word in UV_VALUE_OPTIONS else 1  # a value-taking option consumes the next word; --opt=value is one word | O(1)
    return False  # O(1)


def uv_project_env(command, root, cwd, environ):  # O(c + d) command parse plus stat calls up the cwd parents; never runs uv or git
    """(command, extra environ, note) for a `uv run --no-project` command whose environment is missing (#1120) or another checkout's (#1133); else (command, {}, "")."""  # O(1)
    if not _no_project_uv(command) or environ.get("VIRTUAL_ENV"):  # O(c)
        return command, {}, ""  # O(1)
    uv_project = (Path(root) / "uv.lock").is_file() and (Path(root) / "pyproject.toml").is_file()  # O(1) two stats
    flags = f"--frozen --project {shlex.quote(str(root))}"  # O(1)
    folder = found_env(cwd)  # O(d) the environment uv would use
    if folder is not None:  # O(1)
        if inside(folder, root):  # the root's or its run folder's own environment | O(d)
            return command, {}, ""  # O(1)
        base = f"uv run --no-project would use {folder / '.venv'}, which lies outside {root}"  # another checkout's: a nested worktree or tree (#1133) | O(1)
        if uv_project:  # O(1)
            return NO_PROJECT.sub(flags, command, count=1), {}, f"{base}; running in {root}'s own environment: uv run {flags} (#1133)"  # O(c)
        return command, {}, f"{base}, and {root} has no uv.lock for an environment of its own; the tests may import that folder's package, not {root}'s (#1133)"  # O(1)
    base = f"uv run --no-project finds no environment from {cwd}"  # O(1)
    if uv_project:  # O(1)
        return NO_PROJECT.sub(flags, command, count=1), {}, f"{base}; running in the project's environment: uv run {flags} (#1120)"  # O(c)
    py = found_python(root)  # O(d)
    if py:  # O(1)
        venv = str(Path(py).parent.parent)  # O(1)
        return command, {"VIRTUAL_ENV": venv}, f"{base}; using the project's environment {venv} (VIRTUAL_ENV) (#1120)"  # O(1)
    return command, {}, f"{base} and {root} has no uv.lock; the project's own package may not import (#1120)"  # O(1)


class PytestUnavailable(RuntimeError):  # O(1)
    pass  # O(1)


def have_pytest():  # O(1) import-path lookup (cached after first call)
    return importlib.util.find_spec("pytest") is not None  # O(1) import-path lookup


def pytest_cmd():  # O(P) PATH search
    if have_pytest():  # O(1) import-path lookup
        return [sys.executable, "-m", "pytest"]  # O(1)
    uv = shutil.which("uv")  # O(P) PATH search
    if uv:  # O(1)
        return [uv, "run", "--no-project", "--with", "pytest", "python", "-m", "pytest"]  # O(1)
    raise PytestUnavailable("pytest is not installed for this interpreter "  # O(len(sys.executable))
                            f"({sys.executable}) and uv is not on PATH; "  # O(1)
                            "install pytest (pip install pytest) or uv")  # O(1)


def kill_tree(proc):  # O(D) + process spawn (taskkill)
    """Kill proc and all its descendants. Only the process we started."""  # O(1)
    try:  # O(1)
        if os.name == "nt":  # O(1)
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],  # O(D) + process spawn (taskkill), output O(1) bytes
                           capture_output=True, check=False)  # O(1)
        else:  # O(1)
            os.killpg(proc.pid, signal.SIGKILL)  # O(D) signal syscall
    except (OSError, ProcessLookupError):  # O(1)
        pass  # O(1)
    try:  # O(1)
        proc.kill()  # O(1)
    except OSError:  # O(1)
        pass  # O(1)


def run_tree(cmd, timeout=None, **kw):  # O(a + o) + process spawn; on timeout adds O(D) kill
    if os.name == "nt":  # O(1)
        kw["creationflags"] = kw.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # O(1) hidden console
    else:  # O(1)
        kw["start_new_session"] = True  # O(1)
    kw.setdefault("stdout", subprocess.PIPE)  # O(1)
    kw.setdefault("stderr", subprocess.PIPE)  # O(1)
    if kw.pop("capture_output", False):  # O(1)
        kw["stdout"] = kw["stderr"] = subprocess.PIPE  # O(1)
    with subprocess.Popen(cmd, **kw) as proc:  # O(a) + process spawn
        try:  # O(1)
            out, err = proc.communicate(timeout=timeout)  # O(o) read until exit or timeout
        except subprocess.TimeoutExpired as e:  # O(1)
            kill_tree(proc)  # O(D) + process spawn (taskkill) on POSIX O(D) signal
            proc.communicate()  # O(o) drain remaining output
            raise subprocess.TimeoutExpired(cmd, timeout, e.output, e.stderr) from None  # O(o)
        except BaseException:  # O(1)
            kill_tree(proc)  # O(D) kill
            raise  # O(1)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)  # O(1)


def spawn_detached(cmd, log, **kw):  # O(a) + process spawn; does not wait
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # O(env)
    if os.name == "nt":  # O(1)
        kw["creationflags"] = (kw.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP  # O(1)
                               | subprocess.CREATE_NO_WINDOW)  # never DETACHED_PROCESS: it makes CREATE_NO_WINDOW ignored and every console child pops a window | O(1)
    else:  # O(1)
        kw["start_new_session"] = True  # O(1)
    with open(log, "ab") as fh:  # O(1)
        return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,  # O(a) + process spawn
                                env=env, close_fds=True, **kw)  # O(1)
