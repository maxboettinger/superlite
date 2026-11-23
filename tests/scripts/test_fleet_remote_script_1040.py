# tests/scripts/test_fleet_remote_script_1040.py: host script helpers of fleet_remote_worker (#1040)
import contextlib, shlex, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote as fr  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402
import herdr_client as real_hc  # noqa: E402

OUT = "/h/t/.superlite/golden/attempt.out"


class FakeHc:
    HerdrError = real_hc.HerdrError

    def __init__(self):
        self.calls, self.run_error, self.close_error = [], None, None

    @contextlib.contextmanager
    def on(self, m):
        self.calls.append(("on", m))
        try:
            yield
        finally:
            self.calls.append(("off", m))

    def create_workspace(self, title, cwd, env):
        self.calls.append(("create_workspace", title, cwd, env))
        return "w1", "p1"

    def run_in_pane(self, pane, cmd):
        self.calls.append(("run_in_pane", pane, cmd))
        if self.run_error:
            raise self.run_error

    def close_workspace(self, ws):
        self.calls.append(("close_workspace", ws))
        if self.close_error:
            raise self.close_error


@pytest.fixture
def hc(monkeypatch):
    fake = FakeHc()
    monkeypatch.setattr(rw, "hc", fake)
    return fake


def _fake_read(monkeypatch, data=None, error=None):
    def read(label, path, offset=0):
        assert (label, path) == ("mxn", OUT)
        if error:
            raise error
        return data[offset:] if offset == 0 else b""
    monkeypatch.setattr(rw.fr, "read", read)


def test_run_script_opens_workspace_and_runs_sh(hc):
    assert rw.run_script("mxn", "/h/t", "echo hi", OUT, "sl:golden small-1") == "w1"
    assert [c[0] for c in hc.calls] == ["on", "create_workspace", "run_in_pane", "off"]
    assert hc.calls[0] == ("on", "mxn") and hc.calls[-1] == ("off", "mxn")
    assert hc.calls[1] == ("create_workspace", "sl:golden small-1", "/h/t", {})
    assert hc.calls[2][1] == "p1"
    cmd = hc.calls[2][2]
    assert cmd.startswith("sh -c ")
    full = shlex.split(cmd)[2]
    assert "mkdir -p /h/t/.superlite/golden;" in full
    assert "cd /h/t && echo hi" in full
    assert f"{OUT}.tmp" in full and full.endswith(f"mv {OUT}.tmp {OUT}")


def test_run_script_wrapper_runs_under_sh(hc, tmp_path):
    cwd = tmp_path / "a dir"
    cwd.mkdir()
    out = tmp_path / "o d" / "attempt.out"
    rw.run_script("mxn", str(cwd), "echo hi; exit 3", str(out), "t")
    cmd = hc.calls[2][2]
    subprocess.run(cmd, shell=True, check=True)
    assert out.read_text() == "hi\nexit 3\n"
    assert not (out.parent / "attempt.out.tmp").exists()


def test_run_script_closes_workspace_when_run_fails(hc):
    hc.run_error = real_hc.HerdrError("exit", "x")
    with pytest.raises(real_hc.HerdrError):
        rw.run_script("mxn", "/h/t", "echo hi", OUT, "t")
    assert ("close_workspace", "w1") in hc.calls


def test_script_result_none_while_absent(monkeypatch):
    _fake_read(monkeypatch, b"")
    assert rw.script_result("mxn", OUT) is None


def test_script_result_exit_line(monkeypatch):
    _fake_read(monkeypatch, b"row written\nexit 0\n")
    assert rw.script_result("mxn", OUT) == (0, "row written")
    _fake_read(monkeypatch, b"golden: cannot read case x\nexit 2\n")
    assert rw.script_result("mxn", OUT) == (2, "golden: cannot read case x")
    _fake_read(monkeypatch, b"partial\n")
    assert rw.script_result("mxn", OUT) is None


def test_script_result_reads_every_chunk(monkeypatch):
    chunks = {0: b"line one\n", 9: b"exit 0\n"}

    def read(label, path, offset=0):
        return chunks.get(offset, b"")
    monkeypatch.setattr(rw.fr, "read", read)
    assert rw.script_result("mxn", OUT) == (0, "line one")


def test_script_result_remote_error_propagates(monkeypatch):
    _fake_read(monkeypatch, error=fr.RemoteError("mxn unreachable: ssh"))
    with pytest.raises(fr.RemoteError):
        rw.script_result("mxn", OUT)


def test_close_script_swallows_herdr_error(hc):
    hc.close_error = real_hc.HerdrError("x", "y")
    assert rw.close_script("mxn", "w1") is None
    assert hc.calls == [("on", "mxn"), ("close_workspace", "w1"), ("off", "mxn")]
