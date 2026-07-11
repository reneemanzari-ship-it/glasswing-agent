"""ExtractedEvidence — structured output of the Evidence Extraction Agent
(GLASSWING_SPEC.md section 2.4, Week 4).

Structurally enforces CLAUDE.md invariant #1 and the Week 4 boundary
invariant: this model has NO field that could carry a risk tier,
classification result, or control prescription. It describes the AI
system's characteristics for the deterministic classifier
(glasswing/engines/classification.py) to judge -- it never judges the
system itself. See tests/glasswing/test_agent_boundary.py, which asserts
this structurally (checking the model's field names), not just by
convention.

`business_impact_tier` below is not a regulatory risk tier -- it is the
same INPUT characteristic v0.1's schemas.initiative.ImpactCharacteristics
already carries (how big a deal is this system's business impact,
reported by intake), distinct from `overall_risk_tier` /
`eu_ai_act.tier`, which are OUTPUTS the classification engine assigns.
The structural test checks for the latter, not the former.
"""

from pydantic import BaseModel, Field

# Exact field names a classification/control-prescription result would
# use -- never legitimate on an extraction-evidence model. Checked by
# name, not by substring, so legitimate input fields that happen to
# contain "tier" (business_impact_tier) or "control" (existing_controls)
# are not false positives.
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "tier",
        "risk_tier",
        "overall_tier",
        "overall_risk_tier",
        "classification",
        "classifications",
        "eu_ai_act",
        "nist_ai_rmf",
        "colorado_sb_205",
        "nyc_ll144",
        "human_review_required",
        "prescribed_controls",
        "control_prescription",
        "required_controls",
    }
)


class ExtractedEvidence(BaseModel):
    data_sensitivity: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    user_scope: list[str] = Field(default_factory=list)
    business_impact_tier: str | None = None
    reversibility: str | None = None
    existing_controls: list[str] = Field(default_factory=list)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    unknowns: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)
    citations: dict[str, str] = Field(default_factory=dict)
