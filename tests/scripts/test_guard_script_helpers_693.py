"""#693 T2: guard_files.script_text, script_lang and session_start."""
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "skills" / "subagent-driven-development" / "scripts"))
import guard_files as gf  # noqa: E402


def _w(tmp_path, data, name="f"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_script_text_reads_and_limits(tmp_path):
    assert gf.script_text(_w(tmp_path, b"wc -l src/a.py\n")) == ("wc -l src/a.py\n", None)
    assert gf.script_text(_w(tmp_path, b"a" * 65536)) == ("a" * 65536, None)
    assert gf.script_text(_w(tmp_path, b"a" * 65537)) == (None, "over 65536 characters")
    three = "€" * 30000
    assert gf.script_text(_w(tmp_path, three.encode())) == (three, None)
    assert gf.script_text(_w(tmp_path, b"a" * 11), limit=10) == (None, "over 10 characters")


def test_script_text_binary_and_errors(tmp_path):
    for magic in (b"\x7fELF\x02\x01", b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe",
                  b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"MZ\x90\x00"):
        assert gf.script_text(_w(tmp_path, magic)) == (None, "binary")
    assert gf.script_text(_w(tmp_path, b"echo a\x00b")) == (None, "binary")
    assert gf.script_text(_w(tmp_path, b"\xff\xfe x")) == (None, "not UTF-8 text")
    text, why = gf.script_text(str(tmp_path / "missing"))
    assert text is None and why.startswith("unreadable: ")
    text, why = gf.script_text(str(tmp_path))
    assert text is None and why.startswith("unreadable: ")
    real = _w(tmp_path, b"echo hi\n", "real.sh")
    os.symlink(real, tmp_path / "link.sh")
    assert gf.script_text(str(tmp_path / "link.sh")) == ("echo hi\n", None)


@pytest.mark.parametrize("text,want", [
    ("#!/bin/bash -eu\n", ("sh", "bash")),
    ("#!/bin/sh\n", ("sh", "sh")),
    ("#!/usr/bin/env zsh\n", ("sh", "zsh")),
    ("#!/usr/bin/env python3\n", ("py", "python3")),
    ("#!/usr/local/bin/python3.12\n", ("py", "python3.12")),
    ("#!/usr/bin/env -S uv run --script\nprint(1)\n", ("py", "uv")),
    ("#!/usr/bin/env node\n", ("js", "node")),
    ("#!/usr/bin/env bun\n", ("js", "bun")),
    ("#!/usr/bin/perl -w\n", ("pl", "perl")),
    ("#!/usr/bin/env ruby\n", ("rb", "ruby")),
    ("#!/usr/bin/env php\n", ("php", "php")),
    ("#!/usr/bin/env -i FOO=1 python3\n", ("py", "python3")),
    ("#!/usr/bin/env -u FOO python3\n", ("py", "python3")),
    ("#!/usr/bin/env swift\nprint(1)\n", (None, "swift")),
    ("#!\n", (None, "")),
    ("echo hi\n", ("sh", "sh")),
    ("", ("sh", "sh")),
])
def test_script_lang_cases(text, want):
    assert gf.script_lang(text) == want


def _t(tmp_path, lines):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_session_start_cases(tmp_path):
    assert gf.session_start(None) is None
    assert gf.session_start(str(tmp_path / "missing.jsonl")) is None
    p = _t(tmp_path, [json.dumps({"type": "user", "timestamp": "2020-11-13T02:41:07.427Z"})])
    assert gf.session_start(str(p)) == pytest.approx(1605235267.427)
    p = _t(tmp_path, [json.dumps({"type": "x"}), json.dumps({"timestamp": "2020-11-13T02:41:07Z"})])
    assert gf.session_start(str(p)) == pytest.approx(1605235267.0)
    p = _t(tmp_path, ["not json", json.dumps({"timestamp": "2020-11-13T04:41:07+02:00"})])
    assert gf.session_start(str(p)) == pytest.approx(1605235267.0)
    p = _t(tmp_path, [json.dumps({"type": "x"})])
    if hasattr(os.stat(p), "st_birthtime"):
        assert gf.session_start(str(p)) == pytest.approx(os.stat(p).st_birthtime)
    else:
        assert gf.session_start(str(p)) is None
