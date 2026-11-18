import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import finding_check as fc  # noqa: E402

Q = "for i in range(n - 1):"


def test_normalize_and_fingerprint():
    assert fc.normalize("  `for i in   range(n - 1):` ") == Q
    a = fc.fingerprint("src/a.py", Q)
    assert a == fc.fingerprint("src/a.py", "  for i in  range(n - 1): ")
    assert len(a) == 10 and a == a.lower() and all(c in "0123456789abcdef" for c in a)
    assert fc.fingerprint("src/a.py", "", "off by one") != fc.fingerprint("src/a.py", "off by one")


def _repo(tmp_path, text, name="src/a.py"):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="")
    return tmp_path


def test_verify_matches_part_of_a_line_whitespace_blind_case_sensitive(tmp_path):
    root = _repo(tmp_path, "x\nfor i in  range(n - 1):\n")
    assert fc.verify(root, {"file": "src/a.py", "line": 2, "quote": "range(n - 1)"})["state"] == "verified"
    assert fc.verify(root, {"file": "src/a.py", "line": 2, "quote": "Range(n - 1)"})["state"] == "unverified"


def test_verify_window_and_moved(tmp_path):
    lines = ["pad"] * 100
    lines[11] = Q
    lines[79] = Q
    root = _repo(tmp_path, "\n".join(lines) + "\n")
    f = {"file": "src/a.py", "line": 14, "quote": Q}
    assert fc.verify(root, f) == {"state": "verified", "line": 12, "reason": ""}
    lines[11] = "pad"
    root = _repo(tmp_path, "\n".join(lines) + "\n")
    assert fc.verify(root, f) == {"state": "moved", "line": 80, "reason": "quote found at line 80"}
    lines[89] = Q
    lines[69] = Q
    root = _repo(tmp_path, "\n".join(lines) + "\n")
    assert fc.verify(root, f)["line"] == 70
    lines = ["pad"] * 100
    root = _repo(tmp_path, "\n".join(lines) + "\n")
    assert fc.verify(root, f) == {"state": "unverified", "line": 14, "reason": "quote not in file"}


def test_verify_reasons(tmp_path):
    root = _repo(tmp_path, "hello world\n")
    v = lambda **k: fc.verify(root, {"file": "src/a.py", "line": 1, **k})["reason"]  # noqa: E731
    assert v() == "no quote"
    assert v(quote="  ") == "no quote"
    assert v(quote="hell") == "quote too short"
    assert v(quote="12345") == "quote too short"
    assert fc.verify(root, {"file": "nope.py", "line": 1, "quote": "hello world"})["reason"] == "file not found"
    big = root / "big.py"
    big.write_bytes(b"a" * (2 * 1024 * 1024 + 1))
    assert fc.verify(root, {"file": "big.py", "line": 1, "quote": "aaaaaaaa"})["reason"] == "file too large"
    assert v(quote="not here") == "quote not in file"


def test_verify_refuses_paths_outside_the_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "out.py"
    outside.write_text("secret line here\n")
    (root / "link.py").symlink_to(outside)
    for f in ("../out.py", str(outside), "link.py"):
        r = fc.verify(root, {"file": f, "line": 1, "quote": "secret line here"})
        assert r["state"] == "unverified" and r["reason"] == "outside root"


def test_verify_reads_crlf_and_bad_utf8(tmp_path):
    p = tmp_path / "a.py"
    p.write_bytes(b"one\r\nbad \xff byte\r\nfor i in range(n - 1):\r\n")
    r = fc.verify(tmp_path, {"file": "a.py", "line": 3, "quote": Q})
    assert r == {"state": "verified", "line": 3, "reason": ""}


def test_ledger_append_load_and_bad_lines(tmp_path):
    assert fc.LEDGER == "findings.jsonl"
    fc.append(tmp_path, {"round": 1, "fp": "a"})
    fc.append(tmp_path, {"round": 2, "fp": "b"})
    with open(tmp_path / fc.LEDGER, "a") as f:
        f.write("garbage\n")
    assert fc.load(tmp_path) == [{"round": 1, "fp": "a"}, {"round": 2, "fp": "b"}]
    assert fc.load(tmp_path / "none") == []
    assert fc.next_round([]) == 1
    assert fc.next_round([{"round": 2}]) == 3


def test_prior_ignores_unverified_rows():
    rows = [{"fp": "ab12", "state": "routed", "n": 1}, {"fp": "ab12", "state": "dismissed", "n": 2},
            {"fp": "ab12", "state": "unverified", "n": 3}, {"fp": "zz", "state": "routed"}]
    assert fc.prior(rows, "ab12")["n"] == 2
    assert fc.prior(rows, "q") is None
    assert fc.prior([{"fp": "ab12", "state": "unverified"}], "ab12") is None


def test_non_string_fields_do_not_raise(tmp_path):
    root = _repo(tmp_path, "hello world\n")
    assert fc.normalize(None) == ""
    assert fc.fingerprint(None, None, None) == fc.fingerprint("", "", "")
    assert fc.fingerprint("a", 12345678) == fc.fingerprint("a", "12345678")
    r = fc.verify(root, {"file": "src/a.py", "line": 1, "quote": ["hello world"]})
    assert r["state"] == "unverified"
    assert fc.verify(root, {"file": "src/a.py", "line": 1, "quote": 12345678})["reason"] == "quote not in file"
