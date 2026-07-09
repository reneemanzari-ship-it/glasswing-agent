"""GLASSWING_SPEC.md / CLAUDE.md: "Tests run offline. Set GLASSWING_OFFLINE=1
in CI and use pytest-socket to block network."

Ties the two together so CI only needs to set the env var — no separate
--disable-socket flag to remember.
"""

from __future__ import annotations

import os

import pytest_socket


def pytest_runtest_setup() -> None:
    if os.environ.get("GLASSWING_OFFLINE") == "1":
        pytest_socket.disable_socket()
