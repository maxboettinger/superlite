import json
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"


def _ledger(tmp_path):
    p = tmp_path / "progress.md"
    p.write_bytes(b"Ruling: keep \xff byte\nother line \xff\n")
    return p


def test_finish_ledger_ff_byte(tmp_path):
    p = _ledger(tmp_path)
    r = subprocess.run([sys.executable, str(S / "finish.py"), "--ledger", str(p), "--log", str(tmp_path / "i.jsonl"),
                        "--plan", str(tmp_path / "plan.md")], capture_output=True)
    assert r.returncode == 0, r.stderr
    assert "keep � byte" in r.stdout.decode("utf-8")


def test_finish_second_reader_ff_byte(tmp_path):
    sys.path.insert(0, str(S))
    import finish
    p = _ledger(tmp_path)
    p.write_bytes(b"unblocked: T1 12:00:00 \xff\n")
    lint = tmp_path / "lint-log.jsonl"
    lint.write_text(json.dumps({"time": "12:00:00", "stable": ["T1"]}) + "\n", encoding="utf-8")
    finish.unblocked_report(str(p), str(lint))  # must not raise


def test_incident_add_surrogate_context(tmp_path):
    log = tmp_path / "inc.jsonl"
    argv = [sys.executable.encode(), str(S / "incident.py").encode(), b"add", b"--file", b"f\xff.py",
            b"--line", b"1", b"--context", b"bad \xff byte", b"--log", str(log).encode()]
    r = subprocess.run(argv, capture_output=True)
    assert r.returncode == 0, r.stderr
    text = log.read_bytes().decode("utf-8")
    e = json.loads(text)
    assert "�" in e["context"] and "�" in e["file"]
