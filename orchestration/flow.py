import sys
import uuid
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Tuple, Any, Optional, Dict
from pydantic import BaseModel, ValidationError

sys.path.append(str(Path(__file__).parent.parent))

# Import required Pydantic schemas and enums
from schemas.initiative import Initiative
from schemas.governance_manifest import GovernanceManifest
from schemas.portfolio_state import InitiativeStatus
from schemas.audit_log import AgentID, ActionType
from schemas.risk_profile import RiskProfile
from schemas.control_prescription import ControlPrescription

# Import enums and classes from schemas.risk_profile as requested
from schemas.risk_profile import (
    EUAIActTier,
    NISTAttentionLevel,
    ColoradoSB205Classification
)

from agents.onboarding_intake import OnboardingIntakeAgent
from agents.risk_classifier import RiskClassifierAgent
from agents.control_prescription import ControlPrescriptionAgent
from agents.portfolio_manager import PortfolioManagerAgent
from agents.audit_trail import AuditTrailAgent, AUDIT_LOG_DB

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

# Fields that are freshly (re)generated on every construction — a random
# UUID via default_factory=uuid4, or a fresh datetime.utcnow() — even when
# every other field is byte-identical. Hashing these in would make replay
# verification (Capability #2) impossible by construction: the same input,
# run through the same model/prompt version, would never reproduce the
# same output_hash. They're excluded only from the *content* hash used for
# logging/replay comparison — the objects themselves are unchanged.
_VOLATILE_FIELDS_BY_MODEL = {
    "RiskProfile": {"risk_profile_id", "created_at"},
    # risk_profile_id here is a foreign key into RiskProfile, which is
    # itself freshly regenerated every run — exclude it too, or this
    # object's "stable" hash would inherit RiskProfile's volatility.
    "ControlPrescription": {"control_prescription_id", "created_at", "risk_profile_id"},
    "GovernanceManifest": {
        "manifest_id", "created_at", "manifest_hash", "initiative_hash",
        "risk_profile_hash", "control_prescription_hash", "previous_manifest_hash",
        "risk_profile_ref", "control_prescription_ref",
    },
}

def _stable_hash(model: BaseModel) -> str:
    """Content hash used for output_hash logging and replay verification.
    See _VOLATILE_FIELDS_BY_MODEL for why volatile identity/timestamp
    fields are excluded."""
    exclude = _VOLATILE_FIELDS_BY_MODEL.get(type(model).__name__, set())
    data = model.model_dump(mode="json", exclude=exclude)
    return _get_sha256(json.dumps(data, sort_keys=True, default=str))


class GlasswingGovernanceOrchestrator:
    def __init__(self, db_url: str = None):
        self.db_url = db_url
        self.intake_agent = OnboardingIntakeAgent()
        self.risk_classifier = RiskClassifierAgent()
        self.control_prescriber = ControlPrescriptionAgent()
        self.portfolio_manager = PortfolioManagerAgent(db_url=self.db_url)
        self.audit_trail = AuditTrailAgent()

    def _run_phase(self, *, phase_label: str, agent_id: AgentID, initiative_id,
                   input_hash: str, fn, validate_fn):
        """Runs one pipeline phase behind a schema-validation gate and a
        failure boundary.

        - pydantic.ValidationError (raised either by the agent itself, or
          by validate_fn re-validating its output) means the handoff
          produced a structurally invalid object. This must not silently
          continue to the next agent: it's logged as a HUMAN_REVIEW_REQUIRED
          audit event and raised as a distinct "Schema Validation Halt" so
          callers can route the initiative to a human review queue instead
          of treating it as a crash.
        - Any other exception means the agent itself failed. The partial
          state (everything logged up to this point, plus this failure
          event) is written to the audit trail before the original
          exception is re-raised unchanged, so the audit trail always has
          a complete picture up to the point of failure.
        """
        try:
            result = fn()
            return validate_fn(result)
        except ValidationError as ve:
            output_hash = _get_sha256(f"ValidationError: {ve}")
            self.audit_trail.log_event(
                agent_id=agent_id,
                action_type=ActionType.HUMAN_REVIEW_REQUESTED,
                initiative_id=initiative_id,
                input_hash=input_hash,
                output_hash=output_hash,
                public_context=(
                    f"Schema validation gate failed at {phase_label} handoff — "
                    f"routed to human review queue instead of continuing."
                )[:500]
            )
            raise ValueError(
                f"Schema Validation Halt: {phase_label} produced an invalid object "
                f"and was routed to human review instead of continuing. Details: {ve}"
            ) from ve
        except Exception as e:
            output_hash = _get_sha256(f"{type(e).__name__}: {e}")
            self.audit_trail.log_event(
                agent_id=agent_id,
                action_type=ActionType.HUMAN_REVIEW_REQUESTED,
                initiative_id=initiative_id,
                input_hash=input_hash,
                output_hash=output_hash,
                public_context=(
                    f"{phase_label} raised {type(e).__name__} — partial pipeline "
                    f"state logged to audit trail before re-raising."
                )[:500]
            )
            raise

    def evaluate_new_initiative(self, initiative: Initiative) -> Tuple[GovernanceManifest, bool]:
        """Runs the sequential multi-agent governance workflow for a given Initiative.
        Returns the finalized GovernanceManifest and a boolean representing audit verification success.
        """
        initiative_id = initiative.initiative_id

        # --- Schema gate on the handoff INTO the pipeline ---
        initiative = self._run_phase(
            phase_label="Onboarding Intake handoff",
            agent_id=AgentID.ONBOARDING_INTAKE,
            initiative_id=initiative_id,
            input_hash=_get_sha256(initiative.model_dump_json()),
            fn=lambda: initiative,
            validate_fn=lambda r: Initiative.model_validate(r.model_dump()),
        )

        # --- PHASE 1: Intake Onboarding Logging ---
        onboarding_input = OnboardingInput(
            name=initiative.name,
            description=initiative.description,
            sponsor_business_unit=initiative.sponsor.business_unit,
            sponsor_owner=initiative.sponsor.owner
        )
        input_hash = _get_sha256(onboarding_input.model_dump_json())
        output_hash = _stable_hash(initiative)

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
        input_hash = _get_sha256(initiative.model_dump_json())
        risk_profile = self._run_phase(
            phase_label="Risk Classification",
            agent_id=AgentID.RISK_CLASSIFIER,
            initiative_id=initiative_id,
            input_hash=input_hash,
            fn=lambda: self.risk_classifier.classify_initiative(initiative),
            validate_fn=lambda r: RiskProfile.model_validate(r.model_dump()),
        )

        output_hash = _stable_hash(risk_profile)
        self.audit_trail.log_event(
            agent_id=AgentID.RISK_CLASSIFIER,
            action_type=ActionType.CLASSIFICATION_COMPLETED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Classified overall risk as: {risk_profile.overall_risk_tier.value}"
        )

        # --- PHASE 3: Control Prescription ---
        input_hash = _get_sha256(risk_profile.model_dump_json())
        control_prescription = self._run_phase(
            phase_label="Control Prescription",
            agent_id=AgentID.CONTROL_PRESCRIPTION,
            initiative_id=initiative_id,
            input_hash=input_hash,
            fn=lambda: self.control_prescriber.prescribe_controls(risk_profile),
            validate_fn=lambda r: ControlPrescription.model_validate(r.model_dump()),
        )

        output_hash = _stable_hash(control_prescription)
        self.audit_trail.log_event(
            agent_id=AgentID.CONTROL_PRESCRIPTION,
            action_type=ActionType.PRESCRIPTION_COMPLETED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Prescribed {len(control_prescription.controls.guardrails)} guardrail(s)"
        )

        # --- PHASE 4: Portfolio Registration & Canonical State ---
        def _register():
            return self.portfolio_manager.register_initiative(
                initiative=initiative,
                risk_profile=risk_profile,
                control_prescription=control_prescription,
                transitioned_by="portfolio_manager"
            )

        def _validate_registration(result):
            manifest, status, rationale = result
            manifest = GovernanceManifest.model_validate(manifest.model_dump())
            status = InitiativeStatus(status.value)
            if not isinstance(rationale, str) or not rationale.strip():
                raise ValueError("Portfolio Manager returned an empty transition rationale.")
            return manifest, status, rationale

        registration_input_hash = _get_sha256(
            json.dumps(
                {"initiative_id": str(initiative_id), "risk_profile_id": str(risk_profile.risk_profile_id),
                 "control_prescription_id": str(control_prescription.control_prescription_id)},
                sort_keys=True
            )
        )
        manifest, assigned_status, transition_rationale = self._run_phase(
            phase_label="Portfolio Registration",
            agent_id=AgentID.PORTFOLIO_MANAGER,
            initiative_id=initiative_id,
            input_hash=registration_input_hash,
            fn=_register,
            validate_fn=_validate_registration,
        )

        # Log State Transition action — uses the status Portfolio Manager
        # actually persisted, not a separately recomputed guess, so the
        # audit trail can never drift from what's in the portfolio DB.
        transition_input = TransitionInput(
            initiative_id=str(initiative_id),
            assigned_status=assigned_status.value
        )
        input_hash = _get_sha256(transition_input.model_dump_json())
        output_hash = _stable_hash(manifest)

        self.audit_trail.log_event(
            agent_id=AgentID.PORTFOLIO_MANAGER,
            action_type=ActionType.STATE_TRANSITIONED,
            initiative_id=initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Transitioned initiative status to: {assigned_status.value}. {transition_rationale}"[:500]
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

    async def evaluate_new_initiative_async(self, initiative: Initiative) -> Tuple[GovernanceManifest, bool]:
        """Async wrapper for non-blocking use from Streamlit (or any other
        async caller). Runs the sync pipeline in a worker thread so the
        event loop isn't blocked. evaluate_new_initiative() remains the
        single source of truth — tests exercise it directly, synchronously;
        this just schedules it off-thread."""
        return await asyncio.to_thread(self.evaluate_new_initiative, initiative)

    def replay_initiative(self, initiative_id: uuid.UUID, initiative: Initiative) -> Dict[str, Any]:
        """Replay mode — the visible replay capability demonstration.

        This system stores only cryptographic hashes in the audit log, not
        raw agent inputs/outputs, so the caller must supply the original
        Initiative object (retrieved from whatever system of record holds
        it) alongside its historical initiative_id. Given that, this:

        1. Locates the historical audit log entries for initiative_id.
        2. Recomputes the intake input_hash from the supplied initiative
           and verifies it matches the historical one on record — proving
           this really is a replay of the same submission, not a different
           one that happens to share an ID.
        3. Re-runs the full pipeline fresh, using the same model_id /
           prompt_manifest_sha already recorded in the audit log (both are
           fixed per agent version in this system).
        4. Compares each phase's freshly-computed output_hash against the
           historical one and reports whether they match.
        """
        historical = [e for e in AUDIT_LOG_DB if e["initiative_id"] == initiative_id]
        if not historical:
            raise ValueError(f"Replay Halt: no audit log entries found for initiative_id={initiative_id}")

        intake_entry = next((e for e in historical if e["agent_id"] == AgentID.ONBOARDING_INTAKE), None)
        if intake_entry is None:
            raise ValueError(f"Replay Halt: no onboarding_intake entry on record for initiative_id={initiative_id}")

        onboarding_input = OnboardingInput(
            name=initiative.name,
            description=initiative.description,
            sponsor_business_unit=initiative.sponsor.business_unit,
            sponsor_owner=initiative.sponsor.owner
        )
        recomputed_input_hash = _get_sha256(onboarding_input.model_dump_json())
        if recomputed_input_hash != intake_entry["input_hash"]:
            raise ValueError(
                "Replay Halt: supplied initiative does not reproduce the historical "
                f"input_hash (expected {intake_entry['input_hash']}, got "
                f"{recomputed_input_hash}). This is not a replay of the same submission."
            )

        model_id = intake_entry["model_id"]
        prompt_manifest_sha = intake_entry["prompt_manifest_sha"]
        historical_ids = {e["audit_log_id"] for e in historical}

        # Re-run the pipeline fresh, using the same initiative content, the
        # same agent code (hence same model_id/prompt_manifest_sha).
        manifest, chain_verified = self.evaluate_new_initiative(initiative)

        fresh = [e for e in AUDIT_LOG_DB
                 if e["initiative_id"] == initiative_id and e["audit_log_id"] not in historical_ids]

        phase_comparison = []
        for phase_agent in (AgentID.ONBOARDING_INTAKE, AgentID.RISK_CLASSIFIER,
                             AgentID.CONTROL_PRESCRIPTION, AgentID.PORTFOLIO_MANAGER):
            hist_entry = next((e for e in historical if e["agent_id"] == phase_agent), None)
            new_entry = next((e for e in fresh if e["agent_id"] == phase_agent), None)
            match = bool(hist_entry and new_entry and hist_entry["output_hash"] == new_entry["output_hash"])
            phase_comparison.append({
                "agent_id": phase_agent.value,
                "historical_output_hash": hist_entry["output_hash"] if hist_entry else None,
                "replayed_output_hash": new_entry["output_hash"] if new_entry else None,
                "match": match,
            })

        replay_verified = all(p["match"] for p in phase_comparison)

        return {
            "initiative_id": str(initiative_id),
            "model_id": model_id,
            "prompt_manifest_sha": prompt_manifest_sha,
            "input_hash_verified": True,
            "phase_comparison": phase_comparison,
            "replay_verified": replay_verified,
            "chain_verified": chain_verified,
            "manifest": manifest,
        }

    async def replay_initiative_async(self, initiative_id: uuid.UUID, initiative: Initiative) -> Dict[str, Any]:
        """Async wrapper for replay_initiative — see evaluate_new_initiative_async."""
        return await asyncio.to_thread(self.replay_initiative, initiative_id, initiative)

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

    # Replay demonstration
    replay_report = orchestrator.replay_initiative(sample_initiative.initiative_id, sample_initiative)
    print(f"Replay verified: {replay_report['replay_verified']}")
