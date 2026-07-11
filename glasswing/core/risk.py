"""RiskProfile — output of the deterministic classification engine.

per_framework_results is populated by
glasswing/engines/classification.py::build_per_framework_results(), which
returns every framework's result (eu_ai_act, nist_ai_rmf, colorado_sb_205,
nyc_ll144) as a same-shaped dict entry keyed by framework_id -- this is
the Phase 1 -> Phase 2 contract (GLASSWING_SPEC.md section 4) and what the
Week 6 report reads uniformly across frameworks (DECISIONS.md D-010).
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
