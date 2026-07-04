import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from pydantic import ValidationError

# Import all models and enums from schemas package
from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.risk_profile import (
    RiskProfile, Classifications, EUAIActClassification, EUAIActTier,
    NISTAIRMFClassification, NISTAttentionLevel, ColoradoSB205Classification,
    OverallRiskTier
)
from schemas.control_prescription import (
    ControlPrescription, Controls, DeploymentGate, ImplementationEffort,
    Guardrail, HITLTouchpoint, MonitoringRequirement, AuditArtifactRequirement,
    RegulatorySubmission, IndependentReview, ControlCategory, SourceFramework
)
from schemas.governance_manifest import GovernanceManifest, ManifestStatus
from schemas.portfolio_state import PortfolioState, StateTransition, InitiativeSummary, InitiativeStatus
from schemas.audit_log import AuditLogEntry, AgentID, ActionType, SensitivityClassification

# --- 1. INITIATIVE SCHEMA TESTS ---
def test_initiative_schema_validation():
    initiative_id = uuid4()
    
    # Valid Initiative Example
    valid_data = {
        "initiative_id": initiative_id,
        "name": "Applicant Screening System",
        "sponsor": {
            "business_unit": "Human Resources",
            "owner": "Jane Doe"
        },
        "description": "Automated recruitment ranking and CV parser tool.",
        "target_deployment_date": date.today(),
        "ai_system": {
            "type": AISystemType.LLM,
            "autonomy_level": AutonomyLevel.RECOMMEND_ONLY,
            "hitl_planned": HITLPlanned.YES,
            "hitl_description": "HR Specialist signs off on rankings."
        },
        "data": {
            "sources": ["Uploaded PDF Resumes", "LinkedIn Profiles"],
            "sensitivity": [DataSensitivity.PII],
            "jurisdictions": ["US-CO"]
        },
        "impact": {
            "user_scope": [UserScope.INTERNAL_EMPLOYEES],
            "business_impact_tier": BusinessImpactTier.MODERATE,
            "estimated_dollar_impact": Decimal("50000.00"),
            "reversibility": Reversibility.FULLY_REVERSIBLE
        },
        "existing_controls": [],
        "third_party_vendors": [],
        "intake_metadata": {
            "completeness_score": 0.95,
            "unknowns": [],
            "intake_duration_minutes": 15.5,
            "interview_transcript_ref": "transcript-100",
            "adversarial_flag": False,
            "intake_agent_version": "1.0.0",
            "prompt_manifest_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        }
    }
    
    init = Initiative(**valid_data)
    assert init.name == "Applicant Screening System"
    
    # Invalid Initiative Example (target_deployment_date in the past)
    invalid_data = valid_data.copy()
    invalid_data["target_deployment_date"] = date(2020, 1, 1)
    
    with pytest.raises(ValidationError) as exc:
        Initiative(**invalid_data)
    assert "target_deployment_date cannot be in the past" in str(exc.value)


# --- 2. RISK PROFILE SCHEMA TESTS ---
def test_risk_profile_schema_validation():
    init_id = uuid4()
    
    # Valid RiskProfile Example
    valid_data = {
        "risk_profile_id": uuid4(),
        "initiative_id": init_id,
        "classifications": {
            "eu_ai_act": {
                "citations": ["Annex III.4"],
                "rationale": "Used in employment recruitment evaluation.",
                "confidence": 0.90,
                "tier": EUAIActTier.HIGH_RISK,
                "applicable_annexes": ["Annex III"]
            },
            "nist_ai_rmf": {
                "citations": ["MAP-2", "GOVERN-1"],
                "rationale": "High Stakes decision with bias monitoring goals.",
                "confidence": 0.85,
                "govern_attention": NISTAttentionLevel.ROUTINE,
                "map_attention": NISTAttentionLevel.CRITICAL,
                "measure_attention": NISTAttentionLevel.ELEVATED,
                "manage_attention": NISTAttentionLevel.CRITICAL,
                "critical_categories": ["MP-5"]
            },
            "colorado_sb_205": {
                "citations": ["C.R.S. § 6-1-1701"],
                "rationale": "Makes consequential decisions regarding employment opportunity.",
                "confidence": 0.95,
                "applicable": True,
                "high_risk_category": "employment"
            }
        },
        "overall_risk_tier": OverallRiskTier.HIGH,
        "regulatory_exposure_summary": "High risk exposure under EU AI Act and Colorado SB 205.",
        "classifier_agent_version": "1.0.0",
        "prompt_manifest_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "mcp_server_version": "1.0.0",
        "model_id": "claude-sonnet-4-5-20250115"
    }
    
    profile = RiskProfile(**valid_data)
    assert profile.overall_risk_tier == OverallRiskTier.HIGH
    assert profile.human_review_required is False
    
    # Invalid RiskProfile Example (Colorado high_risk_category missing when applicable=True)
    invalid_data = valid_data.copy()
    invalid_data["classifications"] = valid_data["classifications"].copy()
    invalid_data["classifications"]["colorado_sb_205"] = {
        "citations": ["C.R.S. § 6-1-1701"],
        "rationale": "Makes decisions.",
        "confidence": 0.95,
        "applicable": True,
        "high_risk_category": None # Violates validator
    }
    
    with pytest.raises(ValidationError) as exc:
        RiskProfile(**invalid_data)
    assert "high_risk_category required when applicable=True" in str(exc.value)


# --- 3. CONTROL PRESCRIPTION SCHEMA TESTS ---
def test_control_prescription_schema_validation():
    init_id = uuid4()
    profile_id = uuid4()
    
    # Valid ControlPrescription Example
    valid_data = {
        "control_prescription_id": uuid4(),
        "initiative_id": init_id,
        "risk_profile_id": profile_id,
        "risk_tier_assessed": "high",
        "controls": {
            "guardrails": [
                {
                    "control_id": "GR-0001",
                    "category": ControlCategory.INPUT_VALIDATION,
                    "description": "Checks incoming resumes for standard schema matching.",
                    "implementation_notes": "Use regex patterns and parser exception filters.",
                    "mandatory": True,
                    "source_framework": [SourceFramework.INTERNAL_POLICY],
                    "source_citation": "Internal Security Policy 4.2"
                }
            ],
            "hitl_touchpoints": [
                {
                    "control_id": "HITL-0001",
                    "trigger_description": "Manual reviewer approval on rankings.",
                    "reviewer_role": "Recruiting Lead",
                    "review_sla_hours": 24,
                    "mandatory": True,
                    "source_framework": [SourceFramework.EU_AI_ACT]
                }
            ],
            "monitoring": [],
            "audit_artifacts": [],
            "regulatory_submissions": [],
            "independent_review": []
        },
        "deployment_gate": {
            "approvers_required": ["Chief Legal Officer", "HR Director"],
            "pre_deployment_artifacts_required": ["Model Card", "Fairness Assessment"]
        },
        "estimated_implementation_effort": {
            "engineering_weeks": 2.5,
            "governance_team_weeks": 1.0,
            "external_review_cost_estimate_usd": Decimal("15000.00")
        },
        "executive_summary": "Prescribed input validation guardrails and mandatory HR sign-off touchpoints.",
        "prescription_agent_version": "1.0.0",
        "prompt_manifest_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "model_id": "claude-sonnet-4-5-20250115"
    }
    
    presc = ControlPrescription(**valid_data)
    assert presc.controls.guardrails[0].control_id == "GR-0001"
    
    # Invalid ControlPrescription Example (Invalid guardrail ID pattern)
    invalid_data = valid_data.copy()
    invalid_data["controls"] = valid_data["controls"].copy()
    invalid_data["controls"]["guardrails"] = [
        {
            "control_id": "INVALID-ID", # Violates GR-\d{4} pattern
            "category": ControlCategory.INPUT_VALIDATION,
            "description": "Checks incoming resumes for schema matching.",
            "implementation_notes": "Use regex patterns and parser exception filters.",
            "mandatory": True,
            "source_framework": [SourceFramework.INTERNAL_POLICY],
            "source_citation": "Internal Security Policy 4.2"
        }
    ]
    
    with pytest.raises(ValidationError) as exc:
        ControlPrescription(**invalid_data)
    assert "string_pattern_mismatch" in str(exc.value) or "control_id" in str(exc.value)


# --- 4. GOVERNANCE MANIFEST SCHEMA TESTS ---
def test_governance_manifest_schema_validation():
    init_id = uuid4()
    
    # Valid GovernanceManifest Example
    valid_data = {
        "manifest_id": uuid4(),
        "manifest_version": 1,
        "initiative_id": init_id,
        "status": ManifestStatus.DRAFT,
        "initiative_ref": uuid4(),
        "risk_profile_ref": uuid4(),
        "control_prescription_ref": uuid4(),
        "initiative_hash": "a" * 64,
        "risk_profile_hash": "b" * 64,
        "control_prescription_hash": "c" * 64,
        "manifest_hash": "d" * 64,
        "executive_summary": "Consolidated governance manifest defining classifications and requirements.",
        "deployment_readiness": {"controls_implemented": False, "approvers_signed_off": False}
    }
    
    manifest = GovernanceManifest(**valid_data)
    assert manifest.manifest_version == 1
    
    # Invalid GovernanceManifest Example (Manifest hash has incorrect length)
    invalid_data = valid_data.copy()
    invalid_data["manifest_hash"] = "short-hash" # Less than 64 characters
    
    with pytest.raises(ValidationError):
        GovernanceManifest(**invalid_data)


# --- 5. PORTFOLIO STATE SCHEMA TESTS ---
def test_portfolio_state_schema_validation():
    init_id = uuid4()
    
    # Valid PortfolioState Example
    valid_data = {
        "snapshot_id": uuid4(),
        "total_initiatives": 1,
        "by_status": {
            InitiativeStatus.INTAKE: 1,
            InitiativeStatus.DEPLOYED: 0
        },
        "high_risk_count": 0,
        "deployed_count": 0,
        "at_risk_of_missing_deadline": [],
        "recent_transitions_7d": [
            {
                "initiative_id": init_id,
                "previous_state": InitiativeStatus.INTAKE,
                "new_state": InitiativeStatus.CLASSIFICATION_PENDING,
                "transitioned_at": datetime.utcnow(),
                "transitioned_by": "onboarding_intake",
                "rationale": "Initial onboarding completed successfully."
            }
        ],
        "bottlenecks": []
    }
    
    state = PortfolioState(**valid_data)
    assert state.total_initiatives == 1
    
    # Invalid PortfolioState Example (Negative count)
    invalid_data = valid_data.copy()
    invalid_data["total_initiatives"] = -5
    
    with pytest.raises(ValidationError):
        PortfolioState(**invalid_data)


# --- 6. AUDIT LOG ENTRY SCHEMA TESTS ---
def test_audit_log_schema_validation():
    init_id = uuid4()
    
    # Valid AuditLogEntry Example
    valid_data = {
        "audit_log_id": uuid4(),
        "agent_id": AgentID.ONBOARDING_INTAKE,
        "agent_version": "1.0.0",
        "action_type": ActionType.INTAKE_COMPLETED,
        "initiative_id": init_id,
        "model_id": "claude-sonnet-4-5-20250115",
        "prompt_manifest_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "input_hash": "e" * 64,
        "output_hash": "f" * 64,
        "duration_ms": 1200,
        "sensitivity_classification": SensitivityClassification.INTERNAL,
        "chain_hash": "0" * 64,
        "public_context": "Onboarding transcript submitted"
    }
    
    entry = AuditLogEntry(**valid_data)
    assert entry.agent_id == AgentID.ONBOARDING_INTAKE
    
    # Invalid AuditLogEntry Example (Public context containing PII markers)
    invalid_data = valid_data.copy()
    invalid_data["public_context"] = "Submitted by user@domain.com" # Contains '@'
    
    with pytest.raises(ValidationError) as exc:
        AuditLogEntry(**invalid_data)
    assert "appears to contain sensitive marker" in str(exc.value)
