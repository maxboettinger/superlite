import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "probes"))
from pack import file  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                                reason="permission bits not enforced")


def _probe(name):
    return next(p for p in file.PROBES if p["name"] == name)


def test_both_unreadable_probes_set_up(tmp_path):
    ctx = SimpleNamespace(tmp=tmp_path)
    a = _probe("call_unreadable")["make"](None, ctx)
    args, extra = _probe("arg_unreadable")["make"](None, ctx)
    try:
        assert isinstance(a, str) and extra == "" and len(args) == 1 and a != args[0]
        for f in (a, args[0]):
            assert stat.S_IMODE(os.stat(f).st_mode) == 0
    finally:
        for f in (a, *args):
            os.chmod(f, 0o600)


def test_unreadable_twice_same_probe(tmp_path):
    ctx = SimpleNamespace(tmp=tmp_path)
    a, b = file._unreadable(None, ctx), file._unreadable(None, ctx)
    try:
        assert a != b and os.path.exists(a) and os.path.exists(b)
    finally:
        os.chmod(a, 0o600)
        os.chmod(b, 0o600)
