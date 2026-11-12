"""#605: docs/language.md names the forecast's test-cmd.json fields and rules."""
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "language.md"


def test_language_doc_names_the_forecast_inputs():
    text = DOC.read_text(encoding="utf-8")
    para = next(p for p in text.split("\n\n") if p.startswith("**Forecast.**"))
    for phrase in ('"run_min": {"fast": N, "full": N}', '"slots": N', "- tests fast|full", "full-suite lock",
                   "**Kind:** prose", "SUPERLITE_FORECAST_LIVE=0", "under `live`"):
        assert phrase in para, phrase
    assert text.index("**User-level default.**") < text.index("**Forecast.**")
