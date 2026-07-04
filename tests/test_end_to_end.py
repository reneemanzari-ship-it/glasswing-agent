"""
Full pipeline end-to-end test: the 2:47am autonomous consumer loan
scenario, run through all five Glasswing governance agents.

Unlike tests/test_flow.py (which spot-checks the risk classification
output), this test verifies the *entire* handoff chain: intake -> risk
classification -> control prescription -> portfolio registration ->
audit trail, including the specific mandatory controls a fully
autonomous, no-HITL, high-dollar consumer lending system must carry.
"""
import json
import time
from pathlib import Path
from datetime import date

from orchestration.flow import GlasswingGovernanceOrchestrator
from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.risk_profile import EUAIActTier, NISTAttentionLevel
from schemas.governance_manifest import GovernanceManifest
from schemas.portfolio_state import InitiativeStatus
from schemas.control_prescription import ControlCategory
from agents.audit_trail import AUDIT_LOG_DB, verify_audit_log_chain
from agents.portfolio_manager import query_sqlite_data


def _safe_unlink(path: Path):
    """Best-effort cleanup. On Windows, sqlite3 connections opened via a
    `with` block can hold the OS-level file handle open briefly after the
    block exits, so an immediate unlink can raise PermissionError even
    though the test itself passed. Retry briefly rather than letting
    cleanup noise mask a real result."""
    for _ in range(5):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            time.sleep(0.2)


def test_247am_loan_scenario_full_pipeline():
    test_db = "glasswing_test_e2e_loan.db"
    db_path = Path(test_db)
    _safe_unlink(db_path)

    try:
        orchestrator = GlasswingGovernanceOrchestrator(db_url=f"sqlite:///{test_db}")

        loan_initiative = Initiative(
            name="LendFast Autonomous Underwriter",
            sponsor=Sponsor(business_unit="Retail Lending Division", owner="Alex Credit-Lead"),
            description=(
                "Autonomous credit evaluation and underwriting system that approves "
                "consumer loans without human review at 2:47 AM."
            ),
            target_deployment_date=date.today(),
            ai_system=AISystemCharacteristics(
                type=AISystemType.CLASSICAL_ML,
                autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS,
                hitl_planned=HITLPlanned.NO,
                hitl_description=None
            ),
            data=DataCharacteristics(
                sources=["credit scores bureau history", "financial transaction lists"],
                sensitivity=[DataSensitivity.FINANCIAL, DataSensitivity.PII],
                jurisdictions=["US-CO", "EU"]
            ),
            impact=ImpactCharacteristics(
                user_scope=[UserScope.CONSUMERS],
                business_impact_tier=BusinessImpactTier.HIGH,
                reversibility=Reversibility.PARTIALLY_REVERSIBLE
            ),
            intake_metadata=IntakeMetadata(
                completeness_score=0.90,
                intake_duration_minutes=12.5,
                intake_agent_version="1.0.0",
                prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            )
        )
        initiative_id = loan_initiative.initiative_id

        # --- Run the full pipeline ---
        manifest, chain_verified = orchestrator.evaluate_new_initiative(loan_initiative)

        # --- 1. All five agents executed, in order ---
        entries = [e for e in AUDIT_LOG_DB if e["initiative_id"] == initiative_id]
        expected_order = [
            "onboarding_intake", "risk_classifier", "control_prescription",
            "portfolio_manager", "audit_trail",
        ]
        actual_order = [e["agent_id"].value for e in entries]
        assert actual_order == expected_order, f"expected {expected_order}, got {actual_order}"

        # --- 2. Risk Classifier output ---
        risk_profile = orchestrator.risk_classifier.classify_initiative(loan_initiative)
        assert risk_profile.classifications.eu_ai_act.tier == EUAIActTier.HIGH_RISK
        assert risk_profile.classifications.nist_ai_rmf.manage_attention == NISTAttentionLevel.CRITICAL
        assert risk_profile.classifications.colorado_sb_205.applicable is True
        assert risk_profile.classifications.colorado_sb_205.high_risk_category == "financial_lending"

        # --- 3. Control Prescription output ---
        control_prescription = orchestrator.control_prescriber.prescribe_controls(risk_profile)

        mandatory_hitl = [t for t in control_prescription.controls.hitl_touchpoints if t.mandatory]
        assert any(
            t.trigger_quantitative and "500000" in t.trigger_quantitative for t in mandatory_hitl
        ), "expected a mandatory HITL touchpoint triggered above $500,000"

        confidence_guardrails = [
            g for g in control_prescription.controls.guardrails
            if g.category == ControlCategory.CONFIDENCE_THRESHOLD
        ]
        assert any("0.95" in g.description or "0.95" in g.implementation_notes for g in confidence_guardrails), (
            "expected a confidence-threshold guardrail citing 0.95"
        )

        realtime_monitoring = [
            m for m in control_prescription.controls.monitoring if m.cadence == "real-time"
        ]
        assert len(realtime_monitoring) >= 1, "expected a real-time monitoring requirement"

        seven_year_audit = [
            a for a in control_prescription.controls.audit_artifacts if a.retention_years == 7
        ]
        assert len(seven_year_audit) >= 1, "expected a 7-year audit artifact retention requirement"

        # --- 4. GovernanceManifest created and validates ---
        assert isinstance(manifest, GovernanceManifest)
        revalidated = GovernanceManifest.model_validate(manifest.model_dump())
        assert revalidated.initiative_id == initiative_id

        # --- 5. Portfolio state shows requires-revision-before-approval ---
        status_row = json.loads(
            query_sqlite_data("SELECT status FROM initiatives WHERE id = ?", (str(initiative_id),))
        )
        assert len(status_row) == 1
        assert status_row[0]["status"] == InitiativeStatus.REQUIRES_REVISION_BEFORE_APPROVAL.value

        # --- 6. Audit log has entries from all five agents with valid chain hashes ---
        assert len(entries) == 5
        assert chain_verified is True
        assert "SUCCESS" in verify_audit_log_chain()

    finally:
        _safe_unlink(db_path)
