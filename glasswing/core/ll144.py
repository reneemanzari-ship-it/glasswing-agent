"""NYCLL144Classification — NYC Local Law 144 (Automated Employment
Decision Tools) applicability result.

Deliberately NOT a field on schemas.risk_profile.RiskProfile.Classifications:
that model is a required, non-optional triple (eu_ai_act, nist_ai_rmf,
colorado_sb_205) constructed throughout the still-live v0.1 pipeline
(orchestration/flow.py, agents/*, tests). Adding a fourth required field
there would break every existing call site; making it optional would still
touch a shared schema the Week 2 disposition table doesn't list as
changing. LL144 is new classification capability, so it gets its own
model and its own function (engines/classification.py::classify_nyc_ll144),
called alongside classify_initiative() rather than folded into it
(DECISIONS.md D-010).
"""

from pydantic import BaseModel, Field


class NYCLL144Classification(BaseModel):
    applicable: bool
    citations: list[str] = Field(default_factory=list)
    rationale: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_bias_audit: bool = False
