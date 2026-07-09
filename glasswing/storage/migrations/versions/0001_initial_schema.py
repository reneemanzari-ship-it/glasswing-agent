"""Initial Week 1 schema: engagements, governance_profiles, initiatives,
evidence_records, risk_profiles, control_prescriptions, control_status,
approval_decisions, audit_entries, run_ledger, report_artifacts.

Revision ID: 0001
Revises:
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("jurisdictions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("data_dir", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "governance_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id", sa.Uuid(), sa.ForeignKey("engagements.id"), nullable=False
        ),
        sa.Column("applicable_frameworks", sa.JSON(), nullable=False),
        sa.Column("risk_appetite", sa.JSON(), nullable=False),
        sa.Column("internal_policy_refs", sa.JSON(), nullable=False),
    )

    op.create_table(
        "initiatives",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id", sa.Uuid(), sa.ForeignKey("engagements.id"), nullable=False
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("modality", sa.String(100), nullable=False),
        sa.Column("autonomy_level", sa.String(100), nullable=False),
        sa.Column("data_categories", sa.JSON(), nullable=False),
        sa.Column("jurisdictions", sa.JSON(), nullable=False),
        sa.Column("deployment_date", sa.Date(), nullable=True),
        sa.Column("hitl_planned", sa.String(50), nullable=False),
        sa.Column("lifecycle_state", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id", sa.Uuid(), sa.ForeignKey("initiatives.id"), nullable=False
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("source_document_hash", sa.String(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("needs_human_confirmation", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "risk_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id", sa.Uuid(), sa.ForeignKey("initiatives.id"), nullable=False
        ),
        sa.Column("per_framework_results", sa.JSON(), nullable=False),
        sa.Column("overall_tier", sa.String(50), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.Column("engine_version", sa.String(50), nullable=False),
        sa.Column("framework_versions", sa.JSON(), nullable=False),
        sa.Column("input_evidence_hashes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "control_prescriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "risk_profile_id",
            sa.Uuid(),
            sa.ForeignKey("risk_profiles.id"),
            nullable=False,
        ),
        sa.Column("controls", sa.JSON(), nullable=False),
        sa.Column("library_version", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "control_status",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "prescription_id",
            sa.Uuid(),
            sa.ForeignKey("control_prescriptions.id"),
            nullable=False,
        ),
        sa.Column("control_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("evidence_ref", sa.String(), nullable=True),
        sa.Column("waiver_rationale", sa.String(), nullable=True),
        sa.Column("waiver_signer", sa.String(), nullable=True),
    )

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "initiative_id", sa.Uuid(), sa.ForeignKey("initiatives.id"), nullable=False
        ),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("signer_name", sa.String(200), nullable=False),
        sa.Column("signer_role", sa.String(200), nullable=False),
        sa.Column("rationale", sa.String(2000), nullable=False),
        sa.Column("packet_hash", sa.String(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id", sa.Uuid(), sa.ForeignKey("engagements.id"), nullable=False
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("prev_chain_hash", sa.String(64), nullable=True),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "engagement_id", "seq", name="uq_audit_entries_engagement_seq"
        ),
    )

    op.create_table(
        "run_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id", sa.Uuid(), sa.ForeignKey("engagements.id"), nullable=False
        ),
        sa.Column("pipeline_step", sa.String(100), nullable=False),
        sa.Column("engine_version", sa.String(50), nullable=True),
        sa.Column("framework_versions", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("model_id", sa.String(100), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("output_hash", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "engagement_id", sa.Uuid(), sa.ForeignKey("engagements.id"), nullable=False
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("inputs_snapshot", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("report_artifacts")
    op.drop_table("run_ledger")
    op.drop_table("audit_entries")
    op.drop_table("approval_decisions")
    op.drop_table("control_status")
    op.drop_table("control_prescriptions")
    op.drop_table("risk_profiles")
    op.drop_table("evidence_records")
    op.drop_table("initiatives")
    op.drop_table("governance_profiles")
    op.drop_table("engagements")
