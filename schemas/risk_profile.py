"""
RiskProfile schema — output of Risk Classifier Agent.

Multi-framework classification with mandatory citations. Confidence
scores below 0.75 trigger human review.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID, uuid4


class EUAIActTier(str, Enum):
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    LIMITED_RISK = "limited_risk"
    MINIMAL_RISK = "minimal_risk"


class NISTAttentionLevel(str, Enum):
    ROUTINE = "routine"
    ELEVATED = "elevated"
    CRITICAL = "critical"


class OverallRiskTier(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class FrameworkClassification(BaseModel):
    """Base class — each framework has its own concrete subclass."""
    citations: list[str] = Field(..., min_length=1)
    rationale: str = Field(..., min_length=20, max_length=2000)
    confidence: float = Field(..., ge=0.0, le=1.0)


class EUAIActClassification(FrameworkClassification):
    tier: EUAIActTier
    applicable_annexes: list[str] = Field(default_factory=list)


class NISTAIRMFClassification(FrameworkClassification):
    govern_attention: NISTAttentionLevel
    map_attention: NISTAttentionLevel
    measure_attention: NISTAttentionLevel
    manage_attention: NISTAttentionLevel
    critical_categories: list[str] = Field(default_factory=list)


class ColoradoSB205Classification(FrameworkClassification):
    applicable: bool
    high_risk_category: Optional[str] = None

    @model_validator(mode="after")
    def category_required_if_applicable(self) -> "ColoradoSB205Classification":
        if self.applicable and not self.high_risk_category:
            raise ValueError(
                "high_risk_category required when applicable=True"
            )
        return self


class Classifications(BaseModel):
    eu_ai_act: EUAIActClassification
    nist_ai_rmf: NISTAIRMFClassification
    colorado_sb_205: ColoradoSB205Classification


class RiskProfile(BaseModel):
    """
    Output of Risk Classifier Agent. Consumed by Control Prescription Agent.
    """
    risk_profile_id: UUID = Field(default_factory=uuid4)
    initiative_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    classifications: Classifications
    overall_risk_tier: OverallRiskTier
    regulatory_exposure_summary: str = Field(..., min_length=20, max_length=1000)

    human_review_required: bool = False
    human_review_reasons: list[str] = Field(default_factory=list)

    # Meta for replay
    classifier_agent_version: str
    prompt_manifest_sha: str
    mcp_server_version: str
    model_id: str  # e.g. "claude-sonnet-4-5-20250115"

    @model_validator(mode="after")
    def review_required_when_low_confidence(self) -> "RiskProfile":
        """
        Any framework classification below 0.75 confidence triggers human
        review automatically. This is a structural safeguard, not a
        recommendation.
        """
        low_confidence_frameworks = []
        if self.classifications.eu_ai_act.confidence < 0.75:
            low_confidence_frameworks.append("eu_ai_act")
        if self.classifications.nist_ai_rmf.confidence < 0.75:
            low_confidence_frameworks.append("nist_ai_rmf")
        if self.classifications.colorado_sb_205.confidence < 0.75:
            low_confidence_frameworks.append("colorado_sb_205")

        if low_confidence_frameworks:
            self.human_review_required = True
            self.human_review_reasons.append(
                f"Low confidence in classifications: "
                f"{', '.join(low_confidence_frameworks)}"
            )
        return self
