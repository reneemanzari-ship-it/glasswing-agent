"""RiskProfile — output of the deterministic classification engine.

The engine itself (glasswing/engines/classification.py) lands Week 2; this
model exists in Week 1 only so the table and the Phase 1 -> Phase 2 contract
(GLASSWING_SPEC.md section 4: "the RiskProfile is the contract") have a
stable home from day one.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RiskProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    initiative_id: UUID
    per_framework_results: dict[str, Any] = Field(default_factory=dict)
    overall_tier: str = Field(..., min_length=1, max_length=50)
    human_review_required: bool = False
    engine_version: str = Field(..., min_length=1)
    framework_versions: dict[str, str] = Field(default_factory=dict)
    input_evidence_hashes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
