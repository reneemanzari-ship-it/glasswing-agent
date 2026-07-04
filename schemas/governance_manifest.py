"""
GovernanceManifest schema — the machine-readable per-initiative spec.

This is the consolidated artifact that travels with an initiative
through its lifecycle. Engineering teams consume it to know what to
build. Auditors consume it to know what to verify. Regulators consume
it on demand for compliance reviews.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class ManifestStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


class GovernanceManifest(BaseModel):
    """
    Per-initiative governance spec. The source of truth that engineering,
    audit, and regulators all reference.
    """
    manifest_id: UUID = Field(default_factory=uuid4)
    manifest_version: int = Field(default=1, ge=1)
    initiative_id: UUID
    status: ManifestStatus = ManifestStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None  # role + name

    # The three core artifacts, embedded by ID reference (not by value,
    # to keep manifest size manageable)
    initiative_ref: UUID  # references Initiative
    risk_profile_ref: UUID  # references RiskProfile
    control_prescription_ref: UUID  # references ControlPrescription

    # Hashes for integrity verification
    initiative_hash: str = Field(..., min_length=64, max_length=64)
    risk_profile_hash: str = Field(..., min_length=64, max_length=64)
    control_prescription_hash: str = Field(..., min_length=64, max_length=64)

    # Manifest-level signature
    previous_manifest_hash: Optional[str] = None  # for version chain
    manifest_hash: str = Field(..., min_length=64, max_length=64)

    # Human-readable summary for non-technical consumers
    executive_summary: str = Field(..., min_length=50, max_length=2000)
    deployment_readiness: dict[str, bool] = Field(default_factory=dict)
    # e.g. {"controls_implemented": false, "approvers_signed_off": false,
    #       "regulatory_submissions_filed": false}
