"""glasswing/intake/questionnaire_runner.py: end-to-end questionnaire
intake against real storage (GLASSWING_SPEC.md section 3, Week 3
acceptance criteria).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from glasswing.core.lifecycle import LifecycleState
from glasswing.engines.questionnaire import load_questionnaire
from glasswing.intake.questionnaire_runner import (
    HumanReviewRequiredError,
    submit_questionnaire,
)
from glasswing.services import audit
from glasswing.storage.models import AuditEntryRow, EngagementRow

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "questionnaires"
QUESTIONNAIRE_PATH = FIXTURES_DIR / "sample_intake_v0.yaml"


def _load_answers(filename: str) -> dict:
    return yaml.safe_load((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


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


def test_valid_submission_produces_initiative_and_evidence_and_transitions(session):
    engagement = _make_engagement(session)
    session.commit()
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers.yaml")

    initiative_row, evidence_row = submit_questionnaire(
        session,
        engagement_id=engagement.id,
        questionnaire=questionnaire,
        answers=answers,
        actor="tester",
    )
    session.commit()

    assert initiative_row.name == "FixtureCorp Lending Assistant"
    assert initiative_row.lifecycle_state == LifecycleState.EVIDENCE_COMPLETE.value
    assert evidence_row.source_type == "questionnaire"
    assert evidence_row.content["system_type_category"] == "lending"
    assert evidence_row.initiative_id == initiative_row.id


def test_draft_to_evidence_complete_transition_writes_its_audit_entry(session):
    """GLASSWING_SPEC.md section 3, Week 3 acceptance: 'the DRAFT ->
    EVIDENCE_COMPLETE transition writes its audit entry before the
    mutation'. Asserts the entry exists and the chain still verifies."""
    engagement = _make_engagement(session)
    session.commit()
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers.yaml")

    submit_questionnaire(
        session,
        engagement_id=engagement.id,
        questionnaire=questionnaire,
        answers=answers,
        actor="tester",
    )
    session.commit()

    entries = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq)
        .all()
    )
    event_types = [e.event_type for e in entries]
    # engagement_created, initiative_created, evidence_recorded, state_transitioned
    assert event_types == [
        "engagement_created",
        "initiative_created",
        "evidence_recorded",
        "state_transitioned",
    ]
    assert audit.verify_chain(session, engagement.id).valid


def test_invalid_answers_route_to_human_review_and_log_it(session):
    """GLASSWING_SPEC.md section 3, Week 3 acceptance: an answers file
    failing schema validation routes to human review and logs
    HUMAN_REVIEW_REQUESTED -- never a crash, never a silent continue."""
    engagement = _make_engagement(session)
    session.commit()
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers_invalid.yaml")

    with pytest.raises(HumanReviewRequiredError, match="q_hitl"):
        submit_questionnaire(
            session,
            engagement_id=engagement.id,
            questionnaire=questionnaire,
            answers=answers,
            actor="tester",
        )
    session.commit()

    entries = (
        session.query(AuditEntryRow)
        .filter_by(engagement_id=engagement.id)
        .order_by(AuditEntryRow.seq)
        .all()
    )
    assert [e.event_type for e in entries] == [
        "engagement_created",
        "human_review_requested",
    ]
    assert audit.verify_chain(session, engagement.id).valid


def test_invalid_answers_do_not_create_an_initiative(session):
    engagement = _make_engagement(session)
    session.commit()
    questionnaire = load_questionnaire(QUESTIONNAIRE_PATH)
    answers = _load_answers("sample_answers_invalid.yaml")

    with pytest.raises(HumanReviewRequiredError):
        submit_questionnaire(
            session,
            engagement_id=engagement.id,
            questionnaire=questionnaire,
            answers=answers,
            actor="tester",
        )

    from glasswing.storage.models import InitiativeRow

    assert (
        session.query(InitiativeRow).filter_by(engagement_id=engagement.id).count()
        == 0
    )
