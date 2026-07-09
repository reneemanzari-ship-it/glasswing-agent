"""ControlPrescription and ControlStatus — output of the deterministic
controls engine (glasswing/engines/controls.py, Week 5) and its tracked
implementation state.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ControlPrescription(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    risk_profile_id: UUID
    controls: list[dict[str, Any]] = Field(default_factory=list)
    library_version: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ControlStatusValue(str, Enum):
    PRESCRIBED = "prescribed"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    WAIVED = "waived"


class ControlStatus(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    prescription_id: UUID
    control_id: str = Field(..., min_length=1)
    status: ControlStatusValue = ControlStatusValue.PRESCRIBED
    evidence_ref: str | None = None
    waiver_rationale: str | None = None
    waiver_signer: str | None = None

    @model_validator(mode="after")
    def waived_requires_rationale_and_signer(self) -> "ControlStatus":
        """CLAUDE.md invariant: waivers are recorded, never generated, and
        always attributed — a waived control with no rationale or no named
        signer is not a waiver, it's a silently dropped control."""
        if self.status == ControlStatusValue.WAIVED and (
            not self.waiver_rationale or not self.waiver_signer
        ):
            raise ValueError(
                "status=waived requires both waiver_rationale and waiver_signer"
            )
        return self
