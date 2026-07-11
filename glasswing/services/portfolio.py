"""Initiative lifecycle state machine.

Transitions are the only way lifecycle_state changes (GLASSWING_SPEC.md
section 2.6). Every transition writes an audit entry to the engagement's
hash chain in the same transaction as the state mutation, before the
mutation is considered committed (CLAUDE.md invariant #3) — see
glasswing/storage/database.py::session_scope for the commit/rollback
boundary that makes this atomic.

Implements transitions through REJECTED only, per GLASSWING_SPEC.md
section 3 Week 1 scope: "Phase 2 states defined but transitions to them
raise NotImplementedError." Deterministic, no LLM calls — CLAUDE.md
invariant #1.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from glasswing.core.evidence import EvidenceSourceType
from glasswing.core.lifecycle import LifecycleState
from glasswing.services import audit
from glasswing.storage.models import (
    ApprovalDecisionRow,
    EvidenceRecordRow,
    InitiativeRow,
    RiskProfileRow,
)

EVENT_INITIATIVE_CREATED = "initiative_created"
EVENT_EVIDENCE_RECORDED = "evidence_recorded"
EVENT_RISK_PROFILE_RECORDED = "risk_profile_recorded"
EVENT_STATE_TRANSITIONED = "state_transitioned"

# Legal edges implemented this week: DRAFT -> ... -> {APPROVED |
# REQUIRES_REVISION | REJECTED}. REQUIRES_REVISION and REJECTED have no
# outgoing edges defined yet — GLASSWING_SPEC.md doesn't specify what
# happens after them, so no edge is invented (DECISIONS.md D-003).
# Anything touching a Phase 2+ state (DEPLOYED_MONITORING, UNDER_REVIEW,
# RETIRED) raises NotImplementedError instead of InvalidTransitionError —
# see transition() below.
_IMPLEMENTED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.DRAFT: frozenset({LifecycleState.EVIDENCE_COMPLETE}),
    LifecycleState.EVIDENCE_COMPLETE: frozenset({LifecycleState.CLASSIFIED}),
    LifecycleState.CLASSIFIED: frozenset({LifecycleState.CONTROLS_PRESCRIBED}),
    LifecycleState.CONTROLS_PRESCRIBED: frozenset({LifecycleState.PENDING_SIGNOFF}),
    LifecycleState.PENDING_SIGNOFF: frozenset(
        {
            LifecycleState.APPROVED,
            LifecycleState.REQUIRES_REVISION,
            LifecycleState.REJECTED,
        }
    ),
}

_PHASE_2_PLUS_STATES = frozenset(
    {
        LifecycleState.DEPLOYED_MONITORING,
        LifecycleState.UNDER_REVIEW,
        LifecycleState.RETIRED,
    }
)

# GLASSWING_SPEC.md section 2.6: "PENDING_SIGNOFF -> APPROVED requires an
# ApprovalDecision row whose packet_hash matches current records." Week 1
# checks existence of a matching decision row; packet_hash
# cross-validation against current records is services/signoff.py's job
# once it exists to compute that hash in the first place (Week 5,
# DECISIONS.md D-004).
_DECISION_FOR_STATE: dict[LifecycleState, str] = {
    LifecycleState.APPROVED: "approved",
    LifecycleState.REQUIRES_REVISION: "requires_revision",
    LifecycleState.REJECTED: "rejected",
}


class InvalidTransitionError(ValueError):
    """The requested edge is not legal from the initiative's current state."""


class TransitionPreconditionError(ValueError):
    """The edge is legal in principle, but its precondition isn't met yet."""


def create_initiative(
    session: Session,
    *,
    engagement_id: uuid.UUID,
    name: str,
    description: str,
    modality: str,
    autonomy_level: str,
    hitl_planned: str,
    data_categories: list[str] | None = None,
    jurisdictions: list[str] | None = None,
    deployment_date: date | None = None,
    actor: str = "system",
) -> InitiativeRow:
    """Creates the initiative row in DRAFT state and logs its creation.

    The richer intake fields (Week 3's questionnaire, Week 4's extraction)
    populate evidence_records against this initiative_id; this function
    only establishes the row and its starting lifecycle state.
    """
    initiative = InitiativeRow(
        engagement_id=engagement_id,
        name=name,
        description=description,
        modality=modality,
        autonomy_level=autonomy_level,
        data_categories=data_categories or [],
        jurisdictions=jurisdictions or [],
        deployment_date=deployment_date,
        hitl_planned=hitl_planned,
        lifecycle_state=LifecycleState.DRAFT.value,
    )
    session.add(initiative)
    session.flush()

    audit.append_entry(
        session,
        engagement_id=engagement_id,
        event_type=EVENT_INITIATIVE_CREATED,
        actor=actor,
        payload={
            "initiative_id": str(initiative.id),
            "name": name,
            "lifecycle_state": LifecycleState.DRAFT.value,
        },
    )
    return initiative


def record_evidence(
    session: Session,
    *,
    initiative: InitiativeRow,
    source_type: EvidenceSourceType,
    content: dict[str, Any],
    actor: str = "system",
    source_document_hash: str | None = None,
    extraction_confidence: float | None = None,
) -> EvidenceRecordRow:
    """Creates an evidence_records row for `initiative` and logs its
    creation, mirroring create_initiative()'s audit pattern. Used by the
    Week 3 questionnaire runner (glasswing/intake/questionnaire_runner.py)
    and, from Week 4 on, the Evidence Extraction Agent's offline path.
    """
    evidence = EvidenceRecordRow(
        initiative_id=initiative.id,
        source_type=source_type.value,
        content=content,
        source_document_hash=source_document_hash,
        extraction_confidence=extraction_confidence,
    )
    session.add(evidence)
    session.flush()

    audit.append_entry(
        session,
        engagement_id=initiative.engagement_id,
        event_type=EVENT_EVIDENCE_RECORDED,
        actor=actor,
        payload={
            "initiative_id": str(initiative.id),
            "evidence_record_id": str(evidence.id),
            "source_type": source_type.value,
        },
    )
    return evidence


def record_risk_profile(
    session: Session,
    *,
    initiative: InitiativeRow,
    per_framework_results: dict[str, Any],
    overall_tier: str,
    human_review_required: bool,
    engine_version: str,
    framework_versions: dict[str, str],
    input_evidence_hashes: list[str] | None = None,
    actor: str = "system",
) -> RiskProfileRow:
    """Creates a risk_profiles row for `initiative` and logs its
    creation, mirroring create_initiative()/record_evidence()'s audit
    pattern. Used by the Week 4 extraction runner
    (glasswing/intake/extraction_runner.py) once
    glasswing/engines/classification.py has classified an initiative --
    this function only persists what the engine decided, it never
    decides anything itself (CLAUDE.md invariant #1).
    """
    risk_profile = RiskProfileRow(
        initiative_id=initiative.id,
        per_framework_results=per_framework_results,
        overall_tier=overall_tier,
        human_review_required=human_review_required,
        engine_version=engine_version,
        framework_versions=framework_versions,
        input_evidence_hashes=input_evidence_hashes or [],
    )
    session.add(risk_profile)
    session.flush()

    audit.append_entry(
        session,
        engagement_id=initiative.engagement_id,
        event_type=EVENT_RISK_PROFILE_RECORDED,
        actor=actor,
        payload={
            "initiative_id": str(initiative.id),
            "risk_profile_id": str(risk_profile.id),
            "overall_tier": overall_tier,
            "engine_version": engine_version,
        },
    )
    return risk_profile


def _check_preconditions(
    session: Session, initiative: InitiativeRow, new_state: LifecycleState
) -> None:
    decision = _DECISION_FOR_STATE.get(new_state)
    if decision is None:
        return
    stmt = select(ApprovalDecisionRow).where(
        ApprovalDecisionRow.initiative_id == initiative.id,
        ApprovalDecisionRow.decision == decision,
    )
    if session.execute(stmt).scalars().first() is None:
        raise TransitionPreconditionError(
            f"Cannot transition to {new_state.value}: no ApprovalDecision row "
            f"with decision={decision!r} on record for initiative {initiative.id}."
        )


def transition(
    session: Session,
    *,
    initiative: InitiativeRow,
    new_state: LifecycleState,
    actor: str,
    reason: str,
) -> InitiativeRow:
    """Moves `initiative` to `new_state`, writing the audit entry first.

    Raises:
        NotImplementedError: the edge touches a Phase 2+ state
            (DEPLOYED_MONITORING, UNDER_REVIEW, RETIRED).
        InvalidTransitionError: the edge isn't legal from the current state.
        TransitionPreconditionError: the edge is legal but its
            precondition isn't satisfied.
    """
    current_state = LifecycleState(initiative.lifecycle_state)

    if new_state in _PHASE_2_PLUS_STATES or current_state in _PHASE_2_PLUS_STATES:
        raise NotImplementedError(
            f"Transition {current_state.value} -> {new_state.value} is Phase 2+ "
            "scope (GLASSWING_SPEC.md section 3) and is not implemented in Week 1."
        )

    allowed = _IMPLEMENTED_TRANSITIONS.get(current_state, frozenset())
    if new_state not in allowed:
        legal = sorted(s.value for s in allowed)
        raise InvalidTransitionError(
            f"{current_state.value} -> {new_state.value} is not a legal transition. "
            f"Legal transitions from {current_state.value}: {legal or 'none'}."
        )

    _check_preconditions(session, initiative, new_state)

    # --- INVARIANT-CRITICAL (CLAUDE.md #3: "no entry, no mutation") ---
    # audit.append_entry() and the lifecycle_state assignment below must
    # stay in this order, in this same still-open `session`, with no
    # session.commit() between them. Neither call commits anything itself
    # (append_entry only adds+flushes); the caller's single commit (or
    # session_scope's rollback-on-exception) is what makes both durable —
    # or both vanish — together. Do not split these across two
    # transactions, and do not let a caller commit in between.
    audit.append_entry(
        session,
        engagement_id=initiative.engagement_id,
        event_type=EVENT_STATE_TRANSITIONED,
        actor=actor,
        payload={
            "initiative_id": str(initiative.id),
            "previous_state": current_state.value,
            "new_state": new_state.value,
            "reason": reason,
        },
    )
    initiative.lifecycle_state = new_state.value
    session.flush()
    # --- end invariant-critical block ---
    return initiative
