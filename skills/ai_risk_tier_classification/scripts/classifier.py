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
