from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")


def rows(*names):
    return "\n".join(l for l in DOC.splitlines() if any(l.startswith(f"| `{n}` |") for n in names))


def test_run_tests_and_testcmd_rows():
    r = rows("run_tests", "testcmd")
    for s in ("--record", "--scope", "test-summary-full.json", "test-cmd.seeded", "behind", "file::name"):
        assert s in r, s


def test_review_finish_predict_and_prime_rows():
    assert "End" in rows("pt_review") and "Cut" in rows("pt_review")
    assert "committed" in rows("finish")
    for s in ("predict_live", "SUPERLITE_FORECAST_LIVE"):
        assert s in rows("predict"), s
    assert "## Running the app" in rows("build_prime")
    assert rows("gui_session")
