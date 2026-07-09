"""Initiative — an AI system tracked within an engagement's portfolio.

Week 1 carries the abbreviated field set from GLASSWING_SPEC.md section 2.6.
The richer intake fields (ai_system characteristics, data characteristics,
impact characteristics — see the v0.1 schemas/initiative.py) arrive with the
questionnaire engine in Week 3 as additions to this model, not a rewrite of
it (DECISIONS.md D-002).
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from glasswing.core.lifecycle import LifecycleState


class Initiative(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    modality: str = Field(..., min_length=1, max_length=100)
    autonomy_level: str = Field(..., min_length=1, max_length=100)
    data_categories: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    deployment_date: date | None = None
    hitl_planned: str = Field(..., min_length=1, max_length=50)
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
