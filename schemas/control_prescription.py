"""
ControlPrescription schema — output of Control Prescription Agent.

Specifies concrete, implementable controls. Every control must be
specific enough that an engineering team can build to it without
further interpretation.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class ControlCategory(str, Enum):
    INPUT_VALIDATION = "input_validation"
    OUTPUT_SCHEMA = "output_schema"
    PROMPT_DEFENSE = "prompt_defense"
    CONTENT_FILTER = "content_filter"
    CONFIDENCE_THRESHOLD = "confidence_threshold"


class SourceFramework(str, Enum):
    EU_AI_ACT = "EU AI Act"
    NIST_AI_RMF = "NIST AI RMF"
    COLORADO_SB_205 = "Colorado SB 205"
    NYC_LL_144 = "NYC Local Law 144"
    ISO_42001 = "ISO 42001"
    INTERNAL_POLICY = "Internal Policy"


class Guardrail(BaseModel):
    control_id: str = Field(..., pattern=r"^GR-\d{4}$")  # e.g. "GR-0001"
    category: ControlCategory
    description: str = Field(..., min_length=20, max_length=1000)
    implementation_notes: str = Field(..., min_length=20, max_length=2000)
    mandatory: bool
    source_framework: list[SourceFramework] = Field(..., min_length=1)
    source_citation: str = Field(..., min_length=5)


class HITLTouchpoint(BaseModel):
    control_id: str = Field(..., pattern=r"^HITL-\d{4}$")
    trigger_description: str = Field(..., min_length=20, max_length=1000)
    trigger_quantitative: Optional[str] = None  # e.g. "loan_amount > 500000"
    reviewer_role: str = Field(..., min_length=3, max_length=100)
    review_sla_hours: int = Field(..., ge=1, le=720)  # 1 hour to 30 days
    mandatory: bool
    source_framework: list[SourceFramework] = Field(..., min_length=1)


class MonitoringRequirement(BaseModel):
    control_id: str = Field(..., pattern=r"^MON-\d{4}$")
    metric: str = Field(..., min_length=3, max_length=200)
    cadence: str = Field(..., min_length=3, max_length=100)  # "real-time", "daily", etc.
    alerting_threshold: str = Field(..., min_length=5, max_length=500)
    on_call_role: str = Field(..., min_length=3, max_length=100)
    mandatory: bool


class AuditArtifactRequirement(BaseModel):
    control_id: str = Field(..., pattern=r"^AUD-\d{4}$")
    artifact_type: str = Field(..., min_length=3, max_length=200)
    retention_years: int = Field(..., ge=1, le=99)
    regulator_format_required: bool
    replay_capability_required: bool
    source_framework: list[SourceFramework] = Field(..., min_length=1)


class RegulatorySubmission(BaseModel):
    control_id: str = Field(..., pattern=r"^REG-\d{4}$")
    submission_type: str  # "EU AI Act conformity assessment", etc.
    submission_authority: str
    submission_deadline_days_before_deployment: int
    mandatory: bool
    source_framework: list[SourceFramework] = Field(..., min_length=1)


class IndependentReview(BaseModel):
    control_id: str = Field(..., pattern=r"^IR-\d{4}$")
    review_type: str  # "internal audit", "external fairness audit", etc.
    cadence: str  # "annual", "quarterly", "pre-deployment"
    mandatory: bool


class Controls(BaseModel):
    guardrails: list[Guardrail] = Field(default_factory=list)
    hitl_touchpoints: list[HITLTouchpoint] = Field(default_factory=list)
    monitoring: list[MonitoringRequirement] = Field(default_factory=list)
    audit_artifacts: list[AuditArtifactRequirement] = Field(default_factory=list)
    regulatory_submissions: list[RegulatorySubmission] = Field(default_factory=list)
    independent_review: list[IndependentReview] = Field(default_factory=list)


class DeploymentGate(BaseModel):
    approvers_required: list[str] = Field(..., min_length=1)  # roles
    pre_deployment_artifacts_required: list[str] = Field(..., min_length=1)
    ongoing_compliance_artifacts: list[str] = Field(default_factory=list)


class ImplementationEffort(BaseModel):
    engineering_weeks: float = Field(..., ge=0)
    governance_team_weeks: float = Field(..., ge=0)
    external_review_cost_estimate_usd: Optional[Decimal] = None


class ControlPrescription(BaseModel):
    control_prescription_id: UUID = Field(default_factory=uuid4)
    initiative_id: UUID
    risk_profile_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    risk_tier_assessed: str  # mirrors RiskProfile.overall_risk_tier
    controls: Controls
    deployment_gate: DeploymentGate
    estimated_implementation_effort: ImplementationEffort
    executive_summary: str = Field(..., min_length=50, max_length=1000)

    # Meta for replay
    prescription_agent_version: str
    prompt_manifest_sha: str
    model_id: str
