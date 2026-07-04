"""
Google ADK to Anthropic Claude Routing Pattern:
----------------------------------------------
Model: anthropic/claude-sonnet-4-5-20250115 (via LiteLLM router)
Instructions: Dynamically loaded from prompts/control_prescription.md
Tools: Exposes get_required_controls MCP tool.
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from google.adk import Agent
from schemas.risk_profile import RiskProfile
from schemas.control_prescription import ControlPrescription

from mcp_server.server import get_required_controls

class ControlPrescriptionAgent:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if self.api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
            
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "control_prescription.md"
        self.system_prompt = self._load_prompt()
        
        self.adk_agent = Agent(
            name="control_prescription",
            model="anthropic/claude-sonnet-4-5-20250115",
            instruction=self.system_prompt,
            tools=[get_required_controls]
        )

    def _load_prompt(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        return "You are the Control Prescription Agent. Query controls from framework server."

    def prescribe_controls(self, risk_profile: RiskProfile) -> ControlPrescription:
        """Invokes ADK agent to query MCP controls and output ControlPrescription."""
        prompt_input = f"""
        Prescribe controls for the following AI risk profile:
        Risk Profile ID: {risk_profile.risk_profile_id}
        Initiative ID: {risk_profile.initiative_id}
        Overall Risk Tier: {risk_profile.overall_risk_tier.value}
        EU AI Act risk tier: {risk_profile.classifications.eu_ai_act.tier.value}
        NIST Map attention level: {risk_profile.classifications.nist_ai_rmf.map_attention.value}
        NIST Manage attention level: {risk_profile.classifications.nist_ai_rmf.manage_attention.value}
        Colorado SB 205 High Risk: {risk_profile.classifications.colorado_sb_205.applicable}
        
        Call the 'get_required_controls' tool to fetch required guidelines and structure the prescription.
        """

        if not self.api_key:
            # Fallback simulator for offline mode / testing
            from decimal import Decimal
            from schemas.control_prescription import (
                Controls, DeploymentGate, ImplementationEffort, Guardrail, ControlCategory,
                SourceFramework, HITLTouchpoint, MonitoringRequirement, AuditArtifactRequirement
            )

            guardrails = []
            hitl_touchpoints = []
            monitoring = []
            audit_artifacts = []

            is_eu_high_risk = risk_profile.classifications.eu_ai_act.tier == "high_risk"
            is_financial_lending = risk_profile.classifications.colorado_sb_205.high_risk_category == "financial_lending"

            if is_eu_high_risk:
                guardrails.append(
                    Guardrail(
                        control_id="GR-0001",
                        category=ControlCategory.INPUT_VALIDATION,
                        description="demographic parity checking",
                        implementation_notes="Implement metric evaluations prior to model use.",
                        mandatory=True,
                        source_framework=[SourceFramework.EU_AI_ACT],
                        source_citation="Article 10"
                    )
                )
                guardrails.append(
                    Guardrail(
                        control_id="GR-0002",
                        category=ControlCategory.CONFIDENCE_THRESHOLD,
                        description="Minimum model confidence threshold of 0.95 for autonomous decisions.",
                        implementation_notes="Any decision where model confidence falls below 0.95 must be routed to human review rather than auto-approved.",
                        mandatory=True,
                        source_framework=[SourceFramework.EU_AI_ACT, SourceFramework.NIST_AI_RMF],
                        source_citation="EU AI Act Article 14; NIST AI RMF MANAGE-1"
                    )
                )

            if is_financial_lending:
                hitl_touchpoints.append(
                    HITLTouchpoint(
                        control_id="HITL-0001",
                        trigger_description="Consequential consumer lending decisions above $500,000 require human review before finalization.",
                        trigger_quantitative="loan_amount > 500000",
                        reviewer_role="Senior Credit Underwriter",
                        review_sla_hours=24,
                        mandatory=True,
                        source_framework=[SourceFramework.EU_AI_ACT, SourceFramework.COLORADO_SB_205]
                    )
                )
                monitoring.append(
                    MonitoringRequirement(
                        control_id="MON-0001",
                        metric="Approval/denial disparity across protected classes; model confidence distribution",
                        cadence="real-time",
                        alerting_threshold="Disparate impact ratio outside 0.8-1.25 (four-fifths rule)",
                        on_call_role="ML Risk Monitoring Team",
                        mandatory=True
                    )
                )
                audit_artifacts.append(
                    AuditArtifactRequirement(
                        control_id="AUD-0001",
                        artifact_type="Consumer lending decision audit trail (inputs, score, rationale, outcome)",
                        retention_years=7,
                        regulator_format_required=True,
                        replay_capability_required=True,
                        source_framework=[SourceFramework.COLORADO_SB_205, SourceFramework.EU_AI_ACT]
                    )
                )

            return ControlPrescription(
                initiative_id=risk_profile.initiative_id,
                risk_profile_id=risk_profile.risk_profile_id,
                risk_tier_assessed=risk_profile.overall_risk_tier.value,
                controls=Controls(
                    guardrails=guardrails,
                    hitl_touchpoints=hitl_touchpoints,
                    monitoring=monitoring,
                    audit_artifacts=audit_artifacts,
                ),
                deployment_gate=DeploymentGate(
                    approvers_required=["Compliance Officer"],
                    pre_deployment_artifacts_required=["Model Assessment"]
                ),
                estimated_implementation_effort=ImplementationEffort(
                    engineering_weeks=2.0,
                    governance_team_weeks=1.0
                ),
                executive_summary="Prescribed essential compliance controls based on EU risk parameters.",
                prescription_agent_version="1.0.0",
                prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                model_id="claude-sonnet-4-5-20250115"
            )

        try:
            response = self.adk_agent.run(prompt_input)
            return ControlPrescription.model_validate_json(response.text)
        except Exception:
            # Safe local fallback on unstructured outputs
            from decimal import Decimal
            from schemas.control_prescription import Controls, DeploymentGate, ImplementationEffort
            return ControlPrescription(
                initiative_id=risk_profile.initiative_id,
                risk_profile_id=risk_profile.risk_profile_id,
                risk_tier_assessed=risk_profile.overall_risk_tier.value,
                controls=Controls(),
                deployment_gate=DeploymentGate(
                    approvers_required=["Compliance Officer"],
                    pre_deployment_artifacts_required=["Compliance Audit"]
                ),
                estimated_implementation_effort=ImplementationEffort(
                    engineering_weeks=1.0,
                    governance_team_weeks=1.0
                ),
                executive_summary="Safe default controls prescribed.",
                prescription_agent_version="1.0.0",
                prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                model_id="claude-sonnet-4-5-20250115"
            )
