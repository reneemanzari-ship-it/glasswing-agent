"""RunLedgerEntry — records the exact versions that produced any pipeline
step's output (CLAUDE.md invariant #4). Every engine and agent invocation
writes one of these, from Week 1 onward, even before any engine exists to
call — the ledger itself is the stable piece.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RunLedgerEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    pipeline_step: str = Field(..., min_length=1, max_length=100)
    engine_version: str | None = None
    framework_versions: dict[str, str] = Field(default_factory=dict)
    prompt_version: str | None = None
    model_id: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
