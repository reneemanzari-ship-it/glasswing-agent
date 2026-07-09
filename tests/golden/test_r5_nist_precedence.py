"""Dedicated regression pin for R5 (prompts/risk_classifier.md):
"overall_risk_tier follows the assigned EU AI Act tier, not NIST
attention... This rule exists because v0.1 derived the overall tier from
NIST attention, which misclassified a plain customer-service chatbot; the
golden test for that case pins this forever."

This must never regress silently (GLASSWING_SPEC.md section 3, Week 2:
"The overall_risk_tier derivation fix... must be pinned by an explicit
golden test"). Kept as its own module, separate from the general golden
suite, so this specific historical bug has a test that can't be
accidentally deleted along with an unrelated fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

from glasswing.engines.classification import classify_initiative
from schemas.initiative import Initiative
from schemas.risk_profile import NISTAttentionLevel, OverallRiskTier

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_initiative(slug: str) -> Initiative:
    path = FIXTURES_DIR / f"{slug}.input_initiative.json"
    return Initiative(**json.loads(path.read_text(encoding="utf-8")))


def test_elevated_nist_attention_does_not_raise_overall_tier_above_moderate() -> None:
    """The canonical case: a plain customer-service chatbot has elevated
    NIST measure/manage attention (it does interact with consumers and
    needs monitoring) but no Annex III or SB 205 high-risk trigger. R5
    requires overall_risk_tier == moderate here, driven by the EU AI Act's
    limited_risk tier -- never "high" or "critical" just because NIST
    flagged elevated attention on some function."""
    for slug in ("03_limited_risk_chatbot", "12_limited_risk_deepfake_watermarking"):
        initiative = _load_initiative(slug)
        profile = classify_initiative(initiative)
        nist = profile.classifications.nist_ai_rmf
        attentions = (
            nist.govern_attention,
            nist.map_attention,
            nist.measure_attention,
            nist.manage_attention,
        )

        # Confirm the premise: this fixture really does have at least one
        # elevated NIST attention level, or the test below wouldn't be
        # exercising the R5 guard at all.
        assert NISTAttentionLevel.ELEVATED in attentions, (
            f"{slug}: fixture no longer has elevated NIST attention; "
            "R5 guard isn't exercised"
        )

        assert profile.classifications.eu_ai_act.tier.value == "limited_risk", slug
        assert profile.overall_risk_tier == OverallRiskTier.MODERATE, (
            f"{slug}: R5 regression -- elevated NIST attention must never raise "
            f"overall_risk_tier above what the EU AI Act tier (limited_risk -> "
            f"moderate) assigns. Got {profile.overall_risk_tier!r}."
        )


def test_critical_nist_attention_does_not_substitute_for_a_high_risk_trigger() -> None:
    """A prohibited-practice system has critical NIST attention across
    every function (the most severe attention level), yet R5 still
    requires overall_risk_tier to track the EU AI Act tier (prohibited),
    not to be independently derived from -- or capped by -- NIST
    attention. This is the sharpest version of R5: even the highest
    possible NIST signal never substitutes for the actual tier
    derivation."""
    initiative = _load_initiative("05_prohibited_social_scoring")
    profile = classify_initiative(initiative)
    nist = profile.classifications.nist_ai_rmf

    assert nist.manage_attention == NISTAttentionLevel.CRITICAL
    assert profile.classifications.eu_ai_act.tier.value == "prohibited"
    assert profile.overall_risk_tier == OverallRiskTier.PROHIBITED
