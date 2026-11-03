"""history.detect_language: each marker file or bundle suffix maps to its stack (#89: Swift rows were `unknown`)."""
from __future__ import annotations

import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import history  # noqa: E402


@pytest.mark.parametrize("marker, is_dir, lang", [
    ("Package.swift", False, "swift"),
    ("App.xcodeproj", True, "swift"),
    ("App.xcworkspace", True, "swift"),
    ("pyproject.toml", False, "python"),
    ("App.csproj", False, "csharp"),
])
def test_marker_maps_to_language(tmp_path, marker, is_dir, lang):
    target = tmp_path / marker
    target.mkdir() if is_dir else target.write_text("", encoding="utf-8")
    assert history.detect_language(tmp_path) == lang


def test_xcode_app_with_local_packages_is_swift(tmp_path):
    """The pix-app layout: an .xcodeproj at the root next to a Packages/ folder, no Package.swift at the root."""
    (tmp_path / "pix-app.xcodeproj").mkdir()
    (tmp_path / "Packages" / "Core").mkdir(parents=True)
    (tmp_path / "Packages" / "Core" / "Package.swift").write_text("", encoding="utf-8")
    assert history.detect_language(tmp_path) == "swift"


def test_no_marker_is_unknown(tmp_path):
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    assert history.detect_language(tmp_path) == "unknown"
