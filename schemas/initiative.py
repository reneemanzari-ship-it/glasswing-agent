"""
Initiative schema — the structured output of the Onboarding Intake Agent.

This is the canonical representation of an AI initiative entering the
Glasswing governance system. Every downstream agent operates on this
object or its derivatives.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from uuid import UUID, uuid4


class AISystemType(str, Enum):
    LLM = "llm"
    CLASSICAL_ML = "classical_ml"
    COMPUTER_VISION = "computer_vision"
    MULTI_AGENT = "multi_agent"
    HYBRID = "hybrid"
    OTHER = "other"


class AutonomyLevel(str, Enum):
    RECOMMEND_ONLY = "recommend_only"           # AI suggests, human decides
    APPROVE_WITH_OVERRIDE = "approve_with_override"  # AI acts, human can reverse
    FULLY_AUTONOMOUS = "fully_autonomous"       # AI acts without human review


class HITLPlanned(str, Enum):
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class DataSensitivity(str, Enum):
    NONE = "none"
    COMMERCIAL = "commercial"
    PII = "pii"
    FINANCIAL = "financial"
    HEALTH = "health"
    BIOMETRIC = "biometric"
    CHILDREN = "children"


class UserScope(str, Enum):
    INTERNAL_EMPLOYEES = "internal_employees"
    B2B_CUSTOMERS = "b2b_customers"
    CONSUMERS = "consumers"
    VULNERABLE_POPULATIONS = "vulnerable_populations"
    REGULATED_POPULATIONS = "regulated_populations"


class BusinessImpactTier(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class Reversibility(str, Enum):
    FULLY_REVERSIBLE = "fully_reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class Sponsor(BaseModel):
    business_unit: str = Field(..., min_length=1, max_length=200)
    owner: str = Field(..., min_length=1, max_length=200)


class AISystemCharacteristics(BaseModel):
    type: AISystemType
    autonomy_level: AutonomyLevel
    hitl_planned: HITLPlanned
    hitl_description: Optional[str] = Field(None, max_length=2000)


class DataCharacteristics(BaseModel):
    sources: list[str] = Field(..., min_length=1)
    sensitivity: list[DataSensitivity] = Field(..., min_length=1)
    jurisdictions: list[str] = Field(..., min_length=1)  # e.g. "US-CO", "EU", "US-NY"


class ImpactCharacteristics(BaseModel):
    user_scope: list[UserScope] = Field(..., min_length=1)
    business_impact_tier: BusinessImpactTier
    estimated_dollar_impact: Optional[Decimal] = None
    reversibility: Reversibility


class IntakeMetadata(BaseModel):
    """
    Meta-information about how the intake was conducted. Required for
    replay and audit.
    """
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    unknowns: list[str] = Field(default_factory=list)  # field names left unknown
    intake_duration_minutes: float = Field(..., ge=0)
    interview_transcript_ref: Optional[str] = None
    adversarial_flag: bool = False
    adversarial_reason: Optional[str] = None
    intake_agent_version: str
    prompt_manifest_sha: str  # git SHA of the prompt at intake time


class Initiative(BaseModel):
    """
    The canonical representation of an AI initiative. Output of
    Onboarding Intake Agent.
    """
    initiative_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Section A — basics
    name: str = Field(..., min_length=3, max_length=200)
    sponsor: Sponsor
    description: str = Field(..., min_length=10, max_length=2000)
    target_deployment_date: Optional[date] = None

    # Section B — AI system
    ai_system: AISystemCharacteristics

    # Section C — data
    data: DataCharacteristics

    # Section D — impact
    impact: ImpactCharacteristics

    # Section E — existing governance
    existing_controls: list[str] = Field(default_factory=list)
    third_party_vendors: list[str] = Field(default_factory=list)

    # Meta
    intake_metadata: IntakeMetadata

    @field_validator("target_deployment_date")
    @classmethod
    def deployment_date_not_in_past(cls, v: Optional[date]) -> Optional[date]:
        if v and v < date.today():
            raise ValueError("target_deployment_date cannot be in the past")
        return v
