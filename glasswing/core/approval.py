"""ApprovalDecision — the load-bearing sign-off record (GLASSWING_SPEC.md
section 2.6). A named human decision, never made by an engine or an agent.

services/signoff.py (Week 5) is what computes packet_hash and writes these
rows via the portfolio state machine's PENDING_SIGNOFF preconditions; this
model exists in Week 1 so those preconditions have a real table to check
against.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ApprovalDecisionValue(str, Enum):
    APPROVED = "approved"
    REQUIRES_REVISION = "requires_revision"
    REJECTED = "rejected"


class ApprovalDecision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    initiative_id: UUID
    decision: ApprovalDecisionValue
    signer_name: str = Field(..., min_length=1, max_length=200)
    signer_role: str = Field(..., min_length=1, max_length=200)
    rationale: str = Field(..., min_length=1, max_length=2000)
    packet_hash: str = Field(..., min_length=1)
    decided_at: datetime = Field(default_factory=datetime.utcnow)
