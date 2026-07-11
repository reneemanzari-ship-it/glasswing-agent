"""build_per_framework_results() -- DECISIONS.md D-010's resolution: LL144
folds into the same uniform, forward-facing payload as the other three
frameworks (glasswing.core.risk.RiskProfile.per_framework_results shape),
rather than living behind a separately-discovered function.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glasswing.engines.classification import build_per_framework_results
from schemas.initiative import Initiative

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SLUGS = sorted(
    p.stem.removesuffix(".input_initiative")
    for p in FIXTURES_DIR.glob("*.input_initiative.json")
)


def _load_initiative(slug: str) -> Initiative:
    path = FIXTURES_DIR / f"{slug}.input_initiative.json"
    return Initiative(**json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("slug", SLUGS)
def test_all_four_frameworks_present_uniformly(slug: str) -> None:
    results = build_per_framework_results(_load_initiative(slug))
    assert set(results.keys()) == {
        "eu_ai_act",
        "nist_ai_rmf",
        "colorado_sb_205",
        "nyc_ll144",
    }
    for framework_id, entry in results.items():
        assert isinstance(entry, dict), framework_id
        assert "citations" in entry, framework_id
        assert "confidence" in entry, framework_id


def test_per_framework_results_matches_classify_initiative_for_eu_and_nist() -> None:
    """The uniform payload must not silently diverge from the same
    classify_initiative() call it's built from."""
    from glasswing.engines.classification import classify_initiative

    initiative = _load_initiative("01_high_risk_credit_lendfast")
    profile = classify_initiative(initiative)
    results = build_per_framework_results(initiative)

    eu = profile.classifications.eu_ai_act
    assert results["eu_ai_act"]["tier"] == eu.tier.value
    assert results["eu_ai_act"]["citations"] == eu.citations
    assert (
        results["nist_ai_rmf"]["manage_attention"]
        == profile.classifications.nist_ai_rmf.manage_attention.value
    )
    assert (
        results["colorado_sb_205"]["high_risk_category"]
        == profile.classifications.colorado_sb_205.high_risk_category
    )


def test_ll144_entry_reflects_the_dedicated_ll144_classifier() -> None:
    from glasswing.engines.classification import classify_nyc_ll144

    triggering = _load_initiative("06_ll144_triggering_nyc_aedt")
    non_triggering = _load_initiative("07_ll144_non_triggering_no_nyc_nexus")

    triggering_results = build_per_framework_results(triggering)
    non_triggering_results = build_per_framework_results(non_triggering)

    assert triggering_results["nyc_ll144"]["applicable"] is True
    assert triggering_results["nyc_ll144"]["requires_bias_audit"] is True
    assert (
        triggering_results["nyc_ll144"]["applicable"]
        == classify_nyc_ll144(triggering).applicable
    )

    assert non_triggering_results["nyc_ll144"]["applicable"] is False


def test_overall_tier_and_human_review_are_not_duplicated_here() -> None:
    """overall_risk_tier/human_review_required live on classify_initiative()'s
    RiskProfile, not in per_framework_results -- LL144 applicability must
    never raise or substitute for the overall tier (same R5 guarantee
    NIST attention already has)."""
    initiative = _load_initiative("06_ll144_triggering_nyc_aedt")
    results = build_per_framework_results(initiative)
    assert "overall_risk_tier" not in results
    assert "human_review_required" not in results
