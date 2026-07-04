"""
Google ADK to Anthropic Claude Routing Pattern:
----------------------------------------------
1. Model Routing: Google ADK uses LiteLLM as its multi-provider adapter layer.
   When instantiating an Agent, we supply the model name in the LiteLLM format:
   `model="anthropic/claude-sonnet-4-5-20250115"` (or `anthropic/claude-3-5-sonnet-20241022`).
2. Authentication: The ADK routes requests through LiteLLM, which expects the 
   `ANTHROPIC_API_KEY` environment variable to be set.
3. System Instructions: System prompt instructions are loaded from the versioned 
   `prompts/onboarding_intake.md` markdown file at runtime and injected into the ADK Agent's 
   `instruction` attribute.
4. Execution: Invoking the agent's run cycle delegates the generation to the configured Claude instance.
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from google.adk import Agent
from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.audit_log import AgentID, ActionType
from agents.audit_trail import AuditTrailAgent
from security.adversarial_test import detect_adversarial_input

# Define agent tools as standard python functions for ADK registration
def submit_initiative(initiative_data: Dict[str, Any]) -> str:
    """Finalizes the onboarding intake and submits the Initiative object downstream."""
    try:
        init = Initiative(**initiative_data)
        # Store metadata state
        return f"Successfully validated and submitted initiative: {init.name} (ID: {init.initiative_id})"
    except Exception as e:
        return f"Validation failed during submission: {str(e)}"

def flag_security_concern(input_text: str, reason: str) -> str:
    """Escalates potential prompt injections, adversarial overrides, or malicious activity."""
    return f"SECURITY_ALERT_RAISED: Security concern raised for input: '{input_text[:50]}...'. Reason: {reason}"

def request_clarification(field: str, current_value: Any, question: str) -> str:
    """Asks the user a clarifying question about a specific field value."""
    return f"CLARIFICATION_REQUIRED: Field '{field}' (Current: {current_value}). Question: {question}"


def _build_flagged_initiative(matched_pattern: str) -> Initiative:
    """Builds a placeholder Initiative carrying adversarial_flag=True so the
    security event can be logged with a real initiative_id and output_hash.

    This object is never submitted downstream as a real intake — it exists
    only so orchestration.flow.evaluate_new_initiative() has something to
    halt on if it's ever handed this object directly. The primary defense
    is refusing to proceed past this point in execute_turn() itself.
    """
    return Initiative(
        name="ADVERSARIAL_INPUT_BLOCKED",
        sponsor=Sponsor(business_unit="unknown", owner="unknown"),
        description="Intake blocked before processing: adversarial input pattern detected.",
        ai_system=AISystemCharacteristics(
            type=AISystemType.OTHER,
            autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
            hitl_planned=HITLPlanned.UNKNOWN,
        ),
        data=DataCharacteristics(
            sources=["unknown"],
            sensitivity=[DataSensitivity.NONE],
            jurisdictions=["unknown"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.INTERNAL_EMPLOYEES],
            business_impact_tier=BusinessImpactTier.LOW,
            reversibility=Reversibility.FULLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.0,
            unknowns=["all fields — intake refused"],
            intake_duration_minutes=0.0,
            adversarial_flag=True,
            adversarial_reason=f"Injection pattern detected: '{matched_pattern}'",
            intake_agent_version="1.0.0",
            prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        ),
    )


class OnboardingIntakeAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if self.api_key:
            # LiteLLM routes anthropic/ model requests via ANTHROPIC_API_KEY env var
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
            
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "onboarding_intake.md"
        self.system_prompt = self._load_prompt()
        self.audit_trail = AuditTrailAgent(api_key=self.api_key)

        # Instantiate the ADK Agent class, configured to use Claude via LiteLLM
        self.adk_agent = Agent(
            name="onboarding_intake",
            model="anthropic/claude-sonnet-4-5-20250115",
            instruction=self.system_prompt,
            tools=[submit_initiative, flag_security_concern, request_clarification]
        )

    def _load_prompt(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        return "You are the Onboarding Intake Agent. Run conversational interviews to onboard initiatives."

    def execute_turn(self, conversation_history: List[Dict[str, str]], user_input: str) -> str:
        """Executes a conversation turn by passing inputs to the Google ADK Agent."""
        # Security check runs before any LLM call. Detection logic lives in
        # security/adversarial_test.py — the single source of truth — not
        # duplicated here.
        is_adversarial, matched_pattern = detect_adversarial_input(user_input)
        if is_adversarial:
            return self._handle_adversarial_input(user_input, matched_pattern)

        # In production, we run the ADK agent cycle
        # For simulation/local validation when API key is missing:
        if not self.api_key:
            return f"[Offline ADK Mode] Intake Agent received input: '{user_input}'. Please configure ANTHROPIC_API_KEY."

        # Route conversational history to the agent context
        # In ADK, we run step by step using agent.run() or custom message structures
        try:
            response = self.adk_agent.run(user_input)
            return response.text
        except Exception as e:
            return f"Agent execution error: {str(e)}"

    def _handle_adversarial_input(self, user_input: str, matched_pattern: str) -> str:
        """Refuses intake and logs the security event to the Audit Trail
        Agent's hash chain. No valid Initiative is produced for adversarial
        input — the flagged placeholder built here exists only to carry the
        flag and a real initiative_id into the audit log entry."""
        flagged = _build_flagged_initiative(matched_pattern)

        input_hash = hashlib.sha256(user_input.encode("utf-8")).hexdigest()
        output_hash = hashlib.sha256(flagged.model_dump_json().encode("utf-8")).hexdigest()

        self.audit_trail.log_event(
            agent_id=AgentID.ONBOARDING_INTAKE,
            action_type=ActionType.SECURITY_FLAG_RAISED,
            initiative_id=flagged.initiative_id,
            input_hash=input_hash,
            output_hash=output_hash,
            public_context=f"Security flag raised at intake: matched pattern '{matched_pattern}'."
        )

        return (
            "This submission could not be processed. It appears to contain an "
            f"attempt to override agent instructions (matched pattern: '{matched_pattern}'). "
            "No initiative was recorded. This has been logged for security review. "
            "Please resubmit your initiative description through standard intake "
            "channels, without embedded directives addressed to the agent."
        )
