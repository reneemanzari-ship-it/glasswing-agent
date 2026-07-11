"""Deterministic risk classification engine — canonical implementation.

Migrated Week 2 (GLASSWING_SPEC.md section 3) from v0.1's
skills/ai_risk_tier_classification/scripts/classifier.py::local_classify().
skills/ai_risk_tier_classification now imports classify_initiative from
here (glasswing.engines.classification is the single source of truth); the
skill is a thin wrapper, not a fork.

Implements prompts/risk_classifier.md's numbered rules R1-R9:
- R2/R3/R5: EU AI Act tier assignment order (prohibited -> high-risk ->
  limited-risk -> minimal-risk), with overall_risk_tier following the EU
  tier only -- never NIST attention (see the dedicated regression test in
  tests/golden/test_r5_nist_precedence.py pinning the historical bug this
  guards against).
- R4: NIST AI RMF function-attention mapping.
- R6: Colorado SB 205 consequential-decision applicability.
- R8: confidence reflects intake certainty, capped at 0.84 when material
  fields are unknown/unconfirmed.
- R9: mandatory-control-gap detection (EU Article 14 / SB 205 human
  review) drives human_review_required.

R1 ("MCP is the source of truth") is honored at the citation/category
level: citations and category identifiers here match what
mcp_server/frameworks/*.json actually contains for the same tiers, and are
kept in sync at the migration point below. Full live MCP-tool queries in
this engine are Week 5+ scope, when the controls engine also starts
consuming get_controls_for_tier; this week's migration is deliberately a
faithful port of v0.1's already-working keyword-based classification, not
a rearchitecture (DECISIONS.md D-009).

Deterministic, no LLM calls -- CLAUDE.md invariant #1.
"""

from __future__ import annotations

from glasswing.core.ll144 import NYCLL144Classification
from schemas.initiative import Initiative
from schemas.risk_profile import (
    Classifications,
    ColoradoSB205Classification,
    EUAIActClassification,
    EUAIActTier,
    NISTAIRMFClassification,
    NISTAttentionLevel,
    OverallRiskTier,
    RiskProfile,
)

ENGINE_VERSION = "2.0.0"

_CREDIT_KEYWORDS = ["loan", "credit", "lending", "underwriter", "underwriting"]
_RECRUITMENT_KEYWORDS = ["employment", "hiring", "recruit", "cv", "resume"]
_LIMITED_RISK_KEYWORDS = [
    "chatbot",
    "conversational",
    "virtual assistant",
    "deepfake",
    "synthetic content",
]
_PROHIBITED_KEYWORDS = (
    "social scoring",
    "social credit",
    "subliminal manipulation",
    "untargeted scraping of facial images",
    "real-time biometric identification in public",
)


def classify_initiative(initiative: Initiative) -> RiskProfile:
    """Classifies an Initiative against EU AI Act, NIST AI RMF, and
    Colorado SB 205. Canonical entry point -- see module docstring."""
    name = initiative.name.lower()
    desc = initiative.description.lower()

    sensitivities = [s.value for s in initiative.data.sensitivity]
    scopes = [u.value for u in initiative.impact.user_scope]

    combined_text = f"{name} {desc} {' '.join(sensitivities)} {' '.join(scopes)}"

    # R2 step 1 / R2.1: Article 5 prohibited practices. Checked first and
    # unconditionally -- a prohibited-practice match halts at this tier
    # regardless of any other keyword that might also be present. New in
    # Week 2: v0.1's local_classify() had no branch that ever assigned
    # EUAIActTier.PROHIBITED (DECISIONS.md D-011); this is additive
    # capability, not a behavior change for any scenario v0.1 already
    # handled.
    is_prohibited_scenario = any(k in combined_text for k in _PROHIBITED_KEYWORDS)
    is_credit_scenario = any(k in combined_text for k in _CREDIT_KEYWORDS)
    is_recruitment_scenario = any(k in combined_text for k in _RECRUITMENT_KEYWORDS)
    # Limited Risk (Article 50): interacts directly with natural persons (chatbot/
    # conversational/synthetic content) with some human oversight in place, and
    # isn't already a credit or recruitment (Annex III) high-risk trigger.
    is_limited_risk_scenario = any(
        k in combined_text for k in _LIMITED_RISK_KEYWORDS
    ) and initiative.ai_system.hitl_planned.value in ("yes", "partial")

    if is_prohibited_scenario:
        eu_act = EUAIActClassification(
            citations=["EU AI Act Article 5"],
            rationale=(
                "This system's described behavior matches an Article 5 prohibited "
                "practice (e.g. social scoring by a public authority, subliminal "
                "manipulation, or untargeted biometric scraping). Deployment of "
                "this system is prohibited in the EU; this is a halt condition."
            ),
            confidence=0.90,
            tier=EUAIActTier.PROHIBITED,
            applicable_annexes=[],
        )
        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF GOVERN-1", "MAP-2", "MANAGE-1"],
            rationale=(
                "A prohibited-practice system requires critical attention across "
                "every function: it should not be operated at all, and every "
                "function's controls are implicated by the fact that it is."
            ),
            confidence=0.90,
            govern_attention=NISTAttentionLevel.CRITICAL,
            map_attention=NISTAttentionLevel.CRITICAL,
            measure_attention=NISTAttentionLevel.CRITICAL,
            manage_attention=NISTAttentionLevel.CRITICAL,
            critical_categories=["GV-1", "MP-2", "MG-1"],
        )
        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(a)"],
            rationale=(
                "A system determining eligibility for government services or "
                "benefits based on a trustworthiness/behavior score is a "
                "substantial factor in a consequential decision in an "
                "essential-government-service category."
            ),
            confidence=0.85,
            applicable=True,
            high_risk_category="essential_government_service",
        )
        overall = OverallRiskTier.PROHIBITED
        exposure_summary = (
            "Prohibited under EU AI Act Article 5 (unacceptable-risk practice); "
            "do not proceed to control prescription for this initiative."
        )

    elif is_credit_scenario:
        # EU AI Act High Risk (Annex III.5.b - credit scoring)
        eu_act = EUAIActClassification(
            citations=["EU AI Act Annex III(5)(b)"],
            rationale=(
                "This system performs automated credit scoring and evaluation of "
                "creditworthiness, which is classified as high-risk under "
                "essential services."
            ),
            confidence=0.95,
            tier=EUAIActTier.HIGH_RISK,
            applicable_annexes=["Annex III(5)(b)"],
        )

        # NIST AI RMF Critical Map & Manage (Fully autonomous high stakes credit)
        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF MAP-2", "MANAGE-1"],
            rationale=(
                "Automated consumer lending involves high-stakes consumer "
                "impact, requiring critical attention on mapping risks and "
                "managing bias controls."
            ),
            confidence=0.88,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.CRITICAL,
            measure_attention=NISTAttentionLevel.ELEVATED,
            manage_attention=NISTAttentionLevel.CRITICAL,
            critical_categories=["MAP-2", "MANAGE-1"],
        )

        # Colorado SB 205 High Risk Applicable (Financial lending category)
        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(a)"],
            rationale=(
                "Under Colorado state law, AI systems making consumer financial "
                "or lending decisions are high-risk consequential systems."
            ),
            confidence=0.95,
            applicable=True,
            high_risk_category="financial_lending",
        )

        overall = OverallRiskTier.HIGH
        exposure_summary = (
            "High regulatory exposure under EU AI Act Annex III(5)(b) and "
            "Colorado SB 205 (financial lending)."
        )

    elif is_recruitment_scenario:
        # EU AI Act High Risk (Annex III.4 - recruitment scoring)
        eu_act = EUAIActClassification(
            citations=["EU AI Act Annex III(4)(a)"],
            rationale=(
                "Vetting and screening applications for recruitment purposes is "
                "a high-risk sector category under EU AI Act."
            ),
            confidence=0.90,
            tier=EUAIActTier.HIGH_RISK,
            applicable_annexes=["Annex III(4)(a)"],
        )

        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF MAP-2"],
            rationale=(
                "Employment decisions significantly impact natural persons, "
                "necessitating elevated attention levels across measurement "
                "and mapping."
            ),
            confidence=0.85,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.ELEVATED,
            measure_attention=NISTAttentionLevel.ELEVATED,
            manage_attention=NISTAttentionLevel.ROUTINE,
            critical_categories=[],
        )

        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(a)"],
            rationale=(
                "AI tools utilized to make employment opportunities "
                "determinations are consequential and subject to SB 205."
            ),
            confidence=0.90,
            applicable=True,
            high_risk_category="employment",
        )

        overall = OverallRiskTier.HIGH
        exposure_summary = (
            "High regulatory exposure under EU AI Act Annex III(4) and "
            "Colorado SB 205 (employment)."
        )

    elif is_limited_risk_scenario:
        # EU AI Act Limited Risk (Article 50 - transparency obligations)
        eu_act = EUAIActClassification(
            citations=["EU AI Act Article 50"],
            rationale=(
                "This system interacts directly with natural persons "
                "(chatbot/conversational AI) and owes them a transparency "
                "disclosure under Article 50, even though it makes no "
                "consequential decisions under Annex III or Colorado SB 205."
            ),
            confidence=0.90,
            tier=EUAIActTier.LIMITED_RISK,
            applicable_annexes=[],
        )

        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF MEASURE-1", "MANAGE-2"],
            rationale=(
                "Conversational AI interacting directly with consumers "
                "requires elevated attention to measurement and management of "
                "response quality and escalation, though it does not rise to "
                "consequential-decision-making critical attention."
            ),
            confidence=0.90,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.ROUTINE,
            measure_attention=NISTAttentionLevel.ELEVATED,
            manage_attention=NISTAttentionLevel.ELEVATED,
            critical_categories=[],
        )

        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(b)"],
            rationale=(
                "System does not make or substantially factor into a "
                "consequential decision affecting consumer life opportunities; "
                "routine customer service interaction only."
            ),
            confidence=0.90,
            applicable=False,
            high_risk_category=None,
        )

        # overall_risk_tier follows the assigned EU AI Act tier (Limited Risk ->
        # moderate), not NIST attention levels in isolation. Elevated measure/manage
        # attention here reflects transparency/interaction risk; it doesn't by
        # itself imply a different overall tier. (R5 -- see
        # tests/golden/test_r5_nist_precedence.py.)
        overall = OverallRiskTier.MODERATE
        exposure_summary = (
            "Moderate regulatory exposure under EU AI Act Limited Risk "
            "(Article 50 transparency obligations); no high-risk trigger "
            "under Annex III or Colorado SB 205."
        )

    else:
        # Minimal Risk
        eu_act = EUAIActClassification(
            citations=["EU AI Act Article 5/6"],
            rationale=(
                "No prohibited or Annex III high-risk triggers detected in "
                "description payload."
            ),
            confidence=0.95,
            tier=EUAIActTier.MINIMAL_RISK,
            applicable_annexes=[],
        )

        nist = NISTAIRMFClassification(
            citations=["NIST AI RMF General"],
            rationale=(
                "Low impact general utility system requiring standard routine "
                "organizational governance practices."
            ),
            confidence=0.90,
            govern_attention=NISTAttentionLevel.ROUTINE,
            map_attention=NISTAttentionLevel.ROUTINE,
            measure_attention=NISTAttentionLevel.ROUTINE,
            manage_attention=NISTAttentionLevel.ROUTINE,
            critical_categories=[],
        )

        co_sb = ColoradoSB205Classification(
            citations=["C.R.S. § 6-1-1701(7)(b)"],
            rationale=(
                "System does not make consequential decisions affecting "
                "consumer life opportunities."
            ),
            confidence=0.95,
            applicable=False,
            high_risk_category=None,
        )

        overall = OverallRiskTier.LOW
        exposure_summary = (
            "Minimal or routine regulatory exposure across all evaluated frameworks."
        )

    classifications = Classifications(
        eu_ai_act=eu_act, nist_ai_rmf=nist, colorado_sb_205=co_sb
    )

    # R9: mandatory-control-gap detection, plus the credit/recruitment-specific
    # human-review triggers preserved from v0.1.
    human_review = False
    reasons: list[str] = []

    if is_prohibited_scenario:
        human_review = True
        reasons.append(
            "EU AI Act Article 5 prohibited-practice halt: this initiative must "
            "not proceed to control prescription and requires immediate human "
            "review."
        )

    autonomy = initiative.ai_system.autonomy_level.value
    credit_fully_autonomous = is_credit_scenario and autonomy == "fully_autonomous"
    if credit_fully_autonomous:
        human_review = True
        reasons.append(
            "High stakes consumer credit system deployed without "
            "human-in-the-loop oversight."
        )
    hitl_planned = initiative.ai_system.hitl_planned.value
    recruitment_hitl_gap = is_recruitment_scenario and hitl_planned in ("no", "unknown")
    if recruitment_hitl_gap:
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
        has_human_oversight_control = initiative.ai_system.hitl_planned.value in (
            "yes",
            "partial",
        ) or any(
            kw in c.lower()
            for c in initiative.existing_controls
            for kw in ("human", "appeal", "oversight")
        )
        if not has_human_oversight_control:
            human_review = True
            reasons.append(
                "Mandatory control gap: EU AI Act Article 14 (Human Oversight) "
                "and Colorado SB 205 Right to Appeal and Human Review are "
                "required for this tier, but the initiative reports no "
                "human-in-the-loop and no equivalent control in "
                "existing_controls."
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
        classifier_agent_version=ENGINE_VERSION,
        prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        mcp_server_version="1.0.0",
        model_id="deterministic-engine",
    )


def classify_nyc_ll144(initiative: Initiative) -> NYCLL144Classification:
    """NYC Local Law 144 (Automated Employment Decision Tools) applicability.

    Low-level building block -- build_per_framework_results() below is
    what the Phase 1 -> Phase 2 contract and Week 6 report actually read;
    this function stays independently callable/testable, and its result
    model (glasswing.core.ll144.NYCLL144Classification) stays a plain
    Pydantic model rather than a schemas.risk_profile.RiskProfile field,
    since that model is the v0.1-parity-tested internal shape
    classify_initiative() still returns, not the forward contract
    (DECISIONS.md D-010).

    Applicable when the initiative is used to substantially assist or
    replace a discretionary employment decision (screening, ranking, or
    scoring candidates -- the same recruitment signal
    classify_initiative() already detects) for a role based in New York
    City. Verified 2026-07-09: LL144 took effect 2023-01-01, enforcement
    began 2023-07-05, and requires an independent annual bias audit,
    public posting of audit results, and >=10 business days' candidate
    notice (NYC DCWP; see mcp_server/frameworks/nyc_ll144.json
    verification_note for sources).
    """
    combined_text = f"{initiative.name.lower()} {initiative.description.lower()}"
    is_recruitment_scenario = any(k in combined_text for k in _RECRUITMENT_KEYWORDS)
    has_nyc_nexus = "US-NY" in initiative.data.jurisdictions

    if is_recruitment_scenario and has_nyc_nexus:
        return NYCLL144Classification(
            applicable=True,
            citations=["NYC Admin. Code § 20-870 et seq. (Local Law 144)"],
            rationale=(
                "This system screens, ranks, or scores candidates for a New "
                "York City-based role, substantially assisting the employment "
                "decision -- an Automated Employment Decision Tool under Local "
                "Law 144."
            ),
            confidence=0.85,
            requires_bias_audit=True,
        )

    return NYCLL144Classification(
        applicable=False,
        citations=[],
        rationale=(
            "No New York City jurisdictional nexus and/or no automated "
            "employment screening, ranking, or scoring detected; Local Law "
            "144 does not apply."
        ),
        confidence=0.85,
        requires_bias_audit=False,
    )


def build_per_framework_results(initiative: Initiative) -> dict[str, dict[str, object]]:
    """The uniform, forward-facing classification payload -- this is the
    shape glasswing.core.risk.RiskProfile.per_framework_results holds, and
    what the Phase 1 -> Phase 2 contract (GLASSWING_SPEC.md section 4,
    which consumes overall_tier and per-framework results) and the Week 6
    report (which carries every framework's classification uniformly) are
    meant to read.

    Every framework -- eu_ai_act, nist_ai_rmf, colorado_sb_205, and
    nyc_ll144 -- appears as a same-shaped dict entry keyed by framework_id,
    so a report renderer or a Phase 2 policy-derivation step iterates
    uniformly over frameworks without special-casing LL144 as a fourth,
    differently-discovered thing (DECISIONS.md D-010: resolves the
    Week 2 rationale for a separate model, which did not hold once
    per_framework_results -- a plain JSON dict -- was available to hold
    it uniformly).

    overall_risk_tier and human_review_required are NOT included here:
    they come from classify_initiative()'s RiskProfile directly, driven
    solely by the EU AI Act tier per R5 -- LL144 applicability never
    raises or substitutes for the overall tier, the same guarantee R5
    already gives NIST attention.
    """
    profile = classify_initiative(initiative)
    ll144 = classify_nyc_ll144(initiative)
    eu = profile.classifications.eu_ai_act
    nist = profile.classifications.nist_ai_rmf
    co = profile.classifications.colorado_sb_205

    return {
        "eu_ai_act": {
            "tier": eu.tier.value,
            "citations": eu.citations,
            "rationale": eu.rationale,
            "confidence": eu.confidence,
            "applicable_annexes": eu.applicable_annexes,
        },
        "nist_ai_rmf": {
            "govern_attention": nist.govern_attention.value,
            "map_attention": nist.map_attention.value,
            "measure_attention": nist.measure_attention.value,
            "manage_attention": nist.manage_attention.value,
            "citations": nist.citations,
            "rationale": nist.rationale,
            "confidence": nist.confidence,
            "critical_categories": nist.critical_categories,
        },
        "colorado_sb_205": {
            "applicable": co.applicable,
            "high_risk_category": co.high_risk_category,
            "citations": co.citations,
            "rationale": co.rationale,
            "confidence": co.confidence,
        },
        "nyc_ll144": {
            "applicable": ll144.applicable,
            "citations": ll144.citations,
            "rationale": ll144.rationale,
            "confidence": ll144.confidence,
            "requires_bias_audit": ll144.requires_bias_audit,
        },
    }
