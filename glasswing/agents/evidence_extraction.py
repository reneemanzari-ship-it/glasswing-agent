"""Evidence Extraction Agent (GLASSWING_SPEC.md section 2.4, Week 4).

Extracts structured evidence from an unstructured source (a model card,
a vendor security document, a freeform description) into ExtractedEvidence
-- a Pydantic model that structurally cannot carry a risk tier,
classification, or control prescription (see
glasswing/core/extracted_evidence.py and
tests/glasswing/test_agent_boundary.py). This agent's output is INPUT to
glasswing/engines/classification.py, which is the only code path
permitted to assign a tier -- CLAUDE.md invariant #1.

Deterministic offline mode: pass `fixture_response` (a recorded model
response, as JSON text) to replay it through the exact same parse+
validate path a live response would go through, with zero network
regardless of GLASSWING_OFFLINE. This is how the offline test suite
exercises this function. Live mode (fixture_response=None) calls
glasswing.agents.base.complete(), which itself refuses to run under
GLASSWING_OFFLINE=1 or with no ANTHROPIC_API_KEY configured -- live runs
are manual, operator-initiated, and logged in docs/live_runs.md, never
CI-gated.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from glasswing.agents import base
from glasswing.core.extracted_evidence import ExtractedEvidence

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extraction" / "v1.md"


class ExtractionValidationError(ValueError):
    """The model's response is not valid JSON, or doesn't validate
    against ExtractedEvidence. Callers route this to human review; it is
    never allowed to propagate as an unhandled crash, and the invalid
    payload is never passed downstream unvalidated."""


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_evidence(
    source_text: str,
    source_type_label: str,
    *,
    fixture_response: str | None = None,
) -> ExtractedEvidence:
    """Extracts structured evidence from `source_text`.

    `fixture_response`, if given, is a recorded model response (JSON
    text) parsed directly instead of making a live call -- this is the
    deterministic replay path the offline test suite uses.
    """
    if fixture_response is not None:
        raw_text = fixture_response
    else:
        response = base.complete(
            system_prompt=_load_prompt(),
            user_content=f"Source type: {source_type_label}\n\n{source_text}",
        )
        raw_text = response.text

    try:
        payload = json.loads(raw_text)
        return ExtractedEvidence.model_validate(payload)
    except (json.JSONDecodeError, PydanticValidationError) as exc:
        raise ExtractionValidationError(
            f"Extraction response failed schema validation: {exc}"
        ) from exc
