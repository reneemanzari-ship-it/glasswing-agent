"""Evidence extraction runner (GLASSWING_SPEC.md section 3, Week 4).

Ties glasswing/agents/evidence_extraction.py's output to the
deterministic classifier and the portfolio state machine: extract ->
validate -> classify -> persist RiskProfile -> transition
EVIDENCE_COMPLETE -> CLASSIFIED.

CLAUDE.md invariant #1 boundary: the LLM (agents/evidence_extraction.py)
extracts; glasswing/engines/classification.py classifies. This module is
the seam between the two -- it calls the engine and records what the
engine decided; it never assigns a tier itself. Every validation failure
routes to human review with a HUMAN_REVIEW_REQUESTED audit entry (never
a crash, never a silent continue -- CLAUDE.md invariant #2). The
EVIDENCE_COMPLETE -> CLASSIFIED transition reuses
services/portfolio.transition() unchanged (Week 1's atomic
audit-before-mutation pattern).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from glasswing.agents.evidence_extraction import (
    ExtractionValidationError,
    extract_evidence,
)
from glasswing.core.evidence import EvidenceSourceType
from glasswing.core.extracted_evidence import ExtractedEvidence
from glasswing.core.lifecycle import LifecycleState
from glasswing.engines.classification import (
    ENGINE_VERSION,
    build_per_framework_results,
    classify_initiative,
)
from glasswing.services import audit, portfolio
from glasswing.storage.models import InitiativeRow, RiskProfileRow
from mcp_server.server import _load_framework_json
from schemas.initiative import (
    AISystemCharacteristics,
    AISystemType,
    AutonomyLevel,
    BusinessImpactTier,
    DataCharacteristics,
    DataSensitivity,
    HITLPlanned,
    ImpactCharacteristics,
    IntakeMetadata,
    Reversibility,
    Sponsor,
    UserScope,
)
from schemas.initiative import Initiative as ClassifierInitiative

EVENT_HUMAN_REVIEW_REQUESTED = "human_review_requested"
EXTRACTION_AGENT_VERSION = "1.0.0"
CONFIDENCE_THRESHOLD = 0.75

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extraction" / "v1.md"
_FRAMEWORK_IDS_FOR_VERSIONING = (
    "eu_ai_act",
    "nist_ai_rmf",
    "colorado_sb_205",
    "nyc_ll144",
)


class HumanReviewRequiredError(Exception):
    """Raised when extraction fails schema validation, or succeeds but
    falls below the confidence/completeness threshold. The
    HUMAN_REVIEW_REQUESTED audit entry has already been written by the
    time this is raised -- see glasswing/cli/app.py's catch-inside-
    session_scope pattern (same as the Week 3 questionnaire runner) for
    why callers must not let this propagate out of an open transaction.
    """


def _prompt_manifest_sha() -> str:
    import hashlib

    return hashlib.sha256(_PROMPT_PATH.read_bytes()).hexdigest()[:40]


def _current_framework_versions() -> dict[str, str]:
    """Reads the current framework_version field from each dataset file
    -- honest per-artifact version recording (CLAUDE.md invariant #4),
    not a hardcoded snapshot that could silently drift from the files
    themselves. Reuses mcp_server.server's own loader rather than
    duplicating file-path logic (DECISIONS.md D-023's finding: the
    classification engine itself does not consult these files; this is
    metadata-only, recorded alongside the engine's output, not consumed
    by it).
    """
    versions: dict[str, str] = {}
    for framework_id in _FRAMEWORK_IDS_FOR_VERSIONING:
        data = _load_framework_json(framework_id)
        version = data.get("framework_version")
        if version:
            versions[framework_id] = version
    return versions


def _bridge_to_classifier_initiative(
    initiative: InitiativeRow, extracted: ExtractedEvidence
) -> ClassifierInitiative:
    """Bridges glasswing.core.initiative.Initiative (the storage shape
    Weeks 1/3 populate) into schemas.initiative.Initiative (the rich
    shape glasswing/engines/classification.py consumes, per DECISIONS.md
    D-009) using ExtractedEvidence for the fields the storage model
    doesn't carry.

    Fields neither model supplies (sponsor identity, intake timing) fall
    back to the same "unknown"/default placeholders v0.1's own freeform-
    intake extraction path already established
    (skills/ai_risk_tier_classification/scripts/classifier.py::
    AIRiskTierClassificationSkill._extract_initiative) -- not a new
    convention invented here. See DECISIONS.md D-025.
    """
    return ClassifierInitiative(
        name=initiative.name,
        sponsor=Sponsor(business_unit="unknown", owner="unknown"),
        description=initiative.description,
        target_deployment_date=initiative.deployment_date,
        ai_system=AISystemCharacteristics(
            type=AISystemType(initiative.modality),
            autonomy_level=AutonomyLevel(initiative.autonomy_level),
            hitl_planned=HITLPlanned(initiative.hitl_planned),
            hitl_description=None,
        ),
        data=DataCharacteristics(
            sources=extracted.data_sources or ["unknown"],
            sensitivity=(
                [DataSensitivity(s) for s in extracted.data_sensitivity]
                or [DataSensitivity.NONE]
            ),
            jurisdictions=initiative.jurisdictions or ["unknown"],
        ),
        impact=ImpactCharacteristics(
            user_scope=(
                [UserScope(s) for s in extracted.user_scope]
                or [UserScope.INTERNAL_EMPLOYEES]
            ),
            business_impact_tier=(
                BusinessImpactTier(extracted.business_impact_tier)
                if extracted.business_impact_tier
                else BusinessImpactTier.MODERATE
            ),
            reversibility=(
                Reversibility(extracted.reversibility)
                if extracted.reversibility
                else Reversibility.PARTIALLY_REVERSIBLE
            ),
        ),
        existing_controls=extracted.existing_controls,
        intake_metadata=IntakeMetadata(
            completeness_score=extracted.completeness_score,
            unknowns=extracted.unknowns,
            intake_duration_minutes=0.0,
            intake_agent_version=EXTRACTION_AGENT_VERSION,
            prompt_manifest_sha=_prompt_manifest_sha(),
        ),
    )


def run_extraction_and_classification(
    session: Session,
    *,
    initiative: InitiativeRow,
    source_text: str,
    source_type: EvidenceSourceType,
    actor: str,
    fixture_response: str | None = None,
) -> tuple[RiskProfileRow, InitiativeRow]:
    """Runs the full Week 4 pipeline: extract -> validate -> record
    evidence -> classify -> record RiskProfile -> transition
    EVIDENCE_COMPLETE -> CLASSIFIED.

    Raises HumanReviewRequiredError (audit entry already written) if
    extraction fails schema validation, or if its confidence/completeness
    falls below CONFIDENCE_THRESHOLD. Any other exception is a genuine
    bug, not an expected outcome, and is left to propagate.
    """
    try:
        extracted = extract_evidence(
            source_text,
            source_type.value,
            fixture_response=fixture_response,
        )
    except ExtractionValidationError as exc:
        audit.append_entry(
            session,
            engagement_id=initiative.engagement_id,
            event_type=EVENT_HUMAN_REVIEW_REQUESTED,
            actor=actor,
            payload={"initiative_id": str(initiative.id), "reason": str(exc)},
        )
        raise HumanReviewRequiredError(str(exc)) from exc

    if (
        extracted.extraction_confidence < CONFIDENCE_THRESHOLD
        or extracted.completeness_score < CONFIDENCE_THRESHOLD
    ):
        reason = (
            "Extraction confidence or completeness below threshold "
            f"({CONFIDENCE_THRESHOLD}): confidence={extracted.extraction_confidence}, "
            f"completeness={extracted.completeness_score}."
        )
        audit.append_entry(
            session,
            engagement_id=initiative.engagement_id,
            event_type=EVENT_HUMAN_REVIEW_REQUESTED,
            actor=actor,
            payload={"initiative_id": str(initiative.id), "reason": reason},
        )
        raise HumanReviewRequiredError(reason)

    portfolio.record_evidence(
        session,
        initiative=initiative,
        source_type=source_type,
        content=extracted.model_dump(),
        actor=actor,
        extraction_confidence=extracted.extraction_confidence,
    )

    classifier_initiative = _bridge_to_classifier_initiative(initiative, extracted)
    # The engine classifies; this module only records what it decided.
    risk_profile = classify_initiative(classifier_initiative)
    per_framework_results = build_per_framework_results(classifier_initiative)

    risk_profile_row = portfolio.record_risk_profile(
        session,
        initiative=initiative,
        per_framework_results=per_framework_results,
        overall_tier=risk_profile.overall_risk_tier.value,
        human_review_required=risk_profile.human_review_required,
        engine_version=ENGINE_VERSION,
        framework_versions=_current_framework_versions(),
        actor=actor,
    )

    portfolio.transition(
        session,
        initiative=initiative,
        new_state=LifecycleState.CLASSIFIED,
        actor=actor,
        reason=(
            f"Classified via deterministic engine (engine_version="
            f"{ENGINE_VERSION}); overall_tier="
            f"{risk_profile.overall_risk_tier.value}."
        ),
    )

    return risk_profile_row, initiative
