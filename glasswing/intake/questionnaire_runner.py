"""Questionnaire runner — ties glasswing/engines/questionnaire.py's
deterministic logic to storage and the portfolio state machine
(GLASSWING_SPEC.md section 3, Week 3).

Every handoff validates a Pydantic schema; validation failure routes to
human review with a HUMAN_REVIEW_REQUESTED audit entry, never a crash and
never a silent continue (CLAUDE.md invariant #2). The DRAFT ->
EVIDENCE_COMPLETE transition reuses services/portfolio.transition()
unchanged (Week 1's atomic audit-before-mutation pattern) rather than
reimplementing it.

Deterministic, no LLM calls -- CLAUDE.md invariant #1.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from glasswing.core.evidence import EvidenceSourceType
from glasswing.core.initiative import Initiative
from glasswing.core.lifecycle import LifecycleState
from glasswing.engines.questionnaire import (
    PydanticValidationError,
    Questionnaire,
    QuestionnaireValidationError,
    build_initiative_and_evidence_fields,
)
from glasswing.services import audit, portfolio
from glasswing.storage.models import EvidenceRecordRow, InitiativeRow

EVENT_HUMAN_REVIEW_REQUESTED = "human_review_requested"


class HumanReviewRequiredError(Exception):
    """Raised when a questionnaire submission fails schema validation.

    The HUMAN_REVIEW_REQUESTED audit entry has already been written by
    the time this is raised -- callers must not treat this as an
    unhandled crash, and must let the enclosing transaction commit (not
    roll back) so that audit entry survives. See
    glasswing/cli/app.py's `intake questionnaire` command for the
    catch-inside-session_scope pattern this requires.
    """


def submit_questionnaire(
    session: Session,
    *,
    engagement_id: uuid.UUID,
    questionnaire: Questionnaire,
    answers: dict[str, Any],
    actor: str,
) -> tuple[InitiativeRow, EvidenceRecordRow]:
    """Runs a full questionnaire intake: validates answers against the
    questionnaire schema, validates the resulting Initiative against its
    Pydantic model, creates the initiative and its evidence record, and
    transitions DRAFT -> EVIDENCE_COMPLETE.

    Raises HumanReviewRequiredError (audit entry already written) if either
    validation layer fails. Any other exception is a genuine bug, not an
    expected outcome, and is left to propagate.
    """
    try:
        initiative_fields, evidence_content = build_initiative_and_evidence_fields(
            questionnaire, answers
        )
        # Second, independent validation layer: the real Initiative model,
        # not just the questionnaire's own field-level checks.
        validated = Initiative(engagement_id=engagement_id, **initiative_fields)
    except (QuestionnaireValidationError, PydanticValidationError) as exc:
        audit.append_entry(
            session,
            engagement_id=engagement_id,
            event_type=EVENT_HUMAN_REVIEW_REQUESTED,
            actor=actor,
            payload={
                "questionnaire_id": questionnaire.questionnaire_id,
                "reason": str(exc),
            },
        )
        raise HumanReviewRequiredError(str(exc)) from exc

    initiative_row = portfolio.create_initiative(
        session,
        engagement_id=engagement_id,
        name=validated.name,
        description=validated.description,
        modality=validated.modality,
        autonomy_level=validated.autonomy_level,
        hitl_planned=validated.hitl_planned,
        data_categories=validated.data_categories,
        jurisdictions=validated.jurisdictions,
        deployment_date=validated.deployment_date,
        actor=actor,
    )

    evidence_row = portfolio.record_evidence(
        session,
        initiative=initiative_row,
        source_type=EvidenceSourceType.QUESTIONNAIRE,
        content=evidence_content,
        actor=actor,
    )

    portfolio.transition(
        session,
        initiative=initiative_row,
        new_state=LifecycleState.EVIDENCE_COMPLETE,
        actor=actor,
        reason=(
            f"Questionnaire '{questionnaire.questionnaire_id}' completed and "
            "validated."
        ),
    )

    return initiative_row, evidence_row
