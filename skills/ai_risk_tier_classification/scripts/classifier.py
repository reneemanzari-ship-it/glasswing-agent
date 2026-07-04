import json
import uuid
from datetime import datetime
from typing import Dict, Any, List
from schemas.initiative import Initiative
from schemas.risk_profile import (
    RiskProfile, Classifications, EUAIActClassification, EUAIActTier,
    NISTAIRMFClassification, NISTAttentionLevel, ColoradoSB205Classification,
    OverallRiskTier
)

def local_classify(initiative: Initiative) -> RiskProfile:
    """A helper function executing local, deterministic framework classification.
    Constructs and returns a fully validated nested RiskProfile.
    """
    name = initiative.name.lower()
    desc = initiative.description.lower()
    
    # Check sensitivity and scope
    sensitivities = [s.value for s in initiative.data.sensitivity]
    scopes = [u.value for u in initiative.impact.user_scope]
    
    combined_text = f"{name} {desc} {' '.join(sensitivities)} {' '.join(scopes)}"
    
    # Check if this matches a high-risk credit underwriting scenario (like the 2:47am loan)
    is_credit_scenario = any(k in combined_text for k in ["loan", "credit", "lending", "underwriter", "underwriting"])
    is_recruitment_scenario = any(k in combined_text for k in ["employment", "hiring", "recruit", "cv", "resume"])
    # Limited Risk (Article 50): interacts directly with natural persons (chatbot/
    # conversational/synthetic content) with some human oversight in place, and
    # isn't already a credit or recruitment (Annex III) high-risk trigger.
    is_limited_risk_scenario = (
        any(k in combined_text for k in ["chatbot", "conversational", "virtual assistant", "deepfake", "synthetic content"])
        and initiative.ai_system.hitl_planned.value in ("yes", "partial")
    )

    if is_credit_scenario:
        # EU AI Act High Risk (Annex III.5.b - credit scoring)
        eu_act = EUAIActClassification(
            citations=["EU AI Act Annex III(5)(b)"],
            rationale="This system performs automated credit scoring and evaluation of creditworthiness, which is classified as high-risk under essential services.",
            confidence=0.95,
            tier=EUAIActTier.HIGH_RISK,
            applicable_annexes=["Annex III(5)(b)"]
        )
        
        # NIST AI RMF Critical Map & Manage (Fully autonomous high stakes credit)
        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF MAP-2", "MANAGE-1"],
            rationale="Automated consumer lending involves high-stakes consumer impact, requiring critical attention on mapping risks and managing bias controls.",
            confidence=0.88,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.CRITICAL,
            measure_attention=NISTAttentionLevel.ELEVATED,
            manage_attention=NISTAttentionLevel.CRITICAL,
            critical_categories=["MAP-2", "MANAGE-1"]
        )
        
        # Colorado SB 205 High Risk Applicable (Financial lending category)
        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(a)"],
            rationale="Under Colorado state law, AI systems making consumer financial or lending decisions are high-risk consequential systems.",
            confidence=0.95,
            applicable=True,
            high_risk_category="financial_lending"
        )
        
        overall = OverallRiskTier.HIGH
        exposure_summary = "High regulatory exposure under EU AI Act Annex III(5)(b) and Colorado SB 205 (financial lending)."
        
    elif is_recruitment_scenario:
        # EU AI Act High Risk (Annex III.4 - recruitment scoring)
        eu_act = EUAIActClassification(
            citations=["EU AI Act Annex III(4)(a)"],
            rationale="Vetting and screening applications for recruitment purposes is a high-risk sector category under EU AI Act.",
            confidence=0.90,
            tier=EUAIActTier.HIGH_RISK,
            applicable_annexes=["Annex III(4)(a)"]
        )
        
        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF MAP-2"],
            rationale="Employment decisions significantly impact natural persons, necessitating elevated attention levels across measurement and mapping.",
            confidence=0.85,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.ELEVATED,
            measure_attention=NISTAttentionLevel.ELEVATED,
            manage_attention=NISTAttentionLevel.ROUTINE,
            critical_categories=[]
        )
        
        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(a)"],
            rationale="AI tools utilized to make employment opportunities determinations are consequential and subject to SB 205.",
            confidence=0.90,
            applicable=True,
            high_risk_category="employment"
        )
        
        overall = OverallRiskTier.HIGH
        exposure_summary = "High regulatory exposure under EU AI Act Annex III(4) and Colorado SB 205 (employment)."

    elif is_limited_risk_scenario:
        # EU AI Act Limited Risk (Article 50 - transparency obligations)
        eu_act = EUAIActClassification(
            citations=["EU AI Act Article 50"],
            rationale="This system interacts directly with natural persons (chatbot/conversational AI) and owes them a transparency disclosure under Article 50, even though it makes no consequential decisions under Annex III or Colorado SB 205.",
            confidence=0.90,
            tier=EUAIActTier.LIMITED_RISK,
            applicable_annexes=[]
        )

        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF MEASURE-1", "MANAGE-2"],
            rationale="Conversational AI interacting directly with consumers requires elevated attention to measurement and management of response quality and escalation, though it does not rise to consequential-decision-making critical attention.",
            confidence=0.90,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.ROUTINE,
            measure_attention=NISTAttentionLevel.ELEVATED,
            manage_attention=NISTAttentionLevel.ELEVATED,
            critical_categories=[]
        )

        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(b)"],
            rationale="System does not make or substantially factor into a consequential decision affecting consumer life opportunities; routine customer service interaction only.",
            confidence=0.90,
            applicable=False,
            high_risk_category=None
        )

        # overall_risk_tier follows the assigned EU AI Act tier (Limited Risk ->
        # moderate), not NIST attention levels in isolation. Elevated measure/manage
        # attention here reflects transparency/interaction risk; it doesn't by
        # itself imply a different overall tier.
        overall = OverallRiskTier.MODERATE
        exposure_summary = "Moderate regulatory exposure under EU AI Act Limited Risk (Article 50 transparency obligations); no high-risk trigger under Annex III or Colorado SB 205."

    else:
        # Minimal Risk
        eu_act = EUAIActClassification(
            citations=["EU AI Act Article 5/6"],
            rationale="No prohibited or Annex III high-risk triggers detected in description payload.",
            confidence=0.95,
            tier=EUAIActTier.MINIMAL_RISK,
            applicable_annexes=[]
        )
        
        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF General"],
            rationale="Low impact general utility system requiring standard routine organizational governance practices.",
            confidence=0.90,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.ROUTINE,
            measure_attention=NISTAttentionLevel.ROUTINE,
            manage_attention=NISTAttentionLevel.ROUTINE,
            critical_categories=[]
        )
        
        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(b)"],
            rationale="System does not make consequential decisions affecting consumer life opportunities.",
            confidence=0.95,
            applicable=False,
            high_risk_category=None
        )
        
        overall = OverallRiskTier.LOW
        exposure_summary = "Minimal or routine regulatory exposure across all evaluated frameworks."

    classifications = Classifications(
        eu_ai_act=eu_act,
        nist_ai_rmf=nist,
        colorado_sb_205=co_sb
    )

    # Let's set human review flags if confidence is low, or if scenario demands it
    # Fully autonomous loan decisions at 2:47am (no HITL) automatically require human review
    human_review = False
    reasons = []
    if is_credit_scenario and initiative.ai_system.autonomy_level.value == "fully_autonomous":
        human_review = True
        reasons.append("High stakes consumer credit system deployed without human-in-the-loop oversight.")
    if is_recruitment_scenario and initiative.ai_system.hitl_planned.value in ("no", "unknown"):
        human_review = True
        reasons.append(
            "High stakes employment decision system reports hitl_planned="
            f"{initiative.ai_system.hitl_planned.value}; human oversight not confirmed."
        )

    # Missing mandatory control detection: EU AI Act Article 14 (Human Oversight)
    # and Colorado SB 205's Right to Appeal and Human Review are both mandatory
    # for the High-Risk tier. Flag the gap when neither hitl_planned nor
    # existing_controls shows evidence of a human-oversight control.
    if overall == OverallRiskTier.HIGH:
        has_human_oversight_control = initiative.ai_system.hitl_planned.value in ("yes", "partial") or any(
            kw in c.lower() for c in initiative.existing_controls for kw in ("human", "appeal", "oversight")
        )
        if not has_human_oversight_control:
            human_review = True
            reasons.append(
                "Mandatory control gap: EU AI Act Article 14 (Human Oversight) and Colorado SB 205 "
                "Right to Appeal and Human Review are required for this tier, but the initiative "
                "reports no human-in-the-loop and no equivalent control in existing_controls."
            )

    # Confidence reflects intake certainty, not just tier certainty: if a field
    # material to classification is unconfirmed, or overall intake completeness
    # is low, cap confidence and force human review rather than reporting
    # unwarranted certainty.
    material_unknown_fields = {"ai_system.autonomy_level", "ai_system.hitl_planned"}
    ambiguous_intake = (
        any(u in material_unknown_fields for u in initiative.intake_metadata.unknowns)
        or initiative.intake_metadata.completeness_score < 0.75
        or initiative.ai_system.hitl_planned.value == "unknown"
    )
    if ambiguous_intake:
        eu_act.confidence = min(eu_act.confidence, 0.84)
        nist.confidence = min(nist.confidence, 0.84)
        co_sb.confidence = min(co_sb.confidence, 0.84)
        human_review = True
        reasons.append(
            "Classification confidence capped: intake data material to classification "
            "(autonomy level and/or HITL plan) is unknown or incompletely confirmed."
        )

    return RiskProfile(
        initiative_id=initiative.initiative_id,
        classifications=classifications,
        overall_risk_tier=overall,
        regulatory_exposure_summary=exposure_summary,
        human_review_required=human_review,
        human_review_reasons=reasons,
        classifier_agent_version="1.0.0",
        prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        mcp_server_version="1.0.0",
        model_id="claude-sonnet-4-5-20250115"
    )
