"""#590: commands/backlog.md names the plan sync, run end, handover and main's catch-up list."""
from pathlib import Path

TEXT = (Path(__file__).resolve().parents[2] / "commands/backlog.md").read_text()


def test_names_plan_sync_and_run_end():
    for s in ("sync:", "run end:", "sl fleet off"):
        assert s in TEXT


def test_hand_over_and_closing_report():
    for s in ("Hand over while a lead runs", "WAITING", "other repository"):
        assert s in TEXT


def test_catch_up_items():
    for s in ("fast path", "already shipped:", "check:", "not found:", "unskip", "reset B",
              "--discard", "--help", "offer:", '"by"', "no-change", "Unverified:",
              "Kind: design", "Refs #N", "ship B notes", "ship B done"):
        assert s in TEXT, s
