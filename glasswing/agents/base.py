"""Isolates every model-SDK-specific type behind one module
(GLASSWING_SPEC.md section 2.1: "the SDK is young and its API will move
... isolate every SDK type behind agents/base.py"). Every agent module
imports its model client from here; nothing outside this file imports
`anthropic` (or any future SDK) directly.

DECISIONS.md D-024: uses the base `anthropic` Python SDK, not
`claude-agent-sdk`. The latter is built for interactive, multi-turn
agentic tool-use loops (the Claude Code harness shape); the Evidence
Extraction Agent's actual job -- one-shot structured extraction from a
block of text -- is a single messages.create() call, not an agentic
loop. Isolating that call behind this module gives the same swap-safety
GLASSWING_SPEC.md asks for without pulling in a heavier dependency this
agent doesn't use.

CLAUDE.md invariant #1 boundary: this module makes model calls. It must
never be imported by glasswing/engines/ or glasswing/services/ -- see
tests/glasswing/test_agent_boundary.py, which asserts that structurally.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL_ID = "claude-sonnet-4-5-20250115"


class OfflineModeError(RuntimeError):
    """Raised when a live model call is attempted while offline (no
    ANTHROPIC_API_KEY, or GLASSWING_OFFLINE=1). Callers must branch to a
    recorded-fixture replay before reaching this call, not catch this as
    a fallback path -- CLAUDE.md: "Tests run offline ... Any test that
    needs the network is wrong; fix the test, not the flag."
    """


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model_id: str


def is_offline() -> bool:
    return os.environ.get("GLASSWING_OFFLINE") == "1" or not os.environ.get(
        "ANTHROPIC_API_KEY"
    )


def complete(
    *, system_prompt: str, user_content: str, model_id: str = DEFAULT_MODEL_ID
) -> ModelResponse:
    """Makes a single live completion call. Raises OfflineModeError under
    GLASSWING_OFFLINE=1 or with no API key configured -- this is a manual,
    operator-initiated path only (docs/live_runs.md), never something CI
    or the offline test suite reaches.
    """
    if is_offline():
        raise OfflineModeError(
            "Cannot make a live model call: GLASSWING_OFFLINE=1 or no "
            "ANTHROPIC_API_KEY configured. Live runs are manual and logged "
            "in docs/live_runs.md, never automatic."
        )

    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model_id,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return ModelResponse(text=text, model_id=model_id)
