"""mcp_check: GUI session and tools/list handshake for fleet worker MCP servers (#576)."""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import mcp_check  # noqa: E402

STUB_SRC = r'''
import json, sys
flag = sys.argv[1] if len(sys.argv) > 1 else ""
counter = sys.argv[2] if len(sys.argv) > 2 else ""
if counter:
    with open(counter, "a") as f:
        f.write("x\n")
def send(obj):
    print(json.dumps(obj), flush=True)
for line in sys.stdin:
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if flag == "silent":
        continue
    if flag == "noise":
        print("loading plugins...", flush=True)
    if msg.get("id") == 1:
        send({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "stub", "version": "1"}}})
    elif msg.get("id") == 2:
        if flag == "error":
            send({"jsonrpc": "2.0", "id": 2, "error": {"message": "nope"}})
        else:
            send({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "ping", "inputSchema": {"type": "object"}}]}})
'''


@pytest.fixture
def stub(tmp_path):
    path = tmp_path / "stub.py"
    path.write_text(STUB_SRC)

    def make(flag="", counter=None):
        args = [str(path), flag] + ([str(counter)] if counter else [])
        return {"command": sys.executable, "args": args}
    return make


@pytest.fixture
def probing(monkeypatch):
    monkeypatch.delenv("SUPERLITE_MCP_CHECK", raising=False)


def test_probe_ok(stub):
    assert mcp_check.probe(stub()) is None


def test_probe_exit_before_answer():
    d = {"command": sys.executable, "args": ["-c", "import sys; sys.exit(3)"]}
    assert mcp_check.probe(d) == "exited before answering tools/list (exit 3)"


def test_command_not_found(probing, tmp_path):
    assert mcp_check.check("docs", {"command": "no-such-cmd-576"}, tmp_path) == "command no-such-cmd-576 not found"


def test_stdout_noise_is_skipped(stub):
    assert mcp_check.probe(stub("noise")) is None


def test_silent_server_times_out(stub):
    t0 = time.time()
    assert mcp_check.probe(stub("silent"), timeout=1) == "did not answer tools/list in 1 s"
    assert time.time() - t0 < 5


def test_silent_server_process_is_gone(stub, tmp_path, monkeypatch):
    killed = []
    real = mcp_check.subprocess.Popen

    class Spy(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            killed.append(self)
    monkeypatch.setattr(mcp_check.subprocess, "Popen", Spy)
    mcp_check.probe(stub("silent"), timeout=1)
    assert killed and killed[0].poll() is not None


def test_tools_list_error(stub):
    assert mcp_check.probe(stub("error")) == "tools/list error: nope"


def test_http_not_probed(probing, tmp_path):
    assert mcp_check.check("web", {"type": "http", "url": "http://127.0.0.1:9"}, tmp_path) is None


def test_gui_background_reason(probing, monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_check.sys, "platform", "darwin")
    monkeypatch.setattr(mcp_check.gui_session, "session_kind", lambda *a, **k: "Background")
    d = {"type": "stdio", "command": "xcrun", "args": ["mcpbridge"]}
    assert mcp_check.check("xcode", d, tmp_path) == "no macOS GUI session (launchctl managername: Background, not Aqua)"


def test_gui_aqua_passes_to_probe(probing, stub, monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_check.sys, "platform", "darwin")
    monkeypatch.setattr(mcp_check.gui_session, "session_kind", lambda *a, **k: "Aqua")
    assert mcp_check.check("xcode", stub(), tmp_path) is None


def test_cache_skips_second_start(probing, stub, tmp_path):
    counter = tmp_path / "count"
    d = stub(counter=counter)
    sd = tmp_path / "sd"
    assert mcp_check.check("docs", d, sd) is None
    assert mcp_check.check("docs", d, sd) is None
    assert counter.read_text().count("x") == 1
    d2 = stub("", counter)
    d2["env"] = {"A": "1"}
    assert mcp_check.check("docs", d2, sd) is None
    assert counter.read_text().count("x") == 2
    cache = sd / "fleet" / "mcp-check.json"
    data = json.loads(cache.read_text())
    for v in data.values():
        v["at"] = time.time() - 601
    cache.write_text(json.dumps(data))
    assert mcp_check.check("docs", d, sd) is None
    assert counter.read_text().count("x") == 3


def test_cache_not_object_counts_empty(probing, stub, tmp_path):
    sd = tmp_path / "sd"
    (sd / "fleet").mkdir(parents=True)
    (sd / "fleet" / "mcp-check.json").write_text("[1]")
    assert mcp_check.check("docs", stub(), sd) is None


def test_check_off(stub, tmp_path, monkeypatch):
    counter = tmp_path / "count"
    monkeypatch.setenv("SUPERLITE_MCP_CHECK", "0")
    assert mcp_check.check("docs", stub(counter=counter), tmp_path / "sd") is None
    assert not counter.exists()


@pytest.mark.skipif(os.name == "nt", reason="process groups are POSIX only")
def test_wrapper_grandchild_is_stopped(tmp_path):
    pidfile = tmp_path / "grandchild.pid"
    code = (
        "import subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(g.pid))\n"
        "time.sleep(60)\n"
    )
    t0 = time.time()
    assert mcp_check.probe({"command": sys.executable, "args": ["-c", code]}, timeout=1) == "did not answer tools/list in 1 s"
    assert time.time() - t0 < 8
    pid = int(pidfile.read_text())
    gone = False
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            gone = True
            break
        time.sleep(0.1)
    if not gone:
        os.kill(pid, 9)
    assert gone
