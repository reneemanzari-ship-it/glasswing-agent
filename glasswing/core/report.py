"""ReportArtifact — a generated client-facing deliverable.

The renderer that produces these (glasswing/reporting/) lands Week 6. The
model exists in Week 1 so report_artifacts is a stable table from day one.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReportArtifactType(str, Enum):
    TEARDOWN = "teardown"
    MONITORING_BRIEF = "monitoring_brief"
    REGULATOR_PACKET = "regulator_packet"


class ReportArtifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    type: ReportArtifactType
    path: str = Field(..., min_length=1)
    file_hash: str = Field(..., min_length=1)
    inputs_snapshot: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
