import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: real Claude Code session, needs SUPERLITE_E2E=1")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SUPERLITE_E2E"):
        return
    skip = pytest.mark.skip(reason="set SUPERLITE_E2E=1")
    for item in items:
        if item.get_closest_marker("e2e"):
            item.add_marker(skip)
