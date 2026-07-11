"""NYCLL144Classification — NYC Local Law 144 (Automated Employment
Decision Tools) applicability result.

Not a field on schemas.risk_profile.RiskProfile.Classifications: that
model is a required, non-optional triple (eu_ai_act, nist_ai_rmf,
colorado_sb_205) constructed throughout the still-live v0.1 pipeline
(orchestration/flow.py, agents/*, tests), and adding a fourth required
field there would break every existing call site. But it DOES fold into
the forward-facing contract: glasswing.core.risk.RiskProfile.per_framework_results
(a plain JSON dict) includes an "nyc_ll144" entry alongside the other
three, built by engines/classification.py::build_per_framework_results().
This model stays the return type of the low-level
classify_nyc_ll144() function that feeds that dict (DECISIONS.md D-010,
resolved Week 3).
"""

from pydantic import BaseModel, Field


class NYCLL144Classification(BaseModel):
    applicable: bool
    citations: list[str] = Field(default_factory=list)
    rationale: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_bias_audit: bool = False
