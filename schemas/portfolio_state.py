"""
PortfolioState schema — aggregate portfolio state.

Maintained by Portfolio Manager Agent in SQLite. The source of truth
for "what's in flight, what's parked, what's been approved" across the
organization.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


class InitiativeStatus(str, Enum):
    INTAKE = "intake"
    CLASSIFICATION_PENDING = "classification_pending"
    CONTROL_PRESCRIPTION_PENDING = "control_prescription_pending"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    APPROVED_FOR_BUILD = "approved_for_build"
    IN_BUILD = "in_build"
    AWAITING_DEPLOYMENT_GATE = "awaiting_deployment_gate"
    DEPLOYED = "deployed"
    REQUIRES_REVISION = "requires_revision"
    REQUIRES_REVISION_BEFORE_APPROVAL = "requires_revision_before_approval"
    PARKED = "parked"
    KILLED = "killed"


class StateTransition(BaseModel):
    initiative_id: UUID
    previous_state: InitiativeStatus
    new_state: InitiativeStatus
    transitioned_at: datetime
    transitioned_by: str  # agent ID or role
    rationale: str = Field(..., min_length=10, max_length=2000)


class InitiativeSummary(BaseModel):
    """
    A single initiative's place in the portfolio, used for reports.
    """
    initiative_id: UUID
    name: str
    sponsor_business_unit: str
    sponsor_owner: str
    current_status: InitiativeStatus
    overall_risk_tier: Optional[str] = None  # from RiskProfile if classified
    target_deployment_date: Optional[date] = None
    last_updated: Optional[datetime] = None
    days_in_current_state: int = Field(..., ge=0)
    next_required_action: Optional[str] = None
    next_action_owner: Optional[str] = None
    next_action_due: Optional[date] = None
    blocking: bool = False  # is anyone waiting on this?


class PortfolioState(BaseModel):
    """
    A snapshot of the portfolio at a point in time. Used for executive
    briefings and dashboards.
    """
    snapshot_id: UUID
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_initiatives: int = Field(..., ge=0)
    by_status: dict[InitiativeStatus, int] = Field(default_factory=dict)
    high_risk_count: int = Field(..., ge=0)
    deployed_count: int = Field(..., ge=0)
    summaries: list[InitiativeSummary] = Field(default_factory=list)  # every initiative in the portfolio
    at_risk_of_missing_deadline: list[InitiativeSummary] = Field(default_factory=list)
    recent_transitions_7d: list[StateTransition] = Field(default_factory=list)
    bottlenecks: list[InitiativeSummary] = Field(default_factory=list)  # stuck > 14d
