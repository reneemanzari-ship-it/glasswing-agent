"""glasswing/agents/base.py: offline-mode guard (GLASSWING_SPEC.md
section 3, Week 4 invariant D). A live call must be refused under
GLASSWING_OFFLINE=1 or with no ANTHROPIC_API_KEY -- never silently
attempted, never caught-and-ignored.
"""

from __future__ import annotations

import pytest

from glasswing.agents import base


def test_is_offline_true_when_env_var_set(monkeypatch):
    monkeypatch.setenv("GLASSWING_OFFLINE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-test")
    assert base.is_offline() is True


def test_is_offline_true_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GLASSWING_OFFLINE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert base.is_offline() is True


def test_complete_raises_offline_mode_error_under_glasswing_offline(monkeypatch):
    monkeypatch.setenv("GLASSWING_OFFLINE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-for-test")

    with pytest.raises(base.OfflineModeError):
        base.complete(system_prompt="irrelevant", user_content="irrelevant")


def test_complete_raises_offline_mode_error_with_no_api_key(monkeypatch):
    monkeypatch.delenv("GLASSWING_OFFLINE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(base.OfflineModeError):
        base.complete(system_prompt="irrelevant", user_content="irrelevant")
