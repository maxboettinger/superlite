"""Packet trims (#1085): diff stat rows without padding or bars; the Cut line names each section-8 file once."""
from __future__ import annotations

import sys

from test_packet_cut_code_819 import change, packet, proj  # noqa: F401
from test_packet_inline import SCRIPT

sys.path.insert(0, str(SCRIPT.parent))
import pt_review  # noqa: E402


def test_stat_rows_carry_counts_without_padding_or_bars():
    rows = {"a.py": (3, 1), "deep/dir/long_name.py": (120, 0), "img.png": None}
    assert pt_review._format_stat(rows).splitlines() == [
        " a.py | +3 -1",
        " deep/dir/long_name.py | +120 -0",
        " img.png | Bin",
        " 3 files changed, 123 insertions(+), 1 deletion(-)",
    ]
    assert pt_review._format_stat({}) == ""


def test_head_cut_entries_merge_truncated_and_skip_must_read():
    cuts = ["section 0b: earlier rounds cut at 4000 of 9000 characters", "section 8 left out: a.py, b.md",
            "section 8 truncated: src/big.py", "section 8 truncated: docs/x.md", "section 8 truncated: tests/test_big.py"]
    assert pt_review.head_cut_entries(cuts, ["src/big.py", "a.py"]) == [
        "section 0b: earlier rounds cut at 4000 of 9000 characters", "section 8 left out: a.py, b.md",
        "section 8 truncated: docs/x.md, tests/test_big.py"]
    assert pt_review.head_cut_entries(["section 8 truncated: src/big.py"], ["src/big.py"]) == []
    assert pt_review.head_cut_entries(cuts[:2], []) == cuts[:2]


def test_packet_head_names_a_cut_code_file_once(proj):  # noqa: F811
    change(proj, ["src/big.py"], 400)
    r, t = packet(proj, "--max-tokens", "1500")
    lines = t.splitlines()
    assert "Read in full before your verdict (section 8 cut their diff; one Read each): src/big.py" in lines
    assert not [x for x in lines if x.startswith("Cut to fit the size cap:") and "src/big.py" in x]
    assert any(x.startswith("cut: section 8 truncated: ") and "src/big.py" in x for x in r.stdout.splitlines())
