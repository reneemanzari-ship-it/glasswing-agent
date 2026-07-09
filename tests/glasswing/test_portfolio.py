"""services/portfolio.py: lifecycle state machine through REJECTED.

GLASSWING_SPEC.md section 3, Week 1 acceptance: "Every state-machine
transition test asserts a matching audit entry exists."
"""

from __future__ import annotations

import pytest

from glasswing.core.lifecycle import LifecycleState
from glasswing.services import audit, portfolio
from glasswing.storage.models import (
    ApprovalDecisionRow,
    AuditEntryRow,
    EngagementRow,
    InitiativeRow,
)

FULL_CHAIN = [
    LifecycleState.EVIDENCE_COMPLETE,
    LifecycleState.CLASSIFIED,
    LifecycleState.CONTROLS_PRESCRIBED,
    LifecycleState.PENDING_SIGNOFF,
]


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


def _make_initiative(session, engagement: EngagementRow) -> InitiativeRow:
    return portfolio.create_initiative(
        session,
        engagement_id=engagement.id,
        name="TalentScan CV Filter",
        description="Vets and scores job applicant candidates.",
        modality="llm",
        autonomy_level="recommend_only",
        hitl_planned="yes",
    )


def _approve(session, initiative: InitiativeRow) -> None:
    decision = ApprovalDecisionRow(
        initiative_id=initiative.id,
        decision="approved",
        signer_name="Renee Manzari",
        signer_role="Governance Lead",
        rationale="Meets all control requirements for this tier.",
        packet_hash="a" * 64,
    )
    session.add(decision)
    session.flush()
    portfolio.transition(
        session,
        initiative=initiative,
        new_state=LifecycleState.APPROVED,
        actor="tester",
        reason="Approval decision recorded for test.",
    )


def test_initiative_creation_writes_an_audit_entry(session):
    engagement = _make_engagement(session)
    session.commit()
    before = session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).count()

    initiative = _make_initiative(session, engagement)
    session.commit()

    after = session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).count()
    assert after == before + 1
    assert initiative.lifecycle_state == LifecycleState.DRAFT.value


def test_transition_audit_entry_and_mutation_roll_back_together(session):
    """CLAUDE.md invariant #3: the audit entry and the state mutation are
    one transaction, not two independent commits. transition() itself
    never calls session.commit() -- only the caller does. If the
    transaction never reaches that commit (simulating a failure anywhere
    between transition() returning and the caller's commit) neither
    write should survive: proving they were never separately durable."""
    engagement = _make_engagement(session)
    initiative = _make_initiative(session, engagement)
    session.commit()

    entries_before = (
        session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).count()
    )

    portfolio.transition(
        session,
        initiative=initiative,
        new_state=LifecycleState.EVIDENCE_COMPLETE,
        actor="tester",
        reason="Uncommitted transition for the atomicity test.",
    )
    # Not committed yet -- simulates a failure between transition()
    # returning and the caller's commit.
    session.rollback()

    entries_after = (
        session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).count()
    )
    assert entries_after == entries_before, "rolled-back audit entry must not survive"

    session.refresh(initiative)
    assert (
        initiative.lifecycle_state == LifecycleState.DRAFT.value
    ), "rolled-back state mutation must not survive"
    assert audit.verify_chain(session, engagement.id).valid


def test_every_transition_writes_a_matching_audit_entry(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative(session, engagement)
    session.commit()

    for new_state in FULL_CHAIN:
        before = (
            session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).count()
        )
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=new_state,
            actor="tester",
            reason=f"Progressing to {new_state.value} for test.",
        )
        session.commit()
        after = (
            session.query(AuditEntryRow).filter_by(engagement_id=engagement.id).count()
        )
        assert after == before + 1, f"expected an audit entry for {new_state.value}"

        last_entry = (
            session.query(AuditEntryRow)
            .filter_by(engagement_id=engagement.id)
            .order_by(AuditEntryRow.seq.desc())
            .first()
        )
        assert last_entry.event_type == portfolio.EVENT_STATE_TRANSITIONED
        assert initiative.lifecycle_state == new_state.value

    assert audit.verify_chain(session, engagement.id).valid


def test_approved_requires_an_approval_decision_row(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative(session, engagement)
    session.commit()
    for new_state in FULL_CHAIN:
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=new_state,
            actor="tester",
            reason="Progressing for test.",
        )
    session.commit()

    with pytest.raises(portfolio.TransitionPreconditionError):
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=LifecycleState.APPROVED,
            actor="tester",
            reason="Attempting approval with no decision on record.",
        )

    _approve(session, initiative)
    session.commit()
    assert initiative.lifecycle_state == LifecycleState.APPROVED.value


def test_rejected_requires_a_matching_decision_value(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative(session, engagement)
    session.commit()
    for new_state in FULL_CHAIN:
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=new_state,
            actor="tester",
            reason="Progressing for test.",
        )
    session.commit()

    # An "approved" decision on record does not satisfy a REJECTED transition.
    decision = ApprovalDecisionRow(
        initiative_id=initiative.id,
        decision="approved",
        signer_name="Renee Manzari",
        signer_role="Governance Lead",
        rationale="Wrong decision value for this test on purpose.",
        packet_hash="b" * 64,
    )
    session.add(decision)
    session.commit()

    with pytest.raises(portfolio.TransitionPreconditionError):
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=LifecycleState.REJECTED,
            actor="tester",
            reason="No rejected decision on record yet.",
        )


def test_skipping_ahead_is_an_invalid_transition(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative(session, engagement)
    session.commit()

    with pytest.raises(portfolio.InvalidTransitionError):
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=LifecycleState.CONTROLS_PRESCRIBED,
            actor="tester",
            reason="Skipping ahead from DRAFT; should be rejected.",
        )


def test_phase_2_plus_states_are_not_implemented(session):
    engagement = _make_engagement(session)
    initiative = _make_initiative(session, engagement)
    session.commit()
    for new_state in FULL_CHAIN:
        portfolio.transition(
            session,
            initiative=initiative,
            new_state=new_state,
            actor="tester",
            reason="Progressing for test.",
        )
    _approve(session, initiative)
    session.commit()

    for phase_2_plus_state in (
        LifecycleState.DEPLOYED_MONITORING,
        LifecycleState.UNDER_REVIEW,
        LifecycleState.RETIRED,
    ):
        with pytest.raises(NotImplementedError):
            portfolio.transition(
                session,
                initiative=initiative,
                new_state=phase_2_plus_state,
                actor="tester",
                reason="Phase 2+ scope; should not work in Week 1.",
            )
