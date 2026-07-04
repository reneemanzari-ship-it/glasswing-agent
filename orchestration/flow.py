import sys
import uuid
import json
import hashlib
from pathlib import Path
from typing import Tuple, Any
from pydantic import BaseModel

sys.path.append(str(Path(__file__).parent.parent))

# Import required Pydantic schemas and enums
from schemas.initiative import Initiative
from schemas.governance_manifest import GovernanceManifest
from schemas.portfolio_state import InitiativeStatus
from schemas.audit_log import AgentID, ActionType

# Import enums and classes from schemas.risk_profile as requested
from schemas.risk_profile import (
    EUAIActTier, 
    NISTAttentionLevel, 
    OverallRiskTier, 
    ColoradoSB205Classification
)

from agents.onboarding_intake import OnboardingIntakeAgent
from agents.risk_classifier import RiskClassifierAgent
from agents.control_prescription import ControlPrescriptionAgent
from agents.portfolio_manager import PortfolioManagerAgent
from agents.audit_trail import AuditTrailAgent

# Define helper Pydantic models for input/output logging to guarantee model_dump_json() usage
class OnboardingInput(BaseModel):
    name: str
    description: str
    sponsor_business_unit: str
    sponsor_owner: str

class TransitionInput(BaseModel):
    initiative_id: str
    assigned_status: str

class AuditInput(BaseModel):
    verify_request: str

class AuditOutput(BaseModel):
    chain_integrity_verified: bool
    verify_result: str

def _get_sha256(json_str: str) -> str:
    """Helper to compute sha256 hash of a Pydantic model_dump_json string."""
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

class GlasswingGovernanceOrchestrator:
    def __init__(self, db_url: str = None):
        self.db_url = db_url
        self.intake_agent = OnboardingIntakeAgent()
        self.risk_classifier = RiskClassifierAgent()
        self.control_prescriber = ControlPrescriptionAgent()
        self.portfolio_manager = PortfolioManagerAgent(db_url=self.db_url)
        self.audit_trail = AuditTrailAgent()

    def evaluate_new_initiative(self, initiative: Initiative) -> Tuple[GovernanceManifest, bool]:
        """Runs the sequential multi-agent governance workflow for a given Initiative.
        Returns the finalized GovernanceManifest and a boolean representing audit verification success.
        """
        initiative_id = initiative.initiative_id

        # --- PHASE 1: Intake Onboarding Logging ---
        onboarding_input = OnboardingInput(
            name=initiative.name,
            description=initiative.description,
            sponsor_business_unit=initiative.sponsor.business_unit,
            sponsor_owner=initiative.sponsor.owner
        )
        input_hash = _get_sha256(onboarding_input.model_dump_json())
        output_hash = _get_sha256(initiative.model_dump_json())
        
        # Halt flow immediately if adversarial flag is active
        if initiative.intake_metadata.adversarial_flag:
            self.audit_trail.log_event(
                agent_id=AgentID.ONBOARDING_INTAKE,
                action_type=ActionType.SECURITY_FLAG_RAISED,
                initiative_id=initiative_id,
                input_hash=input_hash,
                output_hash=output_hash,
                public_context=f"Security Halt: Onboarding blocked due to adversarial input."
            )
            raise ValueError(f"Security Halt: Onboarding blocked due to adversarial input. Reason: {initiative.intake_metadata.adversarial_reason}")

        self.audit_trail.log_event(
            agent_id=AgentID.ONBOARDING_INTAKE,
            action_type=ActionType.INTAKE_COMPLETED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Onboarded initiative: '{initiative.name}'"
        )

        # --- PHASE 2: Risk Classification ---
        risk_profile = self.risk_classifier.classify_initiative(initiative)
        
        # Log Classification action
        input_hash = _get_sha256(initiative.model_dump_json())
        output_hash = _get_sha256(risk_profile.model_dump_json())
        
        self.audit_trail.log_event(
            agent_id=AgentID.RISK_CLASSIFIER,
            action_type=ActionType.CLASSIFICATION_COMPLETED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Classified overall risk as: {risk_profile.overall_risk_tier.value}"
        )

        # --- PHASE 3: Control Prescription ---
        control_prescription = self.control_prescriber.prescribe_controls(risk_profile)
        
        # Log Control Prescription action
        input_hash = _get_sha256(risk_profile.model_dump_json())
        output_hash = _get_sha256(control_prescription.model_dump_json())
        
        self.audit_trail.log_event(
            agent_id=AgentID.CONTROL_PRESCRIPTION,
            action_type=ActionType.PRESCRIPTION_COMPLETED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Prescribed {len(control_prescription.controls.guardrails)} guardrail(s)"
        )

        # --- PHASE 4: Portfolio Registration & Canonical State ---
        manifest = self.portfolio_manager.register_initiative(
            initiative=initiative,
            risk_profile=risk_profile,
            control_prescription=control_prescription,
            transitioned_by="portfolio_manager"
        )
        
        # Log State Transition action
        assigned_status = (
            InitiativeStatus.CONTROL_PRESCRIPTION_PENDING.value
            if risk_profile.overall_risk_tier in [OverallRiskTier.HIGH, OverallRiskTier.CRITICAL]
            else InitiativeStatus.APPROVED_FOR_BUILD.value
        )
        
        transition_input = TransitionInput(
            initiative_id=str(initiative_id),
            assigned_status=assigned_status
        )
        input_hash = _get_sha256(transition_input.model_dump_json())
        output_hash = _get_sha256(manifest.model_dump_json())
        
        self.audit_trail.log_event(
            agent_id=AgentID.PORTFOLIO_MANAGER,
            action_type=ActionType.STATE_TRANSITIONED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Transitioned initiative status to: {assigned_status}"
        )

        # --- PHASE 5: Cryptographic Verification Check ---
        verify_result = self.audit_trail.verify_trail()
        is_chain_valid = "CORRUPTION_DETECTED" not in verify_result
        
        audit_input = AuditInput(verify_request="all_entries")
        audit_output = AuditOutput(chain_integrity_verified=is_chain_valid, verify_result=verify_result)
        
        input_hash = _get_sha256(audit_input.model_dump_json())
        output_hash = _get_sha256(audit_output.model_dump_json())
        
        self.audit_trail.log_event(
            agent_id=AgentID.AUDIT_TRAIL,
            action_type=ActionType.REPLAY_REQUESTED if not is_chain_valid else ActionType.REPORT_GENERATED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Audit chain verification complete: {'PASS' if is_chain_valid else 'FAIL'}"
        )

        return manifest, is_chain_valid

if __name__ == "__main__":
    from datetime import date
    from decimal import Decimal
    from schemas.initiative import Sponsor, AISystemCharacteristics, DataCharacteristics, ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel, HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
    
    orchestrator = GlasswingGovernanceOrchestrator()
    print("Executing sample pipeline for 'Applicant Screening AI'...")
    
    # Construct a structured Initiative parameter directly
    sample_initiative = Initiative(
        name="TalentScan CV Filter",
        sponsor=Sponsor(business_unit="Human Resources", owner="HR Officer"),
        description="Vets and scores job application candidates based on qualifications.",
        target_deployment_date=date.today(),
        ai_system=AISystemCharacteristics(
            type=AISystemType.LLM,
            autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
            hitl_planned=HITLPlanned.YES,
            hitl_description="HR specialists review final scores."
        ),
        data=DataCharacteristics(
            sources=["Resumes PDF"],
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
            intake_duration_minutes=10.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        )
    )
    
    manifest, verified = orchestrator.evaluate_new_initiative(sample_initiative)
    print(f"Workflow Complete!")
    print(f"Assigned Risk Tier: {manifest.risk_profile_ref} -> overall {manifest.executive_summary[:50]}...")
    print(f"Audit Trail Verification: {'VERIFIED' if verified else 'FAILED TAMPERING CHECK'}")
