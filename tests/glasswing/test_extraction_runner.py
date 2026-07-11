"""glasswing/intake/extraction_runner.py: end-to-end extraction ->
classification -> EVIDENCE_COMPLETE -> CLASSIFIED (GLASSWING_SPEC.md
section 3, Week 4 acceptance criteria).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from glasswing.core.evidence import EvidenceSourceType
from glasswing.core.lifecycle import LifecycleState
from glasswing.intake.extraction_runner import (
    HumanReviewRequiredError,
    run_extraction_and_classification,
)
from glasswing.services import audit, portfolio
from glasswing.storage.models import AuditEntryRow, EngagementRow

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "evidence_extraction"


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _make_engagement(session) -> EngagementRow:
    engagement = EngagementRow(
        client_name="Fixture Corp",
        sector="fintech",
        jurisdictions=["US-CO"],
        data_dir="",
    )
    session.add(engagement)
    session.flush()
    engagement.data_dir = f"data/engagements/{engagement.id}"
    audit.append_genesis(
        session, engagement_id=engagement.id, payload={"client_name": "Fixture Corp"}
    )
    return engagement


def _make_initiative_in_evidence_complete(session, engagement):
    initiative = portfolio.create_initiative(
        session,
        engagement_id=engagement.id,
        name="FixtureCorp Lending Pre-Approval Assistant",
        description="Recommends credit pre-approval tiers based on credit history.",
        modality="classical_ml",
        autonomy_level="recommend_only",
        hitl_planned="yes",
        jurisdictions=["US-CO"],
    )
    portfolio.transition(
        session,
        initiative=initiative,
        new_state=LifecycleState.EVIDENCE_COMPLETE,
        actor="tester",
        reason="Questionnaire completed for test setup.",
    )
    return initiative


def test_valid_extraction_classifies_via_the_engine_and_moves_to_classified(session):
    """The core Week 4 acceptance criterion: the tier comes from the
    ENGINE, not the LLM -- classify_initiative()'s deterministic keyword
    logic on a credit-scenario description always assigns EU AI Act
    high_risk/financial_lending, regardless of what the (synthetic, fixed)
    extraction fixture says. Nothing in the extraction response could
    have supplied that tier -- ExtractedEvidence has no field for it
    (see test_agent_boundary.py)."""
    engagement = _make_engagement(session)
    initiative = _make_initiative_in_evidence_complete(session, engagement)
    session.commit()

    source_text = _read("model_card_lending.md")
    recorded_response = _read("model_card_lending.response.json")

    risk_profile_row, updated_initiative = run_extraction_and_classification(
        session,
        initiative=initiative,
        source_text=source_text,
        source_type=EvidenceSourceType.MODEL_CARD,
        actor="tester",
        fixture_response=recorded_response,
    )
    session.commit()

    assert updated_initiative.lifecycle_state == LifecycleState.CLASSIFIED.value
    assert risk_profile_row.overall_tier == "high"
    assert risk_profile_row.per_framework_results["eu_ai_act"]["tier"] == "high_risk"
    assert (
        risk_profile_row.per_framework_results["colorado_sb_205"]["high_risk_category"]
        == "financial_lending"
    )
    assert risk_profile_row.engine_version
    assert risk_profile_row.framework_versions.get("eu_ai_act")


def test_evidence_complete_to_classified_writes_audit_entry_before_mutation(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative_in_evidence_complete(session, engagement)
    session.commit()

    run_extraction_and_classification(
        session,
        initiative=initiative,
        source_text=_read("model_card_lending.md"),
        source_type=EvidenceSourceType.MODEL_CARD,
        actor="tester",
        fixture_response=_read("model_card_lending.response.json"),
    )
    session.commit()

    entries = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq)
        .all()
    )
    event_types = [e.event_type for e in entries]
    assert event_types == [
        "engagement_created",
        "initiative_created",
        "state_transitioned",  # DRAFT -> EVIDENCE_COMPLETE (test setup)
        "evidence_recorded",  # extraction's evidence
        "risk_profile_recorded",  # the engine's output, persisted
        "state_transitioned",  # EVIDENCE_COMPLETE -> CLASSIFIED
    ]
    assert audit.verify_chain(session, engagement.id).valid


def test_malformed_extraction_routes_to_human_review(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative_in_evidence_complete(session, engagement)
    session.commit()

    with pytest.raises(HumanReviewRequiredError):
        run_extraction_and_classification(
            session,
            initiative=initiative,
            source_text=_read("model_card_lending.md"),
            source_type=EvidenceSourceType.MODEL_CARD,
            actor="tester",
            fixture_response=_read("malformed.response.json"),
        )
    session.commit()

    assert initiative.lifecycle_state == LifecycleState.EVIDENCE_COMPLETE.value
    entries = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq)
        .all()
    )
    assert entries[-1].event_type == "human_review_requested"
    assert audit.verify_chain(session, engagement.id).valid


def test_low_confidence_extraction_routes_to_human_review(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative_in_evidence_complete(session, engagement)
    session.commit()

    with pytest.raises(HumanReviewRequiredError, match="below threshold"):
        run_extraction_and_classification(
            session,
            initiative=initiative,
            source_text=_read("model_card_lending.md"),
            source_type=EvidenceSourceType.MODEL_CARD,
            actor="tester",
            fixture_response=_read("low_confidence.response.json"),
        )
    session.commit()

    assert initiative.lifecycle_state == LifecycleState.EVIDENCE_COMPLETE.value
    entries = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq)
        .all()
    )
    assert entries[-1].event_type == "human_review_requested"


def test_no_risk_profile_or_transition_on_human_review_path(session):
    from glasswing.storage.models import RiskProfileRow

    engagement = _make_engagement(session)
    initiative = _make_initiative_in_evidence_complete(session, engagement)
    session.commit()

    with pytest.raises(HumanReviewRequiredError):
        run_extraction_and_classification(
            session,
            initiative=initiative,
            source_text=_read("model_card_lending.md"),
            source_type=EvidenceSourceType.MODEL_CARD,
            actor="tester",
            fixture_response=_read("malformed.response.json"),
        )

    assert (
        session.query(RiskProfileRow).filter_by(initiative_id=initiative.id).count()
        == 0
    )
