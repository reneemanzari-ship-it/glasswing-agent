"""Engagement and GovernanceProfile — the top-level scope for everything
else in the system (GLASSWING_SPEC.md section 2.3: "Engagement is the
top-level entity and every record is scoped to one")."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PinnedFramework(BaseModel):
    """One framework a governance profile applies, pinned to the dataset
    version in effect when the profile was set — so a classification made
    under this profile can always be traced back to the exact framework
    text it used."""

    framework_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)


class Engagement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_name: str = Field(..., min_length=1, max_length=200)
    sector: str = Field(..., min_length=1, max_length=100)
    jurisdictions: list[str] = Field(..., min_length=1)
    status: str = Field(default="active", min_length=1, max_length=50)
    data_dir: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GovernanceProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    applicable_frameworks: list[PinnedFramework] = Field(default_factory=list)
    risk_appetite: dict[str, Any] = Field(default_factory=dict)
    internal_policy_refs: list[str] = Field(default_factory=list)
