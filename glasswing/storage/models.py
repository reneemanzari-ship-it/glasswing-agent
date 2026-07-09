"""SQLAlchemy ORM models for the Week 1 tables (GLASSWING_SPEC.md section
2.6). Alembic migrations in glasswing/storage/migrations/ own the schema
these models describe; mirrored, I/O-free versions of the same entities
live in glasswing/core/ as Pydantic models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class EngagementRow(Base):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    data_dir: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class GovernanceProfileRow(Base):
    __tablename__ = "governance_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id"), nullable=False
    )
    applicable_frameworks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    risk_appetite: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    internal_policy_refs: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )


class InitiativeRow(Base):
    __tablename__ = "initiatives"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    modality: Mapped[str] = mapped_column(String(100), nullable=False)
    autonomy_level: Mapped[str] = mapped_column(String(100), nullable=False)
    data_categories: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    deployment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hitl_planned: Mapped[str] = mapped_column(String(50), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class EvidenceRecordRow(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("initiatives.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_document_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    citations: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_human_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    confirmed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class RiskProfileRow(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("initiatives.id"), nullable=False
    )
    per_framework_results: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    overall_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    human_review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    framework_versions: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    input_evidence_hashes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class ControlPrescriptionRow(Base):
    __tablename__ = "control_prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    risk_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("risk_profiles.id"), nullable=False
    )
    controls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    library_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class ControlStatusRow(Base):
    __tablename__ = "control_status"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("control_prescriptions.id"), nullable=False
    )
    control_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="prescribed"
    )
    evidence_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    waiver_rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    waiver_signer: Mapped[str | None] = mapped_column(String, nullable=True)


class ApprovalDecisionRow(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("initiatives.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signer_role: Mapped[str] = mapped_column(String(200), nullable=False)
    rationale: Mapped[str] = mapped_column(String(2000), nullable=False)
    packet_hash: Mapped[str] = mapped_column(String, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class AuditEntryRow(Base):
    __tablename__ = "audit_entries"
    __table_args__ = (
        UniqueConstraint(
            "engagement_id", "seq", name="uq_audit_entries_engagement_seq"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_chain_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class RunLedgerRow(Base):
    __tablename__ = "run_ledger"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id"), nullable=False
    )
    pipeline_step: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    framework_versions: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReportArtifactRow(Base):
    __tablename__ = "report_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("engagements.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
