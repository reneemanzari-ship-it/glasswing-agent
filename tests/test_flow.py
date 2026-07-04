import pytest
from pathlib import Path
from datetime import date
from uuid import uuid4
from orchestration.flow import GlasswingGovernanceOrchestrator
from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.risk_profile import EUAIActTier, NISTAttentionLevel, OverallRiskTier

def test_governance_pipeline_flow():
    test_db = "glasswing_test_temp.db"
    if Path(test_db).exists():
        Path(test_db).unlink()
        
    try:
        orchestrator = GlasswingGovernanceOrchestrator(db_url=f"sqlite:///{test_db}")
        
        # Construct structured Initiative
        initiative = Initiative(
            name="Test Screening Engine",
            sponsor=Sponsor(business_unit="HR Division", owner="Alice Recruiter"),
            description="Automated candidate screening and CV parser assistant.",
            target_deployment_date=date.today(),
            ai_system=AISystemCharacteristics(
                type=AISystemType.LLM,
                autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
                hitl_planned=HITLPlanned.YES,
                hitl_description="HR specialists review candidate listings."
            ),
            data=DataCharacteristics(
                sources=["resumes"],
                sensitivity=[DataSensitivity.PII],
                jurisdictions=["US-CO"]
            ),
            impact=ImpactCharacteristics(
                user_scope=[UserScope.INTERNAL_EMPLOYEES],
                business_impact_tier=BusinessImpactTier.MODERATE,
                reversibility=Reversibility.FULLY_REVERSIBLE
            ),
            intake_metadata=IntakeMetadata(
                completeness_score=0.95,
                intake_duration_minutes=15.0,
                intake_agent_version="1.0.0",
                prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            )
        )
        
        # Execute flow
        manifest, verified = orchestrator.evaluate_new_initiative(initiative)
        
        # Fetch risk profile from SQLite via portfolio manager
        state = orchestrator.portfolio_manager.get_portfolio_state()
        assert state.total_initiatives == 1
        assert state.summaries[0].name == "Test Screening Engine"
        assert verified is True
        
    finally:
        if Path(test_db).exists():
            Path(test_db).unlink()


def test_247am_loan_scenario_flow():
    test_db = "glasswing_test_loan_temp.db"
    if Path(test_db).exists():
        Path(test_db).unlink()
        
    try:
        orchestrator = GlasswingGovernanceOrchestrator(db_url=f"sqlite:///{test_db}")
        
        # 2:47am Autonomous Loan Underwriter Scenario
        loan_initiative = Initiative(
            name="LendFast Autonomous Underwriter",
            sponsor=Sponsor(business_unit="Retail Lending Division", owner="Alex Credit-Lead"),
            description="Autonomous credit evaluation and underwriting system that approves consumer loans without human review at 2:47 AM.",
            target_deployment_date=date.today(),
            ai_system=AISystemCharacteristics(
                type=AISystemType.CLASSICAL_ML,
                autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS, # No Human signoff
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
        
        # Execute flow
        manifest, verified = orchestrator.evaluate_new_initiative(loan_initiative)
        
        # Fetch generated manifest detail from SQLite db
        db_state = orchestrator.portfolio_manager.get_portfolio_state()
        assert db_state.total_initiatives == 1
        
        # Verify specific portfolio SQLite properties
        res_json = orchestrator.portfolio_manager.query_sqlite_data("SELECT manifest_json FROM initiatives WHERE id = ?", (str(loan_initiative.initiative_id),))
        import json
        rows = json.loads(res_json)
        assert len(rows) == 1
        manifest_obj = json.loads(rows[0]["manifest_json"])
        
        # Construct and query RiskProfile details generated for this scenario
        risk_profile = orchestrator.risk_classifier.classify_initiative(loan_initiative)
        
        # Strict Assertions Checklist as required:
        # 1. EU AI Act tier is HIGH_RISK
        assert risk_profile.classifications.eu_ai_act.tier == EUAIActTier.HIGH_RISK
        
        # 2. EU AI Act applicable_annexes references essential services or Annex III(5)(b)
        annexes_str = " ".join(risk_profile.classifications.eu_ai_act.applicable_annexes)
        assert "Annex III(5)(b)" in annexes_str or "essential services" in annexes_str.lower()
        
        # 3. NIST AI RMF manage_attention is CRITICAL
        assert risk_profile.classifications.nist_ai_rmf.manage_attention == NISTAttentionLevel.CRITICAL
        
        # 4. Colorado SB 205 applicable is True with high_risk_category as "financial_lending"
        assert risk_profile.classifications.colorado_sb_205.applicable is True
        assert risk_profile.classifications.colorado_sb_205.high_risk_category == "financial_lending"
        
        # 5. overall_risk_tier is HIGH or CRITICAL
        assert risk_profile.overall_risk_tier in [OverallRiskTier.HIGH, OverallRiskTier.CRITICAL]
        
        # 6. human_review_required is True
        assert risk_profile.human_review_required is True
        
        assert verified is True

    finally:
        if Path(test_db).exists():
            Path(test_db).unlink()
