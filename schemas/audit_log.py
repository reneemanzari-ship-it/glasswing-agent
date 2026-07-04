"""
AuditLogEntry schema — the cross-cutting audit log.

Every action by every agent in the Glasswing system creates one of these.
The log is append-only with a cryptographic hash chain making it
tamper-evident.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from uuid import UUID, uuid4


class AgentID(str, Enum):
    ONBOARDING_INTAKE = "onboarding_intake"
    RISK_CLASSIFIER = "risk_classifier"
    CONTROL_PRESCRIPTION = "control_prescription"
    PORTFOLIO_MANAGER = "portfolio_manager"
    AUDIT_TRAIL = "audit_trail"


class ActionType(str, Enum):
    INTAKE_STARTED = "intake_started"
    INTAKE_COMPLETED = "intake_completed"
    CLASSIFICATION_COMPLETED = "classification_completed"
    PRESCRIPTION_COMPLETED = "prescription_completed"
    STATE_TRANSITIONED = "state_transitioned"
    REPORT_GENERATED = "report_generated"
    SECURITY_FLAG_RAISED = "security_flag_raised"
    HUMAN_REVIEW_REQUESTED = "human_review_requested"
    MANIFEST_CREATED = "manifest_created"
    MANIFEST_APPROVED = "manifest_approved"
    REPLAY_REQUESTED = "replay_requested"


class SensitivityClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class AuditLogEntry(BaseModel):
    """
    A single audit log entry. Append-only.
    """
    audit_log_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Who did what
    agent_id: AgentID
    agent_version: str  # semver
    action_type: ActionType
    initiative_id: Optional[UUID] = None  # null for portfolio-level actions

    # Replay metadata
    model_id: str = Field(..., min_length=3)  # e.g. "claude-sonnet-4-5-20250115"
    prompt_manifest_sha: str = Field(..., min_length=40, max_length=40)
    input_hash: str = Field(..., min_length=64, max_length=64)  # sha256
    output_hash: str = Field(..., min_length=64, max_length=64)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Execution metadata
    tools_invoked: list[str] = Field(default_factory=list)
    duration_ms: int = Field(..., ge=0)
    sensitivity_classification: SensitivityClassification

    # Chain integrity
    previous_audit_log_id: Optional[UUID] = None  # null only for first entry
    chain_hash: str = Field(..., min_length=64, max_length=64)

    # Optional additional context (NOT for sensitive content)
    public_context: Optional[str] = Field(None, max_length=500)

    @field_validator("public_context")
    @classmethod
    def public_context_must_not_contain_pii_markers(
        cls, v: Optional[str]
    ) -> Optional[str]:
        """
        Basic safeguard: refuse common PII patterns. Real PII detection
        happens upstream in the agents themselves. This is belt-and-suspenders.
        """
        if v is None:
            return v
        pii_markers = ["@", "ssn", "credit card", "password", "api_key", "sk-"]
        v_lower = v.lower()
        for marker in pii_markers:
            if marker in v_lower:
                raise ValueError(
                    f"public_context appears to contain sensitive marker: "
                    f"'{marker}'. Use input_hash reference instead."
                )
        return v
