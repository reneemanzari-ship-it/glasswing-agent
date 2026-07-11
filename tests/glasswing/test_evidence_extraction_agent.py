"""glasswing/agents/evidence_extraction.py: offline fixture replay
(GLASSWING_SPEC.md section 3, Week 4 invariant D). No network, no API
key -- extract_evidence() with fixture_response= never touches
glasswing.agents.base.complete().
"""

from __future__ import annotations

from pathlib import Path

import pytest

from glasswing.agents.evidence_extraction import (
    ExtractionValidationError,
    extract_evidence,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "evidence_extraction"


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_valid_fixture_response_produces_structured_evidence():
    source_text = _read("model_card_lending.md")
    recorded_response = _read("model_card_lending.response.json")

    extracted = extract_evidence(
        source_text, "model_card", fixture_response=recorded_response
    )

    assert extracted.data_sensitivity == ["financial", "pii"]
    assert "human oversight review committee" in extracted.existing_controls
    assert extracted.extraction_confidence == 0.88
    assert extracted.completeness_score == 0.85


def test_malformed_response_raises_extraction_validation_error():
    source_text = _read("model_card_lending.md")
    malformed_response = _read("malformed.response.json")

    with pytest.raises(ExtractionValidationError):
        extract_evidence(source_text, "model_card", fixture_response=malformed_response)


def test_non_json_response_raises_extraction_validation_error():
    with pytest.raises(ExtractionValidationError):
        extract_evidence(
            "irrelevant source text",
            "model_card",
            fixture_response="this is not JSON at all {{{",
        )


def test_low_confidence_fixture_is_still_schema_valid():
    """The low-confidence fixture is schema-VALID -- it's the runner
    (glasswing/intake/extraction_runner.py), not the agent, that routes
    it to human review based on the confidence/completeness threshold.
    The agent's only job is faithful parse+validate."""
    low_confidence_response = _read("low_confidence.response.json")

    extracted = extract_evidence(
        "irrelevant", "model_card", fixture_response=low_confidence_response
    )
    assert extracted.extraction_confidence == 0.5
    assert extracted.completeness_score == 0.4
