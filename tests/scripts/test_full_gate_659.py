"""admission_for: machine.json "admission" per toolchain (#659)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import full_gate  # noqa: E402

SHX = ["sh", "-c", 'exec "$@"', "gate"]
LOCKTAIL = "; running under the full-suite lock"


def machine(home, data):
    Path(home).mkdir(parents=True, exist_ok=True)
    (Path(home) / "machine.json").write_text(json.dumps(data), encoding="utf-8")


def test_self_entry(tmp_path):
    machine(tmp_path, {"admission": {"xcode": "self", "default": SHX}})
    assert full_gate.admission_for("xcode", tmp_path) == full_gate.Admission(
        "self", None, 'full run admitted by the machine itself (machine.json "admission" for xcode: "self"); no full-suite lock, no admission command', None)


def test_default_command(tmp_path):
    machine(tmp_path, {"admission": {"xcode": "self", "default": SHX}})
    assert full_gate.admission_for("python", tmp_path) == full_gate.Admission(
        "command", SHX, 'full run through the admission command sh (machine.json "admission" "default" for python); no full-suite lock', None)


def test_no_entry_lock(tmp_path):
    machine(tmp_path, {"admission": {"python": "lock"}})
    assert full_gate.admission_for("shell", tmp_path) == full_gate.Admission(
        "lock", None, 'full run under the shell full-suite lock (machine.json "admission" has no "shell" or "default" entry)', None)


def test_bad_entry_warns(tmp_path):
    machine(tmp_path, {"admission": {"python": 7}})
    assert full_gate.admission_for("python", tmp_path) == full_gate.Admission(
        "lock", None, None, 'machine.json "admission" for python must be a non-empty list of strings, "self" or "lock"' + LOCKTAIL)


def test_list_form_same_for_every_toolchain(tmp_path):
    machine(tmp_path, {"admission": ["sh"]})
    for tc in ("python", "xcode", "shell"):
        a = full_gate.admission_for(tc, tmp_path)
        assert a.mode == "command" and a.argv == ["sh"] and a.warning is None
        assert a.note == 'full run through the admission command sh (machine.json "admission"); no full-suite lock'


def test_bad_entry_of_other_toolchain_is_silent(tmp_path):
    machine(tmp_path, {"admission": {"xcode": 5, "default": "lock"}})
    a = full_gate.admission_for("python", tmp_path)
    assert a.mode == "lock" and a.warning is None


def test_default_entry_missing_command(tmp_path):
    machine(tmp_path, {"admission": {"default": ["/no/such/gate"]}})
    a = full_gate.admission_for("xcode", tmp_path)
    assert a.mode == "lock" and a.note is None
    assert a.warning == 'admission command /no/such/gate not found (machine.json "admission" "default" for xcode)' + LOCKTAIL


def test_string_value_warns(tmp_path):
    machine(tmp_path, {"admission": "self"})
    a = full_gate.admission_for("python", tmp_path)
    assert a.mode == "lock" and a.warning == 'machine.json "admission" must be a non-empty list of strings or an object keyed by toolchain' + LOCKTAIL


def test_unset_is_none(tmp_path):
    none = full_gate.Admission(None, None, None, None)
    assert full_gate.admission_for("python", tmp_path) == none
    machine(tmp_path, {})
    assert full_gate.admission_for("python", tmp_path) == none
    machine(tmp_path, {"floor": 10})
    assert full_gate.admission_for("python", tmp_path) == none


def test_lock_entry(tmp_path):
    machine(tmp_path, {"admission": {"xcode": "lock"}})
    a = full_gate.admission_for("xcode", tmp_path)
    assert a.mode == "lock" and a.warning is None
    assert a.note == 'full run under the xcode full-suite lock (machine.json "admission" for xcode: "lock")'


def test_self_from_default(tmp_path):
    machine(tmp_path, {"admission": {"default": "self"}})
    a = full_gate.admission_for("shell", tmp_path)
    assert a.mode == "self" and 'machine.json "admission" "default" for shell: "self"' in a.note


def test_empty_object_is_no_entry(tmp_path):
    machine(tmp_path, {"admission": {}})
    a = full_gate.admission_for("python", tmp_path)
    assert a.mode == "lock" and "has no" in a.note


def test_admission_command_wrapper(tmp_path):
    machine(tmp_path, {"admission": {"python": SHX, "xcode": "self"}})
    assert full_gate.admission_command(tmp_path, "python") == (SHX, None)
    assert full_gate.admission_command(tmp_path, "xcode") == (None, None)
