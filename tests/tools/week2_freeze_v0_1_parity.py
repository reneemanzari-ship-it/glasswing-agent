"""HISTORICAL ARTIFACT — DO NOT RE-RUN.

This is the recovered, as-executed script that generated
tests/golden/v0.1_parity/*.v0.1_output.json (GLASSWING_SPEC.md section 3,
Week 2 sequencing requirement: freeze v0.1's actual output before
touching the engine). It was run once, against the untouched v0.1
skill/classifier, before glasswing/engines/classification.py existed, and
was deleted from the working tree immediately after (a mistake — Week 3
pre-work A restores it here, committed, so the frozen baseline's
provenance is itself auditable rather than merely asserted).

Re-running this script today would NOT reproduce v0.1's output: Week 2
repointed skills/ai_risk_tier_classification/scripts/classifier.py's
local_classify to re-export glasswing.engines.classification.classify_initiative,
so `from skills.ai_risk_tier_classification.scripts.classifier import
local_classify` now resolves to the migrated engine, not v0.1. Running
this again would silently overwrite the genuine v0.1 baseline with
post-migration output and defeat the entire point of the parity check.
It is kept only as evidence of how the frozen snapshots were actually
produced — by executing the real v0.1 code path, not by hand-transcribing
expected values.

Original run: 2026-07-09, against the commit at HEAD when
glasswing/services/{audit,portfolio}.py existed but
glasswing/engines/classification.py did not yet exist (immediately after
the Week 1 follow-ups commit, immediately before the Week 2 engine
migration commit). Verifiable via `git log` on those two commits.
"""

from __future__ import annotations

import json
from pathlib import Path

from schemas.initiative import (
    AISystemCharacteristics,
    AISystemType,
    AutonomyLevel,
    BusinessImpactTier,
    DataCharacteristics,
    DataSensitivity,
    HITLPlanned,
    ImpactCharacteristics,
    Initiative,
    IntakeMetadata,
    Reversibility,
    Sponsor,
    UserScope,
)
from skills.ai_risk_tier_classification.scripts.classifier import local_classify

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "golden" / "fixtures"
PARITY_DIR = REPO_ROOT / "tests" / "golden" / "v0.1_parity"
EXAMPLES_DIR = REPO_ROOT / "skills" / "ai_risk_tier_classification" / "examples"
SHA = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


def _initiative(**kwargs) -> Initiative:
    return Initiative(**kwargs)


def _from_example(filename: str) -> Initiative:
    """Loads one of the 4 pre-existing skill examples unmodified -- these
    already ARE the v0.1-representable fixtures 1-4; reading them here
    (rather than retyping the data) guarantees the golden set uses the
    exact same input the skill's existing examples/regression tests do."""
    with open(EXAMPLES_DIR / filename, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return Initiative(**payload["input_initiative"])


# --- Fixtures 1-4: the 4 pre-existing skill examples, unmodified. ---
# --- Fixtures 5-12: the 8 new fixtures for Week 2's expanded coverage. ---

FIXTURES: dict[str, Initiative] = {
    "01_high_risk_credit_lendfast": _from_example("example_high_risk_loan.json"),
    "02_high_risk_recruitment_ambiguous": _from_example(
        "example_ambiguous_hiring.json"
    ),
    "03_limited_risk_chatbot": _from_example("example_limited_risk_chatbot.json"),
    "04_minimal_risk_marketing": _from_example("example_low_risk_marketing.json"),
    "05_prohibited_social_scoring": _initiative(
        name="Municipal Citizen Trust Scoring System",
        sponsor=Sponsor(
            business_unit="Public Safety Division", owner="City Program Director"
        ),
        description=(
            "Government-operated social scoring system that evaluates citizens' "
            "general trustworthiness and behavior using surveillance and public "
            "records data, determining eligibility for public benefits and "
            "government services based on the resulting trust score."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.CLASSICAL_ML,
            autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS,
            hitl_planned=HITLPlanned.NO,
        ),
        data=DataCharacteristics(
            sources=[
                "public surveillance records",
                "government administrative databases",
            ],
            sensitivity=[DataSensitivity.PII, DataSensitivity.BIOMETRIC],
            jurisdictions=["EU"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.CONSUMERS, UserScope.VULNERABLE_POPULATIONS],
            business_impact_tier=BusinessImpactTier.CRITICAL,
            reversibility=Reversibility.IRREVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.95,
            intake_duration_minutes=10.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "06_ll144_triggering_nyc_aedt": _initiative(
        name="NYC Candidate Screening Scorer",
        sponsor=Sponsor(
            business_unit="Talent Acquisition", owner="Recruiting Ops Lead"
        ),
        description=(
            "Automated employment decision tool that scores and ranks job "
            "applicants for NYC-based roles, substantially assisting hiring "
            "managers' screening decisions. No independent bias audit has been "
            "performed."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.CLASSICAL_ML,
            autonomy_level=AutonomyLevel.APPROVE_WITH_OVERRIDE,
            hitl_planned=HITLPlanned.PARTIAL,
            hitl_description=(
                "Recruiters review the top-ranked candidates before scheduling "
                "interviews."
            ),
        ),
        data=DataCharacteristics(
            sources=["resumes", "applicant tracking system"],
            sensitivity=[DataSensitivity.PII],
            jurisdictions=["US-NY"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.CONSUMERS],
            business_impact_tier=BusinessImpactTier.HIGH,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.90,
            intake_duration_minutes=11.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "07_ll144_non_triggering_no_nyc_nexus": _initiative(
        name="Regional Resume Screening Tool",
        sponsor=Sponsor(
            business_unit="Talent Acquisition", owner="Regional HR Lead"
        ),
        description=(
            "Automated employment decision tool that scores and ranks job "
            "applicants for roles based outside New York City, substantially "
            "assisting hiring managers' screening decisions."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.CLASSICAL_ML,
            autonomy_level=AutonomyLevel.APPROVE_WITH_OVERRIDE,
            hitl_planned=HITLPlanned.PARTIAL,
            hitl_description=(
                "Recruiters review the top-ranked candidates before scheduling "
                "interviews."
            ),
        ),
        data=DataCharacteristics(
            sources=["resumes", "applicant tracking system"],
            sensitivity=[DataSensitivity.PII],
            jurisdictions=["US-TX"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.CONSUMERS],
            business_impact_tier=BusinessImpactTier.HIGH,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.90,
            intake_duration_minutes=11.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "08_credit_with_adequate_oversight": _initiative(
        name="Credit Pre-Approval Recommendation Assistant",
        sponsor=Sponsor(
            business_unit="Retail Lending Division", owner="Lending Ops Lead"
        ),
        description=(
            "Recommends consumer credit pre-approval tiers based on credit "
            "history; a human underwriter reviews and confirms every "
            "recommendation before a loan offer issues."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.CLASSICAL_ML,
            autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
            hitl_planned=HITLPlanned.YES,
            hitl_description=(
                "A licensed underwriter confirms every recommendation before "
                "issuance."
            ),
        ),
        data=DataCharacteristics(
            sources=["credit scores bureau history"],
            sensitivity=[DataSensitivity.FINANCIAL, DataSensitivity.PII],
            jurisdictions=["US-CO"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.CONSUMERS],
            business_impact_tier=BusinessImpactTier.HIGH,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        ),
        existing_controls=["human oversight review committee"],
        intake_metadata=IntakeMetadata(
            completeness_score=0.95,
            intake_duration_minutes=14.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "09_minimal_risk_inventory_bot": _initiative(
        name="Inventory Reorder Bot",
        sponsor=Sponsor(business_unit="Supply Chain Operations", owner="Ops Lead"),
        description=(
            "Recommends internal warehouse reorder quantities based on "
            "historical stock movement; used only by internal supply chain "
            "staff."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.CLASSICAL_ML,
            autonomy_level=AutonomyLevel.APPROVE_WITH_OVERRIDE,
            hitl_planned=HITLPlanned.YES,
        ),
        data=DataCharacteristics(
            sources=["warehouse inventory logs"],
            sensitivity=[DataSensitivity.NONE],
            jurisdictions=["US-NY"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.INTERNAL_EMPLOYEES],
            business_impact_tier=BusinessImpactTier.LOW,
            reversibility=Reversibility.FULLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.95,
            intake_duration_minutes=6.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "10_ambiguous_low_completeness_summarizer": _initiative(
        name="Internal Report Summarization Draft Tool",
        sponsor=Sponsor(business_unit="Operations", owner="Ops Analyst"),
        description=(
            "Drafts summaries of internal weekly operations reports for staff "
            "review."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.LLM,
            autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
            hitl_planned=HITLPlanned.UNKNOWN,
        ),
        data=DataCharacteristics(
            sources=["internal operations reports"],
            sensitivity=[DataSensitivity.NONE],
            jurisdictions=["US-NY"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.INTERNAL_EMPLOYEES],
            business_impact_tier=BusinessImpactTier.LOW,
            reversibility=Reversibility.FULLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.50,
            unknowns=["ai_system.hitl_planned"],
            intake_duration_minutes=4.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "11_clean_recruitment_no_hitl": _initiative(
        name="Automated Candidate Ranking System",
        sponsor=Sponsor(
            business_unit="Human Resources", owner="HR Systems Lead"
        ),
        description=(
            "Automatically ranks job applicants by fit score for open "
            "recruitment requisitions; hiring managers receive the ranked list "
            "with no further review step in the current process."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.CLASSICAL_ML,
            autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
            hitl_planned=HITLPlanned.NO,
        ),
        data=DataCharacteristics(
            sources=["resumes", "applicant tracking system"],
            sensitivity=[DataSensitivity.PII],
            jurisdictions=["US-CO"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.CONSUMERS],
            business_impact_tier=BusinessImpactTier.HIGH,
            reversibility=Reversibility.PARTIALLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.95,
            intake_duration_minutes=13.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
    "12_limited_risk_deepfake_watermarking": _initiative(
        name="Synthetic Media Watermarking Assistant",
        sponsor=Sponsor(business_unit="Trust and Safety", owner="Trust Lead"),
        description=(
            "Generates and labels synthetic content (deepfake-style media "
            "edits) for marketing use, routing any ambiguous or escalated "
            "request to a human reviewer before publication."
        ),
        ai_system=AISystemCharacteristics(
            type=AISystemType.LLM,
            autonomy_level=AutonomyLevel.APPROVE_WITH_OVERRIDE,
            hitl_planned=HITLPlanned.PARTIAL,
            hitl_description=(
                "Escalated or ambiguous synthetic-content requests are routed "
                "to a human reviewer."
            ),
        ),
        data=DataCharacteristics(
            sources=["marketing asset library"],
            sensitivity=[DataSensitivity.NONE],
            jurisdictions=["US-NY"],
        ),
        impact=ImpactCharacteristics(
            user_scope=[UserScope.CONSUMERS],
            business_impact_tier=BusinessImpactTier.MODERATE,
            reversibility=Reversibility.FULLY_REVERSIBLE,
        ),
        intake_metadata=IntakeMetadata(
            completeness_score=0.92,
            intake_duration_minutes=9.0,
            intake_agent_version="1.0.0",
            prompt_manifest_sha=SHA,
        ),
    ),
}

# v0.1-representable: local_classify() can already produce a meaningful
# classification for these (they hit the credit/recruitment/limited-risk/
# minimal-risk branches v0.1 already implements). "06" and "07" are
# v0.1-representable for eu_ai_act/nist_ai_rmf/colorado_sb_205 only --
# v0.1 has no NYC LL144 concept at all, so there is nothing to freeze for
# that framework on those two. "05" (prohibited) is NOT v0.1-representable
# at all: local_classify() has no branch that ever assigns
# EUAIActTier.PROHIBITED, so running it through v0.1 would freeze an
# incorrect MINIMAL_RISK baseline -- not a meaningful parity target.
V0_1_REPRESENTABLE = [
    "01_high_risk_credit_lendfast",
    "02_high_risk_recruitment_ambiguous",
    "03_limited_risk_chatbot",
    "04_minimal_risk_marketing",
    "06_ll144_triggering_nyc_aedt",
    "07_ll144_non_triggering_no_nyc_nexus",
    "08_credit_with_adequate_oversight",
    "09_minimal_risk_inventory_bot",
    "10_ambiguous_low_completeness_summarizer",
    "11_clean_recruitment_no_hitl",
    "12_limited_risk_deepfake_watermarking",
]


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    PARITY_DIR.mkdir(parents=True, exist_ok=True)

    for slug, initiative in FIXTURES.items():
        dumped = json.dumps(
            initiative.model_dump(mode="json"), indent=2, sort_keys=True
        )
        (FIXTURES_DIR / f"{slug}.input_initiative.json").write_text(
            dumped + "\n", encoding="utf-8"
        )
        print(f"wrote fixture input: {slug}")

        if slug in V0_1_REPRESENTABLE:
            v0_1_profile = local_classify(initiative)
            (PARITY_DIR / f"{slug}.v0.1_output.json").write_text(
                v0_1_profile.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"  froze v0.1 output: {slug}")
        else:
            print(f"  skipped v0.1 freeze (not v0.1-representable): {slug}")


if __name__ == "__main__":
    print(
        "REFUSING TO RUN: this script is a historical artifact. Re-running it "
        "today would call the migrated glasswing engine (via the re-exported "
        "local_classify), not v0.1, silently overwriting the genuine v0.1 "
        "baseline. See the module docstring. Exiting without writing anything."
    )
    raise SystemExit(1)
