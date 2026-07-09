"""EvidenceRecord — one piece of evidence backing an initiative's intake.

Populated by the questionnaire engine (Week 3) and the Evidence Extraction
Agent (Week 4). The model exists in Week 1 only so the table and its
downstream foreign keys are stable; no producer writes rows yet.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EvidenceSourceType(str, Enum):
    QUESTIONNAIRE = "questionnaire"
    MODEL_CARD = "model_card"
    THIRD_PARTY_ASSESSMENT = "third_party_assessment"
    REGISTRY = "registry"
    MANUAL = "manual"


class EvidenceRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    initiative_id: UUID
    source_type: EvidenceSourceType
    content: dict[str, Any] = Field(default_factory=dict)
    source_document_hash: str | None = None
    citations: dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_human_confirmation: bool = False
    confirmed_by: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
