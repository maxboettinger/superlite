"""Agents offer `run_tests --affected --task Tn` next to the `--fast PATHS` run (#899)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_haiku_offers_affected():
    text = (ROOT / "agents" / "implementer-haiku.md").read_text(encoding="utf-8")
    assert (
        "`<abs sl> run_tests --fast PATHS --task Tn --background` (or `<abs sl> run_tests --affected --task Tn --background`: "
        "run_tests picks the tests your change touches; when no test covers it, it exits 2 naming the files, so write that test), "
        "then run the `wait:` line"
    ) in text


def test_fixers_offer_affected():
    for name in ("fixer-sonnet.md", "fixer-sonnet-high.md", "fixer-opus.md"):
        text = (ROOT / "agents" / name).read_text(encoding="utf-8")
        assert (
            "`<abs sl> run_tests --fast <touched test files> --background` (or `<abs sl> run_tests --affected --task Tn --background` "
            "when your brief names the task Tn: run_tests picks the tests your change touches), then run the `wait:` line"
        ) in text, name


def test_reviewer_offers_affected():
    text = (ROOT / "agents" / "package-reviewer.md").read_text(encoding="utf-8")
    assert (
        "`<abs sl> run_tests --fast PATHS --background` (or `<abs sl> run_tests --affected --task Tn --background` "
        "for the task under review: run_tests picks the tests its change touches), then run the `wait:` line"
    ) in text
