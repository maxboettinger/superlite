"""backlog-main.md names main's release check (#812) and plan's in progress lines (#813)."""
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "backlog-main.md"
S812 = Path(__file__).with_name("fixtures").joinpath("docs_812_813", "s812.txt").read_text(encoding="utf-8").strip()
S813 = Path(__file__).with_name("fixtures").joinpath("docs_812_813", "s813.txt").read_text(encoding="utf-8").strip()
ANCHOR = "a plan with nothing left says `nothing to plan: every issue is already shipped`."


def _step(n):
    return next(ln for ln in DOC.read_text(encoding="utf-8").splitlines() if ln.startswith(f"{n}. "))


def test_main_step8_has_release_check():
    assert _step(8).endswith(" " + S812)
    assert S812 not in _step(1)


def test_main_step2_names_in_progress_lines():
    assert ANCHOR + " " + S813 + " " in _step(2)
