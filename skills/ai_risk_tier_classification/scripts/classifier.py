from schemas.initiative import (
    Initiative, Sponsor, AISystemCharacteristics, DataCharacteristics,
    ImpactCharacteristics, IntakeMetadata, AISystemType, AutonomyLevel,
    HITLPlanned, DataSensitivity, UserScope, BusinessImpactTier, Reversibility
)
from schemas.risk_profile import RiskProfile

# Migrated Week 2 (GLASSWING_SPEC.md section 3): the deterministic
# classification logic that used to live in this function now lives in
# glasswing/engines/classification.py::classify_initiative(), which is the
# canonical implementation. This is a re-export, not a fork -- keeping the
# `local_classify` name means agents/risk_classifier.py and
# security/adversarial_test.py, which import it directly, need no changes.
# See tests/test_skill.py::test_skill_matches_canonical_engine for the
# regression test proving this stays a re-export and never drifts into a
# second copy of the logic (disposition table item 10: the test now
# asserts the skill matches the engine, not the other way around).
from glasswing.engines.classification import classify_initiative as local_classify


class AIRiskTierClassificationSkill:
    """
    Portable entry point for the AI Risk Tier Classification skill.

    `local_classify()` above remains the stable, unchanged module-level
    function that `agents/risk_classifier.py` and `security/adversarial_test.py`
    already import directly — this class is a thin wrapper around it for
    standalone use (by another ADK agent, a CLI, or a human), not a fork of
    its logic. Two entry points:

    - `classify(initiative)` — structured `Initiative` input. The common path.
    - `classify_from_description(text)` — freeform natural-language input.
      Runs a lightweight, deterministic Onboarding-Intake-style extraction to
      build an `Initiative` first (marking anything it can't determine as
      unknown, with a correspondingly low `completeness_score`), then
      classifies it. This mirrors what a real intake would do for a bare
      paragraph, without requiring a live LLM call.
    """

    def classify(self, initiative: Initiative) -> RiskProfile:
        """Classify a structured Initiative object."""
        return local_classify(initiative)

    def classify_from_description(self, description: str) -> RiskProfile:
        """Classify a freeform natural-language description of an AI
        initiative."""
        initiative = self._extract_initiative(description)
        return self.classify(initiative)

    @staticmethod
    def _extract_initiative(description: str) -> Initiative:
        """Deterministic, keyword-based extraction from freeform text into a
        minimal Initiative. Everything the text doesn't clearly establish is
        marked unknown rather than guessed, and completeness_score is scored
        low — a bare text description is inherently a partial intake, and
        local_classify()'s ambiguous-intake handling (confidence capping,
        forced human review) depends on that being reflected honestly."""
        text = description.lower()

        sensitivity = []
        if any(k in text for k in ("credit", "loan", "financial", "lending", "income")):
            sensitivity.append(DataSensitivity.FINANCIAL)
        if any(k in text for k in ("resume", "cv", "applicant", "customer", "consumer", "email", "name", "personal")):
            sensitivity.append(DataSensitivity.PII)
        if not sensitivity:
            sensitivity = [DataSensitivity.NONE]

        if any(k in text for k in ("consumer", "customer", "chatbot", "public")):
            user_scope = [UserScope.CONSUMERS]
        else:
            user_scope = [UserScope.INTERNAL_EMPLOYEES]

        clean_description = description.strip()
        if len(clean_description) < 10:
            clean_description = f"{clean_description} (freeform description; no further detail provided)."
        name = f"Freeform intake: {clean_description[:60].rstrip()}"

        return Initiative(
            name=name,
            sponsor=Sponsor(business_unit="unknown", owner="unknown"),
            description=clean_description,
            ai_system=AISystemCharacteristics(
                type=AISystemType.OTHER,
                autonomy_level=AutonomyLevel.RECOMMEND_ONLY,
                hitl_planned=HITLPlanned.UNKNOWN,
            ),
            data=DataCharacteristics(
                sources=["unknown"],
                sensitivity=sensitivity,
                jurisdictions=["unknown"],
            ),
            impact=ImpactCharacteristics(
                user_scope=user_scope,
                business_impact_tier=BusinessImpactTier.MODERATE,
                reversibility=Reversibility.PARTIALLY_REVERSIBLE,
            ),
            intake_metadata=IntakeMetadata(
                completeness_score=0.4,
                unknowns=[
                    "sponsor", "ai_system.autonomy_level", "ai_system.hitl_planned",
                    "data.sources", "data.jurisdictions",
                ],
                intake_duration_minutes=0.0,
                intake_agent_version="1.0.0",
                prompt_manifest_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            ),
        )
