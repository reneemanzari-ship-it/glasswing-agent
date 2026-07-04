import pytest
from datetime import date
from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.risk_profile import EUAIActTier, OverallRiskTier
from skills.ai_risk_tier_classification.scripts.classifier import local_classify

def test_risk_classification_high_employment():
    init = Initiative(
        name="Talent Vetting Assistant",
        sponsor=Sponsor(business_unit="Human Resources", owner="Jane Doe"),
        description="Scrapes candidate CVs and ranks them for positions.",
        target_deployment_date=date.today(),
        ai_system=AISystemCharacteristics(
            type=AISystemType.LLM,
            autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
            hitl_planned=HITLPlanned.YES,
            hitl_description="HR recruits vet candidate resume scoring."
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
            completeness_score=0.9,
            intake_duration_minutes=15.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        )
    )
    profile = local_classify(init)
    assert profile.classifications.eu_ai_act.tier == EUAIActTier.HIGH_RISK
    assert profile.classifications.colorado_sb_205.applicable is True
    assert profile.classifications.colorado_sb_205.high_risk_category == "employment"
    assert profile.overall_risk_tier == OverallRiskTier.HIGH

def test_risk_classification_minimal():
    init = Initiative(
        name="Spam Filter v2",
        sponsor=Sponsor(business_unit="IT Systems", owner="Bob Tech"),
        description="Removes spam emails based on static keyword matching rules.",
        target_deployment_date=date.today(),
        ai_system=AISystemCharacteristics(
            type=AISystemType.OTHER,
            autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS,
            hitl_planned=HITLPlanned.NO,
            hitl_description=None
        ),
        data=DataCharacteristics(
            sources=["email headers"],
            sensitivity=[DataSensitivity.NONE],
            jurisdictions=["US-NY"]
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.INTERNAL_EMPLOYEES],
            business_impact_tier=BusinessImpactTier.LOW,
            reversibility=Reversibility.FULLY_REVERSIBLE
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=1.0,
            intake_duration_minutes=5.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        )
    )
    profile = local_classify(init)
    assert profile.classifications.eu_ai_act.tier == EUAIActTier.MINIMAL_RISK
    assert profile.classifications.colorado_sb_205.applicable is False
    assert profile.overall_risk_tier == OverallRiskTier.LOW
