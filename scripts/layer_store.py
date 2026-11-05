#!/usr/bin/env python3
"""Shared store of green test-layer hashes, the run lock and the last green file manifest."""
from __future__ import annotations  # O(1)
import json  # O(1)
import os  # O(1)
import subprocess  # O(1)
import contextlib  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

KEEP = 200  # O(1)  newest green hashes kept per layer
STILL_ACTIVE = 259  # O(1)  Windows GetExitCodeProcess value of a live process


def store_path(root: Path) -> Path:  # O(1)
    try:  # O(1)
        r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=root, capture_output=True, text=True)  # O(1)
    except OSError:  # O(1)
        return Path(root) / ".superlite" / "test-layers.json"  # O(1)
    if r.returncode != 0 or not r.stdout.strip():  # O(1)
        return Path(root) / ".superlite" / "test-layers.json"  # O(1)
    return (Path(root) / r.stdout.strip()).resolve() / "superlite" / "test-layers.json"  # O(1)


def read_json(path: Path) -> dict:  # O(1)
    try:  # O(1)
        data = json.loads(Path(path).read_text(encoding="utf-8"))  # O(size)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return data if isinstance(data, dict) else {}  # O(1)


def write_json(path: Path, data: dict) -> None:  # O(1)
    path = Path(path)  # O(1)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")  # O(1)
    try:  # O(1)
        with os.fdopen(fd, "w", encoding="utf-8") as f:  # O(1)
            json.dump(data, f, indent=1, sort_keys=True)  # O(size)
        os.replace(tmp, path)  # O(1)
    except BaseException:  # O(1)
        try:  # O(1)
            os.unlink(tmp)  # O(1)
        except OSError:  # O(1)
            pass  # O(1)
        raise  # O(1)


def layer_entry(store: Path, layer: str) -> dict:  # O(1)
    layers = read_json(store).get("layers")  # O(size)
    entry = layers.get(layer) if isinstance(layers, dict) else None  # O(1)
    return entry if isinstance(entry, dict) else {}  # O(1)


def manifest_of(entry: dict) -> dict:  # O(1)
    files = entry.get("files")  # O(1)
    return files if isinstance(files, dict) else {}  # O(1)


def is_green(store: Path, layer: str, digest: str) -> bool:  # O(1)
    green = layer_entry(store, layer).get("green")  # O(size)
    return isinstance(green, list) and digest in green  # O(KEEP)


def _lock(store: Path):  # O(1)  exclusive sidecar lock around a read-modify-write; unlocked when unavailable
    return _locked(Path(store).with_name("test-layers.lock"))  # O(1)


@contextlib.contextmanager
def _locked(path: Path):  # O(1)
    fd = None  # O(1)
    kind = ""  # O(1)
    try:  # O(1)
        path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)  # O(1)
        if os.name == "nt":  # O(1)
            import msvcrt  # O(1)
            os.write(fd, b"0") if os.fstat(fd).st_size == 0 else None  # O(1)
            os.lseek(fd, 0, 0)  # O(1)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)  # O(wait)
            kind = "nt"  # O(1)
        else:  # O(1)
            import fcntl  # O(1)
            fcntl.flock(fd, fcntl.LOCK_EX)  # O(wait)
            kind = "posix"  # O(1)
    except (OSError, ImportError):  # O(1)
        kind = ""  # O(1)  proceed unlocked
    try:  # O(1)
        yield  # O(1)
    finally:  # O(1)
        if fd is not None:  # O(1)
            try:  # O(1)
                if kind == "nt":  # O(1)
                    import msvcrt  # O(1)
                    os.lseek(fd, 0, 0)  # O(1)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # O(1)
            except OSError:  # O(1)
                pass  # O(1)
            os.close(fd)  # O(1)


def record_green(store: Path, layer: str, digest: str, files: dict[str, str]) -> None:  # O(1)
    with _lock(store):  # O(wait)
        data = read_json(store)  # O(size)
        layers = data.get("layers") if isinstance(data.get("layers"), dict) else {}  # O(1)
        entry = layers.get(layer) if isinstance(layers.get(layer), dict) else {}  # O(1)
        old = entry.get("green") if isinstance(entry.get("green"), list) else []  # O(1)
        green = [d for d in old if d != digest] + [digest]  # O(KEEP)
        layers[layer] = {"green": green[-KEEP:], "files": dict(files)}  # O(files)
        write_json(store, {"version": 1, "layers": layers})  # O(size)


def changed_files(store: Path, layer: str, files: dict[str, str]) -> list[str]:  # O(1)
    last = manifest_of(layer_entry(store, layer))  # O(size)
    return sorted(p for p in set(files) | set(last) if files.get(p) != last.get(p))  # O(n log n)


def has_manifest(store: Path, layer: str) -> bool:  # O(1)
    return isinstance(layer_entry(store, layer).get("files"), dict)  # O(size)


def lock_path(store: Path) -> Path:  # O(1)
    return Path(store).with_name("running.json")  # O(1)


def start_run(store: Path, layer: str, digest: str, pid: int) -> None:  # O(1)
    with _lock(store):  # O(wait)
        lock = read_json(lock_path(store))  # O(size)
        lock[layer] = {"pid": pid, "digest": digest}  # O(1)
        write_json(lock_path(store), lock)  # O(size)


def end_run(store: Path, layer: str) -> None:  # O(1)
    with _lock(store):  # O(wait)
        lock = read_json(lock_path(store))  # O(size)
        if layer in lock:  # O(1)
            del lock[layer]  # O(1)
            write_json(lock_path(store), lock)  # O(size)


def pid_alive(pid: int) -> bool:  # O(1)
    try:  # O(1)
        return _pid_alive(pid)  # O(1)
    except Exception:  # O(1)  huge pid (OverflowError), ctypes.windll or ArgumentError: unknown means not alive
        return False  # O(1)


def _pid_alive(pid: int) -> bool:  # O(1)
    if os.name == "nt":  # O(1)  os.kill(pid, 0) would terminate the process on Windows
        import ctypes  # O(1)
        kernel32 = ctypes.windll.kernel32  # O(1)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # O(1)  PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:  # O(1)
            return False  # O(1)
        code = ctypes.c_ulong()  # O(1)
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))  # O(1)
        kernel32.CloseHandle(handle)  # O(1)
        return bool(ok) and code.value == STILL_ACTIVE  # O(1)
    try:  # O(1)
        os.kill(pid, 0)  # O(1)
    except ProcessLookupError:  # O(1)
        return False  # O(1)
    except PermissionError:  # O(1)
        return True  # O(1)
    except OSError:  # O(1)
        return False  # O(1)
    return True  # O(1)


def running(store: Path, layer: str, digest: str) -> bool:  # O(1)
    held = read_json(lock_path(store)).get(layer)  # O(size)
    if not isinstance(held, dict) or held.get("digest") != digest:  # O(1)
        return False  # O(1)
    pid = held.get("pid")  # O(1)
    return isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 and pid_alive(pid)  # O(1)
