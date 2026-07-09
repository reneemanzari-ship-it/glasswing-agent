"""AuditEntry — one link in an engagement's tamper-evident hash chain.

See glasswing/services/audit.py for the chain construction and verification
logic this model is written by. Ported from v0.1's agents/audit_trail.py
per GLASSWING_SPEC.md section 2.3 — same SHA-256 chain-hash design, now
scoped per-engagement with a genesis entry instead of one global list.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    seq: int = Field(..., ge=0)
    event_type: str = Field(..., min_length=1, max_length=100)
    actor: str = Field(..., min_length=1, max_length=200)
    payload_hash: str = Field(..., min_length=64, max_length=64)
    prev_chain_hash: str | None = Field(default=None, min_length=64, max_length=64)
    chain_hash: str = Field(..., min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=datetime.utcnow)
