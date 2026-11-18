"""Every prime kind carries the project corrections once, after the standing note; finish names the file."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS, run
from test_prime_standing_note_738 import kinds, lead
from test_slim_prime import make

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import build_prime  # noqa: E402
import corrections  # noqa: E402

HEAD = "## Corrections (binding, from the user)"
FINISH = SCRIPTS / "finish.py"


def put(root, *items):
    for it in items:
        assert corrections.add(root, it, commit=False)[0] == 0


def test_slim_prime_has_corrections_after_the_standing_note(tmp_path):
    plan = make(tmp_path)
    sd = lead(tmp_path, f"# Lead\n{bb.NOTE_HEAD}\n    first rule of main\n")
    put(tmp_path, "Use uv, never pip")
    text = build_prime.build_slim(str(plan), sd).decode("utf-8")
    assert text.index("## Standing note") < text.index(HEAD) < text.index("## Background")
    assert "- Use uv, never pip" in text


def test_mini_and_full_primes_have_the_section(tmp_path):
    plan = make(tmp_path)
    sd = lead(tmp_path, f"# Lead\n{bb.NOTE_HEAD}\n    first rule of main\n")
    put(tmp_path, "Use uv, never pip")
    for data in kinds(plan, sd):
        text = data.decode("utf-8")
        assert text.count(HEAD) == 1
        assert text.index("## Standing note") < text.index(HEAD)


def test_corrections_follow_read_first_when_there_is_no_note(tmp_path):
    plan = make(tmp_path)
    put(tmp_path, "Use uv, never pip")
    for data in kinds(plan, tmp_path / ".superlite"):
        text = data.decode("utf-8")
        assert text.count(HEAD) == 1 and text.index("Rules:") < text.index(HEAD)


def test_prime_without_the_file_has_no_section(tmp_path):
    plan = make(tmp_path)
    for data in kinds(plan, tmp_path / ".superlite"):
        assert b"## Corrections" not in data


def test_prime_survives_a_corrections_error(tmp_path, monkeypatch):
    plan = make(tmp_path)
    put(tmp_path, "Use uv, never pip")

    def boom(_root):
        raise RuntimeError("boom")

    monkeypatch.setattr(corrections, "section", boom)
    for data in kinds(plan, tmp_path / ".superlite"):
        assert data and b"## Corrections" not in data


def summary(tmp_path):
    led = tmp_path / "progress.md"
    led.write_text("", encoding="utf-8")
    return run(FINISH, "--ledger", led, "--log", tmp_path / "incidents.jsonl", cwd=tmp_path).out


def test_finish_summary_names_corrections(tmp_path):
    assert "corrections: 0 lines, 0/2048 bytes" in summary(tmp_path)
    put(tmp_path, "Use uv, never pip", "German UI strings")
    n = (tmp_path / corrections.FILE).stat().st_size
    assert (f"corrections: 2 lines, {n}/2048 bytes (docs/superlite/corrections.md); a user correction from this run "
            'that later runs need: sl corrections add "<rule>"') in summary(tmp_path)
