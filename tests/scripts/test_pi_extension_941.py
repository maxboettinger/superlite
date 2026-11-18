import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_pi_extension_node_suite():
    node = shutil.which("node")
    if not node:
        pytest.skip("node missing")
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    m = re.match(r"v(\d+)", out.strip())
    if not m or int(m.group(1)) < 24:
        pytest.skip("node < 24")
    r = subprocess.run(
        [node, "--test", "tests/pi/test_pi_extension.mjs"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
